"""Clustering hypergraph of a snapshot and the T4 hyper-edge collapse rule, which the method itself applies.

Clustering hypergraph (`incidence`): the six method-centred relations (CLUSTER_RELATIONS), members
restricted to concept nodes, deduplicated, hubs removed; edges left with < 2 members are dropped.
`cites`, `claims`, `presents`, `authored_by` and `proposes_future_work` never enter it.

Edge weights (`edge_weight`):
  inverse_size       w_e = 1 / (|e'| - 1)
  relation_balanced  inverse_size, rescaled so that every relation has the same total weight
                     (inverse_size alone gives evaluated_on ~85% of the mass, notebook 03 section 5)

Collapse onto super-nodes (`collapse`), per fine edge e of arity n spread over lambda_e super-nodes:
  - lambda_e = 1 (m = n): INTERNAL. It links no super-nodes and drops out of every merge score's
    numerator; its weight still counts in the super-node's degree d_A.
  - 1 < lambda_e < n: PARTIAL. One coarse edge over the lambda_e super-nodes; per-super-node
    endpoint counts are kept as metadata.
  - lambda_e >= 3: MULTI-WAY. The coarse edge stays one hyper-edge; it is never split into pairs.
    (lambda_e = n: nothing collapsed yet.)
The merge score (tkh/hierarchy.py) uses exactly this collapsed incidence (presence, i.e. lambda_e):
its numerator is the reduction of the weighted connectivity cut sum_e w_e (lambda_e - 1) caused by
a merge. What the rule loses: endpoint multiplicity in the score (counts are metadata only) and
which fine members took part (kept as fine edge ids in the records).
"""

import numpy as np
from scipy.sparse import csr_matrix

from tkh.semantic import CONCEPT_TYPES

CLUSTER_RELATIONS = ("addresses", "solves", "extends", "uses_component", "uses_technique", "evaluated_on")
EDGE_WEIGHTS = ("inverse_size", "relation_balanced")


def concept_nodes(tkh, snap):
    t = tkh.nodes["type"]
    return sorted(n for n in snap.node_ids if t.at[n] in CONCEPT_TYPES)


def node_papers(tkh, snap):
    """{node: set of snapshot articles it appears in (provenance or incident snapshot edges)}."""
    out = {n: set(tkh.nodes.at[n, "prov_articles"]) & snap.articles for n in snap.node_ids}
    for m, a in zip(snap.edges["members"], snap.edges["article_id"]):
        for v in m:
            if v in out:
                out[v].add(a)
    return out


def hub_threshold(snap, frac):
    """Smallest paper count that makes a node a hub: more than frac * #papers."""
    return int(np.floor(frac * len(snap.articles))) + 1


def hubs(tkh, snap, frac):
    """Concept nodes present in more than `frac` of the snapshot's papers (frac = 1: no hubs)."""
    papers = node_papers(tkh, snap)
    limit = hub_threshold(snap, frac)
    return {n for n in concept_nodes(tkh, snap) if len(papers[n]) >= limit}


def incidence(tkh, snap, items, hubset, edge_weight="inverse_size"):
    """Clustering hypergraph over `items` (concept nodes, in order).

    Returns (B, w, edge_ids, relations): B is a CSR n_items x n_edges 0/1 incidence, w the edge weights.
    """
    if edge_weight not in EDGE_WEIGHTS:
        raise ValueError(f"edge_weight must be one of {EDGE_WEIGHTS}, got {edge_weight!r}")
    pos = {n: i for i, n in enumerate(items)}
    e = snap.edges[snap.edges["relation_type"].isin(CLUSTER_RELATIONS)]
    rows, cols, w, ids, rels = [], [], [], [], []
    for eid, m, r in zip(e.index, e["members"], e["relation_type"]):
        mem = [pos[v] for v in dict.fromkeys(m) if v in pos and v not in hubset]
        if len(mem) < 2:
            continue
        rows += mem
        cols += [len(ids)] * len(mem)
        w.append(1.0 / (len(mem) - 1))
        ids.append(eid)
        rels.append(r)
    w = np.asarray(w)
    if edge_weight == "relation_balanced":
        rel = np.asarray(rels)
        for r in set(rels):
            w[rel == r] /= w[rel == r].sum()
    B = csr_matrix((np.ones(len(rows)), (rows, cols)), shape=(len(items), len(ids)))
    return B, w, ids, rels


def collapse(labels, B):
    """Collapse a fine incidence onto super-nodes. labels: array (n,) of super-node indices 0..K-1.

    Returns dict with counts (K x E endpoint counts), lam (E,), arity (E,), cls (E,) in
    {"internal", "partial", "uncollapsed"} and multiway (E,) bool (lambda >= 3).
    """
    labels = np.asarray(labels)
    K = int(labels.max()) + 1 if len(labels) else 0
    P = csr_matrix((np.ones(len(labels)), (labels, np.arange(len(labels)))), shape=(K, len(labels)))
    counts = (P @ B).tocsr()
    lam = np.asarray((counts > 0).sum(axis=0)).ravel()
    arity = np.asarray(B.sum(axis=0)).ravel()
    cls = np.where(lam == 1, "internal", np.where(lam < arity, "partial", "uncollapsed"))
    return {"counts": counts, "lam": lam, "arity": arity, "cls": cls, "multiway": lam >= 3}


def connectivity_cut(lam, w):
    """Weighted connectivity (lambda - 1) cut: sum_e w_e (lambda_e - 1)."""
    return float(np.sum(np.asarray(w) * (np.asarray(lam) - 1)))


def coarse_edges(levels, items, B, w, edge_ids, relations, sn_ids):
    """T4 collapse of the clustering hypergraph onto every level, for out/<cutoff>/coarse_hyperedges.json.

    levels: [ {key: set(concept members)} per level ]; sn_ids[k][key] = persistent super-node id."""
    pos = {v: i for i, v in enumerate(items)}
    out = {}
    for k, groups in enumerate(levels):
        keys = sorted(groups, key=lambda g: sn_ids[k][g])
        labels = np.empty(len(items), int)
        for i, g in enumerate(keys):
            labels[[pos[v] for v in groups[g]]] = i
        coll = collapse(labels, B)
        C = coll["counts"].tocsc()
        recs = []
        for j, eid in enumerate(edge_ids):
            col = C[:, j]
            recs.append({"fine_edge": eid, "relation_type": relations[j], "arity": int(coll["arity"][j]),
                         "weight": float(w[j]), "lambda": int(coll["lam"][j]), "class": str(coll["cls"][j]),
                         "multiway": bool(coll["multiway"][j]),
                         "endpoint_counts": dict(sorted((sn_ids[k][keys[i]], int(v)) for i, v in zip(col.indices, col.data)))})
        summary = {c: int((coll["cls"] == c).sum()) for c in ("internal", "partial", "uncollapsed")}
        out[k] = {"summary": summary | {"multiway": int(coll["multiway"].sum()), "edges": len(edge_ids)}, "edges": recs}
    return out
