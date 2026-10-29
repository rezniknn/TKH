"""Null models, so that any metric of a SHAC hierarchy can be read against chance.

configuration_null: the type- and period-preserving hypergraph configuration model (degree- and
arity-preserving shuffle; Chodrow 2020, vertex-labelled), applied to the export and sampled by Curveball
trades. Within each stratum (relation, cutoff interval of the edge's paper, member type) the tails
(members[1:]) of the six clustering relations trade members, so that:
  - every node keeps its degree per relation, interval and type; every edge keeps its arity, member-type
    mix, hub members[0], paper and year; no edge gets a duplicate member or its own hub in its tail;
  - hence every snapshot keeps exactly its node set (asserted), and every other relation is untouched.
The null keeps the real names, so it measures what the hypergraph structure adds beyond degrees,
given the semantics. It is run through the same pipeline with the same parameters, and the real
snapshot's hub sets are passed in so that hub_frac means the same thing in real and null runs.

attachment_null: for one transition c0 -> c1, every old concept node at the end of a new paper's clustering edge is
redrawn among the old concept nodes of its type, with probability proportional to their clustering degree up to c0
(preferential attachment). The graph <= c0 and the new nodes stay as they are; so does each edge's arity, type mix and
head. It randomises WHICH old nodes the new papers touch, the null for cross-snapshot stability.

label_permutation (the random-label null, reported as "random_labels"): concept-node ids permuted within
(type, entry interval) over a fixed tree, which keeps
the laminar structure and every super-node's size: the chance baseline for a given size profile.
"""

import bisect
import random

from tkh.coarsen import CLUSTER_RELATIONS, concept_nodes
from tkh.io import from_raw, make_snapshots


def _interval(year, cutoffs):
    return bisect.bisect_left(sorted(cutoffs), year)   # 0: <= c_0, 1: (c_0, c_1], ...


def configuration_null(raw, cutoffs, seed, sweeps=10, intervals=None):
    """Null export (a new dict; `raw` is not modified) and a mixing diagnostic. intervals: rewire only the edges of
    these cutoff intervals (e.g. only a transition's new papers); default all."""
    rng = random.Random(seed)
    ntype = {str(n["id"]): n["type"] for n in raw["nodes"]}
    edges = [dict(e, members=[str(m) for m in e["members"]]) for e in raw["hyperedges"]]
    strata = {}
    for i, e in enumerate(edges):
        if e["relation_type"] in CLUSTER_RELATIONS:
            key = (e["relation_type"], _interval(e["provenance"]["article_year"], cutoffs))
            if intervals is None or key[1] in intervals:
                strata.setdefault(key, []).append(i)
    before = {i: set(edges[i]["members"][1:]) for idx in strata.values() for i in idx}
    trades = 0
    for key in sorted(strata):
        idx = strata[key]
        for _ in range(sweeps * len(idx)):
            if len(idx) < 2:
                break
            a, b = rng.sample(idx, 2)
            trades += _curveball(edges[a], edges[b], ntype, rng)
    moved = sum(len(before[i] - set(edges[i]["members"][1:])) for i in before)
    total = sum(len(s) for s in before.values())
    out = dict(raw, hyperedges=edges, meta=dict(raw.get("meta", {}), null={"model": "configuration", "seed": seed, "sweeps": sweeps,
                                                                             "cutoffs": list(cutoffs), "intervals": intervals and sorted(intervals)}))
    return out, {"seed": seed, "trades": trades, "moved_share": round(moved / max(total, 1), 4)}


def _curveball(ea, eb, ntype, rng):
    """One Curveball trade between two edges' tails, type by type; returns 1 if any member moved."""
    ha, hb = ea["members"][0], eb["members"][0]
    ta, tb = ea["members"][1:], eb["members"][1:]
    sa, sb = set(ta), set(tb)
    keep_a, keep_b = [v for v in ta if v in sb or v == hb], [v for v in tb if v in sa or v == ha]
    free_a, free_b = [v for v in ta if v not in keep_a], [v for v in tb if v not in keep_b]
    new_a, new_b, changed = list(keep_a), list(keep_b), 0
    for t in sorted({ntype[v] for v in free_a + free_b}):
        fa, fb = [v for v in free_a if ntype[v] == t], [v for v in free_b if ntype[v] == t]
        pool = fa + fb
        rng.shuffle(pool)
        new_a += pool[:len(fa)]
        new_b += pool[len(fa):]
        changed |= set(pool[:len(fa)]) != set(fa)
    ea["members"], eb["members"] = [ha] + new_a, [hb] + new_b
    return int(changed)


def null_tkh(raw, articles_path, cutoffs, seed, real=None, sweeps=10, intervals=None):
    """(null TKH, null export, diagnostic); with `real` given, asserts that every snapshot keeps its node set."""
    out, diag = configuration_null(raw, cutoffs, seed, sweeps, intervals)
    tkh = from_raw(out, articles_path, f"null seed {seed}")
    if real is not None:
        for s_null, s_real in zip(make_snapshots(tkh, cutoffs), make_snapshots(real, cutoffs)):
            if s_null.node_ids != s_real.node_ids:
                raise AssertionError(f"null seed {seed} changed the node set of snapshot <= {s_real.cutoff}")
    return tkh, out, diag


def attachment_null(tkh, c0, c1, seed):
    """TKH whose (c0, c1] clustering edges attach to random old concept nodes (see the module docstring)."""
    from dataclasses import replace
    rng = random.Random(seed)
    ntype, entry = tkh.nodes["type"].to_dict(), tkh.nodes["entry_year"].to_dict()
    e = tkh.edges
    clust = e["relation_type"].isin(CLUSTER_RELATIONS)
    deg = {}
    for m in e.loc[clust & (e["article_year"] <= c0), "members"]:
        for v in m[1:]:
            deg[v] = deg.get(v, 0) + 1
    pool = {}
    for v, d in sorted(deg.items()):
        pool.setdefault(ntype[v], ([], []))[0].append(v)
        pool[ntype[v]][1].append(d)
    members = e["members"].copy()
    for eid in sorted(e.index[clust & (e["article_year"] > c0) & (e["article_year"] <= c1)]):
        m = list(members[eid])
        for i in range(1, len(m)):
            v = m[i]
            if entry[v] <= c0 and ntype[v] in pool:
                cand, w = pool[ntype[v]]
                for _ in range(100):   # degree-weighted draw that keeps the edge free of duplicates
                    u = rng.choices(cand, w)[0]
                    if u not in m:
                        m[i] = u
                        break
        members[eid] = m
    return replace(tkh, edges=e.assign(members=members))


def label_permutation(tkh, snap, cutoffs, seed):
    """{concept node: node whose super-node it takes}, a permutation within (type, entry interval)."""
    rng = random.Random(seed)
    strata = {}
    for v in concept_nodes(tkh, snap):
        strata.setdefault((tkh.nodes.at[v, "type"], _interval(tkh.nodes.at[v, "entry_year"], cutoffs)), []).append(v)
    perm = {}
    for ids in strata.values():
        img = ids[:]
        rng.shuffle(img)
        perm.update(zip(ids, img))
    return perm
