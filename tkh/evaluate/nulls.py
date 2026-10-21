"""Null models: degree/arity-preserving hypergraph shuffle and random labels, so that every metric is compared with chance.

Three nulls, each run through the same pipeline and scored with the same metrics against
the REAL node->paper map, citations, names and ground truth:

shuffle_hypergraph(tkh, seed, cutoffs, fixed)
    Structure null. A Curveball shuffle (Strona et al. 2014; Chodrow 2020 for hypergraphs)
    of the clustering-input edges only (CLUSTER_RELATIONS). Two edges of the same
    publication period are drawn; for one node type, the members that are not shared are
    pooled and redistributed, so that every edge keeps its arity and type composition and
    every node keeps its number of edges in every period (hence its degree in every
    cumulative snapshot and its entry year). members[0] (the paper's method) and the
    `fixed` nodes (hubs) never move; edge ids and all other edges are untouched. What is
    destroyed: which concept nodes co-occur in an edge. The null build then uses the REAL
    graph's hub sets (a shuffle changes how many papers a node touches, and recomputed
    hubs would differ: 6 -> 14 at <=2026), so model and null strip the same nodes.
semantic_permutation(tkh, seed, cutoffs)
    Semantics null. A bijection of the name texts among concept nodes of the same type and
    entry period, passed to the build as `text_perm`; structure stays real.
permute_hierarchy(parts, tkh, seed, cutoffs)
    Random-labels null. One permutation of the concept nodes, within (type x entry period
    x paper-count bin), applied to every level and snapshot of a hierarchy. Sizes, nesting,
    the temporal structure and the anchored nodes are kept, so the output passes the
    validator and can be scored on E1, E3 and E4 like the model.

The 2x2 design of the evaluation: struct-null (shuffled structure, real text), sem-null
(real structure, shuffled text) and full-null (both); the full-null is the null of the
hybrid method.
"""

from dataclasses import replace
import random

import numpy as np

from tkh.coarsen import CLUSTER_RELATIONS
from tkh.semantic import CONCEPT_TYPES


def _period(year, cutoffs):
    for i, c in enumerate(sorted(cutoffs)):
        if year <= c:
            return i
    return len(cutoffs)


def shuffle_hypergraph(tkh, seed, cutoffs, fixed=(), sweeps=10):
    """Shuffled copy of tkh (structure null) and diagnostics {retained, trades, ...}."""
    rng = random.Random(seed)
    ntype = tkh.nodes["type"].to_dict()
    fixed = set(fixed)
    e = tkh.edges
    clu = e.index[e["relation_type"].isin(CLUSTER_RELATIONS)]
    members = {i: list(e.at[i, "members"]) for i in clu}
    movable = lambda i: [p for p, v in enumerate(members[i]) if p > 0 and v not in fixed]  # noqa: E731
    strata = {}
    for i in clu:
        strata.setdefault(_period(e.at[i, "article_year"], cutoffs), []).append(i)
    trades = 0
    for ids in strata.values():
        if len(ids) < 2:
            continue
        n_slots = sum(len(movable(i)) for i in ids)
        for _ in range(sweeps * n_slots):
            i, j = rng.sample(ids, 2)
            t = rng.choice(sorted({ntype[members[i][p]] for p in movable(i)} or {None}))
            if t is None:
                continue
            # only nodes absent from the other edge (anywhere, incl. members[0]) can move: no duplicates
            si, sj = set(members[i]), set(members[j])
            pi = [p for p in movable(i) if ntype[members[i][p]] == t and members[i][p] not in sj]
            pj = [p for p in movable(j) if ntype[members[j][p]] == t and members[j][p] not in si]
            if not pi or not pj:
                continue
            pool = sorted({members[i][p] for p in pi} | {members[j][p] for p in pj})
            rng.shuffle(pool)
            for k, p in enumerate(pi):
                members[i][p] = pool[k]
            for k, p in enumerate(pj):
                members[j][p] = pool[len(pi) + k]
            trades += 1
    new = e.copy()
    new["members"] = [members.get(i, m) for i, m in zip(e.index, e["members"])]
    _check_invariants(e, new, clu, ntype, fixed, cutoffs)
    kept = sum(len(set(e.at[i, "members"][1:]) & set(new.at[i, "members"][1:])) for i in clu)
    total = sum(len(e.at[i, "members"]) - 1 for i in clu)
    return replace(tkh, edges=new), {"seed": seed, "trades": trades, "retained_incidence": kept / total if total else 1.0}


def _degrees(edges, ids, cutoffs):
    d = {}
    for i in ids:
        p = _period(edges.at[i, "article_year"], cutoffs)
        for v in edges.at[i, "members"]:
            d[(v, p)] = d.get((v, p), 0) + 1
    return d


def _check_invariants(old, new, clu, ntype, fixed, cutoffs):
    for i in clu:
        a, b = old.at[i, "members"], new.at[i, "members"]
        if len(b) != len(a) or len(set(b)) != len(b) or a[0] != b[0]:
            raise AssertionError(f"edge {i}: arity, duplicate or members[0] invariant broken")
        if sorted(ntype[v] for v in a) != sorted(ntype[v] for v in b):
            raise AssertionError(f"edge {i}: type composition changed")
        if [v for v in a if v in fixed] != [v for v in b if v in fixed]:
            raise AssertionError(f"edge {i}: a fixed node moved")
    if _degrees(old, clu, cutoffs) != _degrees(new, clu, cutoffs):
        raise AssertionError("per-period degrees changed")
    rest = old.index.difference(clu)
    if not all(old.at[i, "members"] == new.at[i, "members"] for i in rest):
        raise AssertionError("a non-clustering edge changed")


def semantic_permutation(tkh, seed, cutoffs):
    """{node: node whose name text it uses}, a bijection within (type, entry period) of concept nodes."""
    rng = random.Random(seed)
    nodes = tkh.nodes
    strata = {}
    for v in sorted(nodes.index[nodes["type"].isin(CONCEPT_TYPES)]):
        strata.setdefault((nodes.at[v, "type"], _period(nodes.at[v, "entry_year"], cutoffs)), []).append(v)
    perm = {}
    for ids in strata.values():
        img = ids[:]
        rng.shuffle(img)
        perm.update(zip(ids, img))
    return perm


def _paper_bin(n):
    return 0 if n <= 1 else 1 if n == 2 else 2


def permute_hierarchy(parts, tkh, seed, cutoffs):
    """parts with concept nodes relabelled by one permutation within (type, entry period, paper-count bin)."""
    rng = random.Random(seed)
    nodes = tkh.nodes
    e = tkh.edges
    papers = {}
    for m, a in zip(e["members"], e["article_id"]):
        for v in m:
            papers.setdefault(v, set()).add(a)
    strata = {}
    for v in sorted(nodes.index[nodes["type"].isin(CONCEPT_TYPES)]):
        n_pap = len(set(nodes.at[v, "prov_articles"]) | papers.get(v, set()))
        strata.setdefault((nodes.at[v, "type"], _period(nodes.at[v, "entry_year"], cutoffs), _paper_bin(n_pap)), []).append(v)
    perm = {}
    for ids in strata.values():
        img = ids[:]
        rng.shuffle(img)
        perm.update(zip(ids, img))
    return {c: [{g: {perm.get(v, v) for v in mem} for g, mem in lv.items()} for lv in levels]
            for c, levels in parts.items()}


def null_build(tkh, cutoffs, budgets, params, kind, seed, fixed=()):
    """Partitions of one null replicate: kind in {"struct", "sem", "full"} (see module doc)."""
    from tkh.coarsen import hubs
    from tkh.hierarchy import build
    from tkh.io import snapshot
    g, perm, diag, hub_sets = tkh, None, {"kind": kind, "seed": seed}, None
    if kind in ("struct", "full"):
        g, d = shuffle_hypergraph(tkh, seed, cutoffs, fixed)
        diag.update(d)
        hub_sets = {c: hubs(tkh, snapshot(tkh, c), params.hub_frac) for c in cutoffs}  # real hubs, as in the model
    if kind in ("sem", "full"):
        perm = semantic_permutation(tkh, seed, cutoffs)
    if kind not in ("struct", "sem", "full"):
        raise ValueError(f"unknown null kind {kind!r}")
    return build(g, cutoffs, budgets, params, text_perm=perm, hub_sets=hub_sets), diag
