"""Structural signal between papers and nodes (notebook 03): which nodes link papers, typed paper-paper links, link views.

Vocabulary:
- concept nodes: CONCEPT_TYPES below (method, task, problem, technique, component, dataset, metric);
- metadata nodes: author, cited_work, claim, future_topic, article;
- a node "links" papers p and q when it occurs in both (in an edge of each, or in the provenance of each).

All functions take an optional snapshot; without one they use the whole export.
"""

from collections import Counter, defaultdict
import math

import numpy as np
import pandas as pd

from tkh.semantic import name_key


key = name_key   # one normaliser for the package (tkh/semantic.py)


# Node types that occur as members of the relations whose hub is a paper's presented method, and those
# relations; notebook 03 section 1 checks both against the export's schema. Defined here, independently of
# any coarsening code.
CONCEPT_TYPES = ("method", "task", "problem", "technique", "component", "dataset", "metric")
METADATA_TYPES = ("author", "cited_work", "claim", "future_topic", "article")
CONCEPT_RELATIONS = ("addresses", "solves", "extends", "uses_component", "uses_technique", "evaluated_on")


def schema_check(tkh):
    """(relation, hub types, member types) per relation, and whether the method-centred relations hold exactly the
    concept types as members."""
    ntype = tkh.nodes["type"].to_dict()
    rows = {}
    for m, r in zip(tkh.edges["members"], tkh.edges["relation_type"]):
        d = rows.setdefault(r, [set(), set()])
        d[0].add(ntype[m[0]])
        d[1].update(ntype[v] for v in m[1:])
    method_hub = sorted(r for r, (h, _) in rows.items() if h == {"method"})
    members = set().union(*(rows[r][1] for r in method_hub))
    ok = set(method_hub) == set(CONCEPT_RELATIONS) and members == set(CONCEPT_TYPES)
    table = pd.DataFrame({"hub types": {r: ", ".join(sorted(h)) for r, (h, _) in rows.items()},
                          "member types": {r: ", ".join(sorted(m)) for r, (_, m) in rows.items()}})
    return table.sort_index(), ok


def _edges(tkh, snap=None):
    return tkh.edges if snap is None else snap.edges


def _articles(tkh, snap=None):
    return set(tkh.articles.index) if snap is None else set(snap.articles)


def node_papers(tkh, snap=None):
    """{node: set of papers} from edge membership and node provenance (restricted to the snapshot)."""
    arts = _articles(tkh, snap)
    out = defaultdict(set)
    for m, a in zip(_edges(tkh, snap)["members"], _edges(tkh, snap)["article_id"]):
        for v in m:
            out[v].add(a)
    ids = tkh.nodes.index if snap is None else snap.node_ids
    for v in ids:
        out[v] |= set(tkh.nodes.at[v, "prov_articles"]) & arts
    return dict(out)


def node_roles(tkh, snap=None):
    """{(node, paper): set of (relation, position)} with position 'hub' (members[0]) or 'member'."""
    out = defaultdict(set)
    for m, r, a in zip(_edges(tkh, snap)["members"], _edges(tkh, snap)["relation_type"], _edges(tkh, snap)["article_id"]):
        for i, v in enumerate(m):
            out[(v, a)].add((r, "hub" if i == 0 else "member"))
    return dict(out)


def sharing_by_type(tkh, snap=None):
    """Per node type: nodes, nodes in >= 2 papers, max papers per node, paper pairs they link."""
    papers = node_papers(tkh, snap)
    ntype = tkh.nodes["type"]
    rows = []
    for t in sorted(ntype.unique()):
        ps = [len(papers.get(v, ())) for v in ntype.index[ntype == t] if v in papers]
        pairs = set()
        for v in ntype.index[ntype == t]:
            s = sorted(papers.get(v, ()))
            if len(s) > 1:
                pairs |= {(s[i], s[j]) for i in range(len(s)) for j in range(i + 1, len(s))}
        ps = np.array(ps) if ps else np.zeros(1)
        rows.append({"type": t, "kind": "concept" if t in CONCEPT_TYPES else "metadata", "nodes": len(ps),
                     "in >= 2 papers": int((ps >= 2).sum()), "share shared": float((ps >= 2).mean()),
                     "max papers": int(ps.max()), "paper pairs linked": len(pairs)})
    return pd.DataFrame(rows).set_index("type").sort_values(["kind", "paper pairs linked"], ascending=[True, False])


def pair_matrix(tkh, types, snap=None, weight="idf", max_paper_share=None, exclude=()):
    """Paper x paper matrix of links through shared nodes of the given types.

    weight: "count" (number of shared nodes) or "idf" (each shared node adds log(N / n_v), so a node
    in two papers counts more than one in twenty). max_paper_share: drop nodes in more than this
    share of the papers (hubs). Returns (DataFrame, contributing nodes per pair)."""
    papers = node_papers(tkh, snap)
    arts = sorted(_articles(tkh, snap), key=lambda a: (tkh.articles.at[a, "year"], str(a)))
    idx = {a: i for i, a in enumerate(arts)}
    N = len(arts)
    ntype = tkh.nodes["type"].to_dict()
    M = np.zeros((N, N))
    via = defaultdict(list)
    for v, ps in papers.items():
        if ntype[v] not in types or v in exclude or len(ps) < 2:
            continue
        if max_paper_share is not None and len(ps) > max_paper_share * N:
            continue
        w = 1.0 if weight == "count" else math.log(N / len(ps))
        s = sorted(ps, key=idx.get)
        for i in range(len(s)):
            for j in range(i + 1, len(s)):
                M[idx[s[i]], idx[s[j]]] += w
                M[idx[s[j]], idx[s[i]]] += w
                via[(s[i], s[j])].append(v)
    return pd.DataFrame(M, index=arts, columns=arts), dict(via)


def link_summary(M):
    """Linked pairs, density, connected components and isolated papers of a paper x paper matrix."""
    A = M.values > 0
    n = len(A)
    seen, comps = set(), []
    for s in range(n):
        if s in seen:
            continue
        stack, comp = [s], []
        seen.add(s)
        while stack:
            u = stack.pop()
            comp.append(u)
            for v in np.nonzero(A[u])[0]:
                if v not in seen:
                    seen.add(v)
                    stack.append(v)
        comps.append(comp)
    pairs = int(A[np.triu_indices(n, 1)].sum())
    return {"papers": n, "linked pairs": pairs, "density": pairs / (n * (n - 1) / 2),
            "components": len(comps), "largest component": max(map(len, comps)),
            "isolated papers": sum(len(c) == 1 for c in comps),
            "median partners per paper": float(np.median(A.sum(axis=1)))}


def typed_links(tkh, snap=None, max_paper_share=0.2):
    """Paper pairs linked through a shared concept node, typed by the relations the node has in each paper.

    One row per (pair, node). 'link' names the pair of roles (e.g. 'evaluated_on ~ evaluated_on' = a
    shared benchmark; 'extends -> presents' = one paper builds on the method the other presents, with
    'earlier' set to the presenting paper; 'same year' flags pairs whose order the years cannot confirm)."""
    papers = node_papers(tkh, snap)
    roles = node_roles(tkh, snap)
    ntype = tkh.nodes["type"].to_dict()
    year = tkh.articles["year"].to_dict()
    N = len(_articles(tkh, snap))
    rows = []
    for v, ps in papers.items():
        if ntype[v] not in CONCEPT_TYPES or len(ps) < 2:
            continue
        hub = max_paper_share is not None and len(ps) > max_paper_share * N
        s = sorted(ps, key=lambda a: (year[a], str(a)))
        for i in range(len(s)):
            for j in range(i + 1, len(s)):
                a, b = s[i], s[j]  # a is not later than b
                ra = sorted({r for r, _ in roles.get((v, a), ())}) or ["(provenance only)"]
                rb = sorted({r for r, _ in roles.get((v, b), ())}) or ["(provenance only)"]
                # 'extends' as a MEMBER (a presented method is also the hub of its paper's extends star)
                ext_a = ("extends", "member") in roles.get((v, a), ())
                ext_b = ("extends", "member") in roles.get((v, b), ())
                if ("presents" in ra and ext_b) or ("presents" in rb and ext_a):
                    link = "extends -> presents (lineage)"      # direction from the roles, not from the year order
                    if "presents" in rb:
                        a, b = b, a                             # 'earlier' = the presenting paper
                else:
                    link = " ~ ".join(sorted(["/".join(ra), "/".join(rb)]))
                rows.append({"earlier": a, "later": b, "node": v, "type": ntype[v], "papers of node": len(ps),
                             "hub": hub, "same year": year[a] == year[b], "link": link})
    return pd.DataFrame(rows)


def lineage_pairs(tkh, snap=None):
    """(later, earlier) paper pairs where the later paper's extends edge contains the earlier paper's presented method."""
    e = _edges(tkh, snap)
    presented = {a: m[1] for m, r, a in zip(e["members"], e["relation_type"], e["article_id"]) if r == "presents"}
    owner = {v: a for a, v in presented.items()}
    return sorted({(a, owner[v]) for m, r, a in zip(e["members"], e["relation_type"], e["article_id"])
                   if r == "extends" for v in m[1:] if v in owner and owner[v] != a})


def name_keys(tkh, v):
    sf = tkh.nodes.at[v, "surface_form"]
    al = tkh.nodes.at[v, "aliases"] if "aliases" in tkh.nodes else None
    return {key(s) for s in [sf, *(al if isinstance(al, list) else [])]} - {""}


def citation_name_pairs(tkh, snap=None):
    """(citing, cited) paper pairs where a cited work's name equals the name of the cited paper's presented method."""
    e = _edges(tkh, snap)
    presented = {a: m[1] for m, r, a in zip(e["members"], e["relation_type"], e["article_id"]) if r == "presents"}
    by_key = defaultdict(set)
    for a, v in presented.items():
        for k in name_keys(tkh, v):
            by_key[k].add(a)
    out = set()
    for m, r, a in zip(e["members"], e["relation_type"], e["article_id"]):
        if r != "cites":
            continue
        for w in m[1:]:
            for k in name_keys(tkh, w):
                out |= {(a, b) for b in by_key.get(k, ()) if b != a}
    return sorted(out)


def cited_work_name_overlap(tkh, snap=None):
    """How cited-work names coincide with concept-node names: overall, and within the citing paper."""
    papers = node_papers(tkh, snap)
    ntype = tkh.nodes["type"].to_dict()
    concept_keys = defaultdict(set)
    paper_keys = defaultdict(set)
    for v, ps in papers.items():
        if ntype[v] in CONCEPT_TYPES:
            for k in name_keys(tkh, v):
                concept_keys[k].add(v)
                for a in ps:
                    paper_keys[a].add(k)
    e = _edges(tkh, snap)
    cited = [(a, w) for m, r, a in zip(e["members"], e["relation_type"], e["article_id"]) if r == "cites" for w in m[1:]]
    works = {w for _, w in cited}
    return {"cited works": len(works),
            "named like some concept node": sum(any(k in concept_keys for k in name_keys(tkh, w)) for w in works),
            "citation incidences": len(cited),
            "named like a concept of the citing paper": sum(bool(name_keys(tkh, w) & paper_keys[a]) for a, w in cited)}


def citation_coupling(tkh, snap=None, works=None):
    """Residual citation coupling between citing papers, computed here without any coarsening code.

    Each citing paper's cited works, minus those whose normalised name equals a concept-node name of that paper
    (the residual filter), optionally restricted to `works`; coupling = IDF-weighted Salton cosine. Returns
    (papers, coupling matrix, removed citation incidences). Exploratory (notebook 03): the method's held-out
    check (eval/p3.py) uses its own fixed ruler, with aliases and a no-overlap pair set."""
    papers = node_papers(tkh, snap)
    ntype = tkh.nodes["type"].to_dict()
    pk = defaultdict(set)
    for v, ps in papers.items():
        if ntype[v] in CONCEPT_TYPES:
            for kk in name_keys(tkh, v):
                for a in ps:
                    pk[a].add(kk)
    e = _edges(tkh, snap)
    cites, removed = defaultdict(set), 0
    for m, r, a in zip(e["members"], e["relation_type"], e["article_id"]):
        if r != "cites":
            continue
        for w in m[1:]:
            if name_keys(tkh, w) & pk[a]:
                removed += 1
            elif works is None or w in works:
                cites[a].add(w)
    P = sorted((a for a in cites if cites[a]), key=str)
    df = Counter(w for a in P for w in cites[a])
    idx = {w: i for i, w in enumerate(sorted(df))}
    X = np.zeros((len(P), len(idx)))
    for i, a in enumerate(P):
        for w in cites[a]:
            X[i, idx[w]] = math.log(len(P) / df[w])
    nrm = np.sqrt((X ** 2).sum(axis=1))
    G = X @ X.T
    den = np.outer(nrm, nrm)
    return P, np.divide(G, den, out=np.zeros_like(G), where=den > 0), removed


def hub_sensitivity(tkh, types, shares=(None, 0.5, 0.3, 0.2, 0.1, 0.05), snap=None):
    rows = []
    for sh in shares:
        M, _ = pair_matrix(tkh, types, snap, weight="count", max_paper_share=sh)
        rows.append({"drop nodes in more than": "nothing" if sh is None else f"{sh:.0%} of papers", **link_summary(M)})
    return pd.DataFrame(rows).set_index("drop nodes in more than")


def concept_components(tkh, snap, relations=CONCEPT_RELATIONS, max_paper_share=0.2):
    """Connected components of the concept-relation hypergraph (concept relations; hubs removed from
    the node set): returns (component sizes, papers spanned by each, in the same order, hub set)."""
    papers = node_papers(tkh, snap)
    ntype = tkh.nodes["type"].to_dict()
    N = len(snap.articles)
    hubs = {v for v, ps in papers.items() if ntype[v] in CONCEPT_TYPES and len(ps) > max_paper_share * N}
    parent = {}

    def find(x):
        parent.setdefault(x, x)
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    items = [v for v in snap.node_ids if ntype[v] in CONCEPT_TYPES and v not in hubs]
    for v in items:
        find(v)
    e = snap.edges[snap.edges["relation_type"].isin(relations)]
    for m in e["members"]:
        mem = [v for v in m if ntype[v] in CONCEPT_TYPES and v not in hubs]
        for v in mem[1:]:
            parent[find(v)] = find(mem[0])
    comp = defaultdict(list)
    for v in items:
        comp[find(v)].append(v)
    comps = sorted(comp.values(), key=len, reverse=True)
    sizes = [len(c) for c in comps]
    spans = [len(set().union(*(papers.get(v, set()) for v in c))) for c in comps]  # aligned with sizes
    return sizes, spans, hubs


def _assoc(a, b):
    from scipy.stats import spearmanr
    la, lb = a > 0, b > 0
    n11, n10, n01, n00 = (la & lb).sum(), (la & ~lb).sum(), (~la & lb).sum(), (~la & ~lb).sum()
    return {"spearman": float(spearmanr(a, b).correlation),
            "odds ratio": float((n11 + 0.5) * (n00 + 0.5) / ((n10 + 0.5) * (n01 + 0.5))),
            "P(B | A)": float(n11 / max(1, la.sum())), "P(B | not A)": float(n01 / max(1, (~la).sum()))}


def matrix_agreement(A, B, n_perm=999, strata=None, seed=0):
    """Agreement of two paper x paper matrices over ALL paper pairs, with a permutation null.

    Reports shared linked pairs and Jaccard, the all-pairs Spearman of the weights, the odds ratio
    of 'linked in A' vs 'linked in B', and P(linked in B | linked in A) vs | not linked in A. The null
    permutes B's paper labels (within `strata`, e.g. publication years, if given), keeping both
    graphs' structure; p = (1 + #{null >= observed}) / (R + 1). A Spearman restricted to pairs linked
    in at least one view is NOT used: it is biased strongly negative by construction."""
    B = B.loc[A.index, A.index]                      # align paper order
    iu = np.triu_indices(len(A), 1)
    a, Bv = A.values[iu], B.values
    obs = _assoc(a, Bv[iu])
    rng = np.random.default_rng(seed)
    labels = np.arange(len(A))
    groups = [labels] if strata is None else [labels[np.asarray(strata) == s] for s in sorted(set(strata))]
    null = []
    for _ in range(n_perm):
        p = labels.copy()
        for g in groups:
            p[g] = rng.permutation(g)
        null.append(_assoc(a, Bv[np.ix_(p, p)][iu]))
    la, lb = a > 0, Bv[iu] > 0
    out = {"pairs in A": int(la.sum()), "pairs in B": int(lb.sum()), "pairs in both": int((la & lb).sum()),
           "Jaccard": float((la & lb).sum() / max(1, (la | lb).sum())), **obs}
    for k in ("spearman", "odds ratio"):
        v = np.array([n[k] for n in null])
        out[f"{k} null mean"] = float(v.mean())
        out[f"{k} p"] = float((1 + (v >= obs[k]).sum()) / (n_perm + 1))
    return out


def relation_bridges(tkh, snap=None, max_paper_share=0.2):
    """Per concept relation: edges, member slots, members that are shared across papers (bridges), and the
    paper pairs those bridges link (hubs excluded)."""
    papers = node_papers(tkh, snap)
    ntype = tkh.nodes["type"].to_dict()
    N = len(_articles(tkh, snap))
    e = _edges(tkh, snap)
    rows = []
    for r in CONCEPT_RELATIONS:
        sub = e[e["relation_type"] == r]
        slots = [v for m in sub["members"] for v in m[1:] if ntype[v] in CONCEPT_TYPES]
        in_rel = defaultdict(set)                       # papers in which the node is a member of THIS relation
        for m, a in zip(sub["members"], sub["article_id"]):
            for v in m[1:]:
                in_rel[v].add(a)
        bridges = {v for v in set(slots) if len(in_rel[v]) >= 2 and len(papers.get(v, ())) <= max_paper_share * N}
        pairs = set()
        for v in bridges:
            s = sorted(in_rel[v], key=str)
            pairs |= {(s[i], s[j]) for i in range(len(s)) for j in range(i + 1, len(s))}
        rows.append({"relation": r, "edges": len(sub), "member slots": len(slots),
                     "distinct members": len(set(slots)), "bridge members (in 2+ papers within the relation, not hubs)": len(bridges),
                     "share of members that bridge": len(bridges) / max(1, len(set(slots))),
                     "paper pairs linked within the relation": len(pairs)})
    return pd.DataFrame(rows).set_index("relation")


def relation_weight(tkh, snap=None, max_paper_share=0.2):
    """Per concept relation, on the concept-relation hypergraph (concept members, hubs removed, >= 2 members):
    its share of the structure under candidate edge weightings.
    - edges: every edge counts 1;
    - member slots: every member occurrence counts 1 (large stars count more);
    - inverse size: an edge counts 1/(|e| - 1) (a common normalisation, equal to 1 per member beyond the first);
    - clique pairs: an edge counts |e|(|e| - 1)/2, as in an unweighted pairwise projection.
    Also the median arity and the share of the relation's edges contributed by its three most prolific papers."""
    papers = node_papers(tkh, snap)
    ntype = tkh.nodes["type"].to_dict()
    N = len(_articles(tkh, snap))
    hubset = {v for v, ps in papers.items() if ntype[v] in CONCEPT_TYPES and len(ps) > max_paper_share * N}
    e = _edges(tkh, snap)
    rows = []
    for m, r, a in zip(e["members"], e["relation_type"], e["article_id"]):
        if r not in CONCEPT_RELATIONS:
            continue
        mem = [v for v in dict.fromkeys(m) if ntype[v] in CONCEPT_TYPES and v not in hubset]
        if len(mem) >= 2:
            n = len(mem)
            rows.append({"relation": r, "paper": a, "arity": n, "edges": 1.0, "member slots": float(n),
                         "inverse size": 1 / (n - 1), "clique pairs": n * (n - 1) / 2})
    d = pd.DataFrame(rows)
    g = d.groupby("relation")
    out = pd.DataFrame({"edges": g.size()})
    for k in ("edges", "member slots", "inverse size", "clique pairs"):
        out[f"share: {k}"] = g[k].sum() / d[k].sum()
    out["median arity"] = g["arity"].median()
    out["top-3 papers' share of the edges"] = g["paper"].apply(lambda s: s.value_counts().head(3).sum() / len(s))
    return out.sort_values("share: edges", ascending=False)


# ---------------------------------------------------------------- method-independent coarse-level analysis

def concept_incidence(tkh, snap=None, max_paper_share=0.2):
    """The concept-relation hypergraph as an incidence: (items, B nodes x edges 0/1 dense, edge papers, relations).
    Members restricted to concept nodes, hubs (> max_paper_share of papers, or None for no removal) removed from
    the edges and from the items, edges with < 2 members dropped."""
    papers = node_papers(tkh, snap)
    ntype = tkh.nodes["type"].to_dict()
    N = len(_articles(tkh, snap))
    ids = tkh.nodes.index if snap is None else snap.node_ids
    concept = sorted(v for v in ids if ntype[v] in CONCEPT_TYPES)
    hubset = set() if max_paper_share is None else {v for v in concept if len(papers.get(v, ())) > max_paper_share * N}
    items = [v for v in concept if v not in hubset]       # hubs are not items: they carry no edge
    pos = {v: i for i, v in enumerate(items)}
    e = _edges(tkh, snap)
    cols, eps, rels = [], [], []
    for m, r, a in zip(e["members"], e["relation_type"], e["article_id"]):
        if r not in CONCEPT_RELATIONS:
            continue
        mem = [pos[v] for v in dict.fromkeys(m) if v in pos and v not in hubset]
        if len(mem) >= 2:
            cols.append(mem)
            eps.append(a)
            rels.append(r)
    B = np.zeros((len(items), len(cols)))
    for j, mem in enumerate(cols):
        B[mem, j] = 1
    return items, B, np.array(eps), np.array(rels)


def reference_partition(kind, items, k, tkh, seed=0, snap=None):
    """A partition of `items` into k groups that encodes no clustering algorithm (labels 0..k-1).
    - "random": uniformly random groups of (almost) equal size;
    - "paper": each node goes with its earliest paper; for k < papers every group is a random set of whole papers,
      for k >= papers every group is part of one paper (each paper's nodes split at random into its share of k);
    - "type": groups never mix node types, each type split at random in proportion to its size (needs k >= types)."""
    rng = np.random.default_rng(seed)
    n = len(items)
    if not 1 <= k <= n:
        raise ValueError(f"k={k} must be between 1 and the number of items ({n})")
    if kind == "random":
        return rng.permutation(np.arange(n) % k)
    if kind == "type":
        key_of = [tkh.nodes.at[v, "type"] for v in items]
    elif kind == "paper":
        papers = node_papers(tkh, snap)
        year = tkh.articles["year"].to_dict()
        key_of = [min(papers.get(v) or {"?"}, key=lambda a: (year.get(a, 0), str(a))) for v in items]
    else:
        raise ValueError(kind)
    keys = sorted(set(key_of), key=str)
    if kind == "type" and k < len(keys):
        raise ValueError(f"a type-preserving partition needs k >= {len(keys)} types")
    members = {kk: [i for i, x in enumerate(key_of) if x == kk] for kk in keys}
    lab = np.empty(n, int)
    if k < len(keys):
        grp = rng.permutation(np.arange(len(keys)) % k)
        for kk, g in zip(keys, grp):
            lab[members[kk]] = g
        return lab
    quota = np.maximum(1, np.floor(k * np.array([len(members[kk]) for kk in keys]) / n)).astype(int)
    while quota.sum() > k:
        quota[np.argmax(quota)] -= 1
    while quota.sum() < k:
        quota[np.argmax([len(members[kk]) / q for kk, q in zip(keys, quota)])] += 1
    base = 0
    for kk, q in zip(keys, quota):
        idx = rng.permutation(members[kk])
        lab[idx] = base + np.arange(len(idx)) % min(q, len(idx))
        base += q
    return np.unique(lab, return_inverse=True)[1]


def collapse_stats(labels, B, w=None, item_papers=None, n_papers=None, affinity_weights=None):
    """What a partition does to the hypergraph when every fine edge is collapsed onto the groups.

    For each edge, lambda = number of distinct groups it touches. Returns: share of edges that become internal
    (lambda = 1), share of the linking edges (lambda >= 2) that stay multi-way (lambda >= 3), share of group pairs
    that share an edge, the pairs a pairwise projection creates per multi-way edge, the Spearman between a
    presence-based and a count-based group-pair affinity, and (if paper sets are given) the Spearman between a
    group's paper coverage and its size.

    The affinity between groups A, B is the weighted shared-edge mass normalised by the groups' weighted degrees,
    computed once from presence (0/1 per edge) and once from endpoint counts. `affinity_weights` maps a name to an
    edge-weight vector ({"uniform": ones} by default; `w` is kept for backward compatibility and means {"w": w})."""
    from scipy.stats import spearmanr
    labels = np.unique(np.asarray(labels), return_inverse=True)[1]   # no empty groups from label gaps
    K = labels.max() + 1
    if affinity_weights is None:
        affinity_weights = {"uniform": np.ones(B.shape[1])} if w is None else {"w": w}
    P = np.zeros((K, len(labels)))
    P[labels, np.arange(len(labels))] = 1
    cnt = P @ B
    pres = (cnt > 0).astype(float)
    lam = pres.sum(axis=0)
    live = lam >= 2
    iu = np.triu_indices(K, 1)
    out = {"groups": int(K), "internal edges": float((lam == 1).mean()),
           "multi-way among linking edges": float((lam[live] >= 3).mean()) if live.any() else np.nan,
           "projection pairs per multi-way edge": float((lam[lam >= 3] * (lam[lam >= 3] - 1) / 2).mean()) if (lam >= 3).any() else np.nan,
           "group pairs sharing an edge": float(((pres @ pres.T)[iu] > 0).mean())}
    for nm, wv in affinity_weights.items():
        d = pres @ wv
        Hp = (pres * wv) @ pres.T / np.sqrt(np.outer(d, d) + 1e-300)
        dc = cnt @ wv
        Hc = (cnt * wv) @ cnt.T / np.sqrt(np.outer(dc, dc) + 1e-300)
        nz = (Hp[iu] > 0) | (Hc[iu] > 0)
        out[f"Spearman(presence, counts), {nm} weights"] = float(spearmanr(Hp[iu][nz], Hc[iu][nz]).correlation) if nz.sum() > 2 else np.nan
    if item_papers is not None:
        sizes = np.bincount(labels, minlength=K)
        cover = [len(set().union(*(item_papers[i] for i in np.nonzero(labels == g)[0]))) / n_papers for g in range(K)]
        out["median paper coverage"] = float(np.median(cover))
        out["Spearman(coverage, size)"] = float(spearmanr(cover, sizes).correlation) if np.ptp(sizes) > 0 else np.nan
    return out


__all__ = ["METADATA_TYPES", "CONCEPT_RELATIONS", "node_papers", "node_roles", "sharing_by_type", "pair_matrix",
           "link_summary", "typed_links", "lineage_pairs", "citation_name_pairs", "cited_work_name_overlap",
           "hub_sensitivity", "concept_components", "matrix_agreement", "relation_bridges", "relation_weight", "concept_incidence", "reference_partition",
           "collapse_stats", "citation_coupling", "schema_check", "CONCEPT_TYPES", "Counter"]
