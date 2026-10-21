"""T4: hyper-edge collapse rule (m = n, 1 < m < n, three or more super-nodes). This rule is applied by the method itself, not only described.

The clustering hypergraph of a snapshot (`incidence`) uses only the concept relations
(CLUSTER_RELATIONS) restricted to concept nodes, with hub nodes removed. `cites`,
`claims`, `presents`, `authored_by` and `proposes_future_work` never enter it.

Collapse onto super-nodes (`collapse`), per fine hyper-edge e with arity n and its
endpoints spread over lambda_e distinct super-nodes:
  - lambda_e = 1 (m = n, all endpoints in one super-node): the edge becomes INTERNAL. It
    no longer links super-nodes and carries no affinity; it is kept as metadata (count
    and weight of internal edges per super-node).
  - 1 < lambda_e < n (some endpoints share a super-node): a COARSE edge over the
    lambda_e distinct super-nodes, with per-super-node endpoint counts kept as metadata.
  - lambda_e >= 3: the coarse edge stays ONE multi-way hyper-edge; it is never split into
    pairs. (lambda_e = n means nothing collapsed yet.)
What the rule loses: which fine members participated (kept only as fine edge ids) and the
endpoint multiplicity in the merge score (the score uses presence, i.e. lambda_e; counts
are metadata). The merge score of tkh.hierarchy is the reduction of the weighted
connectivity cut  sum_e w_e (lambda_e - 1)  that a merge causes, which is computed from
exactly this collapsed incidence.
"""

import numpy as np
from scipy.sparse import csr_matrix

from tkh.semantic import CONCEPT_TYPES

CLUSTER_RELATIONS = ("addresses", "solves", "extends", "uses_component", "uses_technique", "evaluated_on")


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


def hubs(tkh, snap, frac):
    """Concept nodes present in more than `frac` of the snapshot's papers (generic hubs)."""
    papers = node_papers(tkh, snap)
    limit = frac * len(snap.articles)
    return {n for n in concept_nodes(tkh, snap) if len(papers[n]) > limit}


def incidence(tkh, snap, items, hubset):
    """Clustering hypergraph over `items` (concept nodes, in order).

    Returns (B, w, edge_ids, relations): B is a CSR n_items x n_edges 0/1 incidence, w the
    edge weights 1 / (|e'| - 1) on the reduced edges e' (hubs and non-items removed; edges
    left with < 2 members dropped).
    """
    pos = {n: i for i, n in enumerate(items)}
    e = snap.edges[snap.edges["relation_type"].isin(CLUSTER_RELATIONS)]
    rows, cols, w, ids, rels = [], [], [], [], []
    for eid, m, r in zip(e.index, e["members"], e["relation_type"]):
        mem = [pos[v] for v in dict.fromkeys(m) if v in pos and v not in hubset]
        if len(mem) < 2:
            continue
        j = len(ids)
        rows += mem
        cols += [j] * len(mem)
        w.append(1.0 / (len(mem) - 1))
        ids.append(eid)
        rels.append(r)
    B = csr_matrix((np.ones(len(rows)), (rows, cols)), shape=(len(items), len(ids)))
    return B, np.asarray(w), ids, rels


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


def coarse_edge_records(coll, w, edge_ids, relations, sn_ids):
    """JSON-ready coarse hyper-edges (one per fine edge), for out/<cutoff>/coarse_hyperedges.json."""
    C = coll["counts"].tocsc()
    out = []
    for j, eid in enumerate(edge_ids):
        col = C[:, j]
        members = {sn_ids[i]: int(v) for i, v in zip(col.indices, col.data)}
        out.append({"fine_edge": eid, "relation_type": relations[j], "arity": int(coll["arity"][j]),
                    "weight": float(w[j]), "lambda": int(coll["lam"][j]), "class": str(coll["cls"][j]),
                    "multiway": bool(coll["multiway"][j]), "endpoint_counts": dict(sorted(members.items()))})
    return out
