"""Stability: rebuild after removing 10% of hyper-edges (5 seeds), plus real cross-snapshot stability. Reports ARI with confidence intervals.

T6 asks for both, per level of the hierarchy, as Adjusted Rand Index with confidence
intervals / significance rather than point estimates:

perturbation_stability(tkh, build, cutoffs)
    For each seed, remove 10% of the hyper-edges, stratified by publication period
    (round(10%) of the edges of each period between consecutive cutoffs), so every
    cumulative snapshot loses ~10% and the perturbation is consistent across snapshots.
    Rebuild with the same `build` function and compute ARI between the original and the
    rebuilt partition for every snapshot and level, on that snapshot's node set (removing
    edges does not remove nodes). Summary: mean with a 95% Student-t interval over seeds.

cross_snapshot_stability(partitions, cutoffs)
    For consecutive snapshots t -> t+1 and every level, ARI between the two partitions
    restricted to the nodes present in both. Variability: 95% percentile interval over
    random half-subsamples of the common nodes without replacement (a bootstrap with
    replacement duplicates nodes, whose pairs agree by construction and bias ARI upwards).
    The partitions are held fixed, so this reflects which nodes are scored, not clustering
    uncertainty. Significance: one-sided permutation test against random labels, permuting
    the later partition's labels over the common nodes (cluster sizes preserved);
    p = (1 + #{ARI_perm >= ARI_obs}) / (R + 1); with R = 999 the floor is 0.001. This null is
    weak (any shared structure beats it); the informative comparison is method vs null model.
change_localisation(tkh, partitions, cutoffs)
    P5 metric that a temporal prior cannot inflate by itself: for consecutive snapshots,
    the mean reassignment of old nodes TOUCHED by a new clustering edge divided by that of
    UNTOUCHED old nodes. Reassignment of node v = 1 - Jaccard of its co-members (common
    nodes only) in the two partitions. A ratio > 1 means change is concentrated where the
    data changed; freezing everything gives 0/0 and over-smoothing pushes the ratio to 1.
    Significance: permutation of the touched/untouched labels.

Scope (after review of the first version): perturbation removes edges of the clustering
relations only (relations=CLUSTER_RELATIONS; relations=None is the literal "10% of all
hyper-edges" variant, labelled as such), and every measure is computed on concept nodes
only, because anchored nodes follow their anchor and would inflate agreement.

Every row also reports the largest cluster's share of nodes: ARI counts node pairs, so a
giant cluster dominates it and the value then mostly says whether the giant persists.

`build(tkh) -> {cutoff: [ {key: set(members)} per level ]}`; partitions can also be read
from written outputs with read_partitions(out_dir, cutoffs).
"""

from dataclasses import replace
from pathlib import Path
import json
import random

import numpy as np
from scipy import stats

from tkh.structure import CONCEPT_RELATIONS as CLUSTER_RELATIONS, CONCEPT_TYPES


# ---------------------------------------------------------------- ARI and intervals

def ari(a, b):
    """Adjusted Rand Index (Hubert & Arabie 1985) of two label sequences over the same items."""
    a, b = np.asarray(a), np.asarray(b)
    if a.shape != b.shape:
        raise ValueError("label sequences differ in length")
    n = len(a)
    if n < 2:
        return 1.0
    _, ai = np.unique(a, return_inverse=True)
    _, bi = np.unique(b, return_inverse=True)
    cont = np.bincount(ai * (bi.max() + 1) + bi, minlength=(ai.max() + 1) * (bi.max() + 1)).astype(float)
    cont = cont.reshape(ai.max() + 1, bi.max() + 1)
    c2 = lambda x: x * (x - 1) / 2.0
    index = c2(cont).sum()
    sa, sb, total = c2(cont.sum(axis=1)).sum(), c2(cont.sum(axis=0)).sum(), c2(n)
    expected = sa * sb / total
    maximum = (sa + sb) / 2.0
    if maximum == expected:  # both partitions trivial (all one cluster, or all singletons)
        return 1.0
    return float((index - expected) / (maximum - expected))


def t_interval(values, conf=0.95):
    v = np.asarray(values, dtype=float)
    m = float(v.mean())
    if len(v) < 2:
        return {"mean": m, "lo": None, "hi": None, "sd": None, "n": len(v)}
    sd = float(v.std(ddof=1))
    h = float(stats.t.ppf(0.5 + conf / 2, len(v) - 1) * sd / np.sqrt(len(v)))
    return {"mean": m, "lo": m - h, "hi": m + h, "sd": sd, "n": len(v)}


def subsample_ari(a, b, n_rep=1000, seed=0, conf=0.95, frac=0.5):
    """Percentile interval of ARI over random subsamples of the items, without replacement."""
    rng = np.random.default_rng(seed)
    a, b = np.asarray(a), np.asarray(b)
    m = max(2, int(frac * len(a)))
    reps = [ari(a[idx], b[idx]) for idx in (rng.choice(len(a), m, replace=False) for _ in range(n_rep))]
    q = (1 - conf) / 2
    return float(np.quantile(reps, q)), float(np.quantile(reps, 1 - q))


def largest_share(groups, nodes=None):
    sizes = [len(m if nodes is None else m & nodes) for m in groups.values()]
    return max(sizes) / sum(sizes)


def permutation_p(a, b, n_perm=999, seed=0):
    rng = np.random.default_rng(seed)
    obs = ari(a, b)
    b = np.asarray(b)
    hits = sum(ari(a, rng.permutation(b)) >= obs for _ in range(n_perm))
    return (1 + hits) / (n_perm + 1)


def labels(groups, nodes):
    """Label array for `nodes` from {key: set(members)}."""
    where = {n: k for k, m in groups.items() for n in m}
    return [where[n] for n in nodes]


# ---------------------------------------------------------------- the two T6 stability measures

def remove_edges(tkh, frac, seed, cutoffs=None, relations=None):
    """Remove round(frac * n) edges, per publication period if cutoffs are given (else globally),
    drawn from the edges of `relations` only (None: all edges)."""
    rng = random.Random(seed)
    pool = tkh.edges if relations is None else tkh.edges[tkh.edges["relation_type"].isin(relations)]
    years = pool["article_year"]
    if cutoffs:
        bounds = [-10 ** 9] + sorted(cutoffs)
        strata = [list(years.index[(years > lo) & (years <= hi)]) for lo, hi in zip(bounds, bounds[1:])]
        strata.append(list(years.index[years > bounds[-1]]))
    else:
        strata = [list(years.index)]
    drop = [e for ids in strata for e in rng.sample(ids, round(frac * len(ids)))]
    return replace(tkh, edges=tkh.edges.drop(index=drop)), drop


def _scored_nodes(tkh, cutoff, node_types):
    from tkh.io import snapshot
    ids = snapshot(tkh, cutoff).node_ids
    return sorted(ids if node_types is None else (n for n in ids if tkh.nodes.at[n, "type"] in node_types))


def perturbation_stability(tkh, build, cutoffs, frac=0.10, seeds=(0, 1, 2, 3, 4), base=None,
                           relations=CLUSTER_RELATIONS, node_types=CONCEPT_TYPES):
    """Rows: snapshot, level, seed, ari, n_nodes; plus summaries with t-intervals per (snapshot, level)."""
    base = base if base is not None else build(tkh)
    pool = tkh.edges if relations is None else tkh.edges[tkh.edges["relation_type"].isin(relations)]
    variant = "all_edges" if relations is None else "clustering_relations"
    rows = []
    for seed in seeds:
        pert, dropped = remove_edges(tkh, frac, seed, cutoffs, relations)
        rebuilt = build(pert)
        for c in cutoffs:
            snap_edges = int((pool["article_year"] <= c).sum())
            removed = int((tkh.edges.loc[dropped, "article_year"] <= c).sum())
            nodes = _scored_nodes(tkh, c, node_types)
            ns = set(nodes)
            for k, (g0, g1) in enumerate(zip(base[c], rebuilt[c])):
                rows.append({"snapshot": c, "level": k, "seed": seed, "variant": variant, "edges_removed": removed,
                             "share_removed": removed / snap_edges if snap_edges else 0.0, "n_nodes": len(nodes),
                             "largest_share_base": largest_share(g0, ns), "largest_share_rebuilt": largest_share(g1, ns),
                             "ari": ari(labels(g0, nodes), labels(g1, nodes))})
    summary = []
    for c in cutoffs:
        for k in sorted({r["level"] for r in rows}):
            v = [r["ari"] for r in rows if r["snapshot"] == c and r["level"] == k]
            sel = [r for r in rows if r["snapshot"] == c and r["level"] == k]
            summary.append({"snapshot": c, "level": k, "variant": variant, **t_interval(v), "min": min(v), "max": max(v),
                            "largest_share_base": sel[0]["largest_share_base"],
                            "share_removed": float(np.mean([r["share_removed"] for r in sel]))})
    return rows, summary


def cross_snapshot_stability(partitions, cutoffs, n_boot=1000, n_perm=999, seed=0, nodes=None):
    """Rows per (transition, level): n_common, ari, 95% subsample interval, permutation p, largest shares.
    nodes: optional set restricting the scored nodes (e.g. concept nodes)."""
    rows = []
    for t0, t1 in zip(cutoffs, cutoffs[1:]):
        for k, (g0, g1) in enumerate(zip(partitions[t0], partitions[t1])):
            common = sorted({n for m in g0.values() for n in m} & {n for m in g1.values() for n in m})
            if nodes is not None:
                common = [n for n in common if n in nodes]
            a, b = labels(g0, common), labels(g1, common)
            lo, hi = subsample_ari(a, b, n_boot, seed)
            cs = set(common)
            rows.append({"from": t0, "to": t1, "level": k, "n_common": len(common), "ari": ari(a, b),
                         "sub_lo": lo, "sub_hi": hi, "p_vs_random_labels": permutation_p(a, b, n_perm, seed + 1),
                         "largest_share_from": largest_share(g0, cs), "largest_share_to": largest_share(g1, cs)})
    return rows


def _reassignment(g0, g1, common):
    """1 - Jaccard of each node's co-members (restricted to `common`) in g0 and g1."""
    cs = set(common)
    w0 = {n: k for k, m in g0.items() for n in m}
    w1 = {n: k for k, m in g1.items() for n in m}
    m0 = {k: m & cs for k, m in g0.items()}
    m1 = {k: m & cs for k, m in g1.items()}
    out = []
    for v in common:
        a, b = m0[w0[v]] - {v}, m1[w1[v]] - {v}
        u = len(a | b)
        out.append(0.0 if u == 0 else 1.0 - len(a & b) / u)
    return np.array(out)


def touched_nodes(tkh, t0, t1, relations=CLUSTER_RELATIONS):
    """Nodes that are members of a clustering edge that enters the graph between t0 and t1."""
    e = tkh.edges
    new = e[(e["article_year"] > t0) & (e["article_year"] <= t1) & e["relation_type"].isin(relations)]
    return {v for m in new["members"] for v in m}


def change_localisation(tkh, partitions, cutoffs, node_types=CONCEPT_TYPES, relations=CLUSTER_RELATIONS,
                        n_perm=999, seed=0):
    """Rows per (transition, level): mean reassignment of touched / untouched old nodes, ratio, permutation p."""
    rng = np.random.default_rng(seed)
    rows = []
    for t0, t1 in zip(cutoffs, cutoffs[1:]):
        touched = touched_nodes(tkh, t0, t1, relations)
        for k, (g0, g1) in enumerate(zip(partitions[t0], partitions[t1])):
            common = sorted({n for m in g0.values() for n in m} & {n for m in g1.values() for n in m})
            if node_types is not None:
                common = [n for n in common if tkh.nodes.at[n, "type"] in node_types]
            r = _reassignment(g0, g1, common)
            is_t = np.array([n in touched for n in common])
            mt, mu = (float(r[is_t].mean()) if is_t.any() else None), (float(r[~is_t].mean()) if (~is_t).any() else None)
            ratio = mt / mu if mt is not None and mu else None
            p = None
            if ratio is not None:
                obs = mt - mu
                diffs = []
                for _ in range(n_perm):
                    s = rng.permutation(is_t)
                    diffs.append(r[s].mean() - r[~s].mean())
                p = float((1 + sum(d >= obs for d in diffs)) / (n_perm + 1))
            rows.append({"from": t0, "to": t1, "level": k, "n_old": len(common), "n_touched": int(is_t.sum()),
                         "reassign_touched": mt, "reassign_untouched": mu, "reassign_all": float(r.mean()) if len(r) else None,
                         "ratio": ratio, "p_ratio_gt_1": p})
    return rows


def read_partitions(out_dir, cutoffs):
    """{cutoff: [ {id: set(members)} per level ]} from written hierarchy.json files."""
    parts = {}
    for c in cutoffs:
        h = json.loads((Path(out_dir) / str(c) / "hierarchy.json").read_text())
        parts[c] = [{s["id"]: set(s["member_ids"]) for s in h["supernodes"] if s["level"] == k}
                    for k in range(h["levels"])]
    return parts


def pool_over_runs(per_run_rows, keys, value="ari"):
    """t-interval across independent runs (e.g. seeds) of one value per run and key."""
    out = {}
    for rows in per_run_rows:
        for r in rows:
            out.setdefault(tuple(r[k] for k in keys), []).append(r[value])
    return [{**dict(zip(keys, key)), **t_interval(v), "values": v} for key, v in sorted(out.items())]
