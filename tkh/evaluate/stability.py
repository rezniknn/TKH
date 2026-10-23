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

def remove_edges(tkh, frac, seed, cutoffs=None):
    """Remove round(frac * n) edges, per publication period if cutoffs are given (else globally)."""
    rng = random.Random(seed)
    years = tkh.edges["article_year"]
    if cutoffs:
        bounds = [-10 ** 9] + sorted(cutoffs)
        strata = [list(years.index[(years > lo) & (years <= hi)]) for lo, hi in zip(bounds, bounds[1:])]
        strata.append(list(years.index[years > bounds[-1]]))
    else:
        strata = [list(years.index)]
    drop = [e for ids in strata for e in rng.sample(ids, round(frac * len(ids)))]
    return replace(tkh, edges=tkh.edges.drop(index=drop)), drop


def perturbation_stability(tkh, build, cutoffs, frac=0.10, seeds=(0, 1, 2, 3, 4), base=None):
    """Rows: snapshot, level, seed, ari, n_nodes; plus summaries with t-intervals per (snapshot, level)."""
    from tkh.io import snapshot
    base = base if base is not None else build(tkh)
    rows = []
    for seed in seeds:
        pert, dropped = remove_edges(tkh, frac, seed, cutoffs)
        rebuilt = build(pert)
        for c in cutoffs:
            snap_edges = int((tkh.edges["article_year"] <= c).sum())
            removed = int((tkh.edges.loc[dropped, "article_year"] <= c).sum())
            nodes = sorted(snapshot(tkh, c).node_ids)
            for k, (g0, g1) in enumerate(zip(base[c], rebuilt[c])):
                rows.append({"snapshot": c, "level": k, "seed": seed, "edges_removed": removed,
                             "share_removed": removed / snap_edges, "n_nodes": len(nodes),
                             "largest_share_base": largest_share(g0), "largest_share_rebuilt": largest_share(g1),
                             "ari": ari(labels(g0, nodes), labels(g1, nodes))})
    summary = []
    for c in cutoffs:
        for k in sorted({r["level"] for r in rows}):
            v = [r["ari"] for r in rows if r["snapshot"] == c and r["level"] == k]
            sel = [r for r in rows if r["snapshot"] == c and r["level"] == k]
            summary.append({"snapshot": c, "level": k, **t_interval(v), "min": min(v), "max": max(v),
                            "largest_share_base": sel[0]["largest_share_base"],
                            "share_removed": float(np.mean([r["share_removed"] for r in sel]))})
    return rows, summary


def cross_snapshot_stability(partitions, cutoffs, n_boot=1000, n_perm=999, seed=0):
    """Rows per (transition, level): n_common, ari, 95% subsample interval, permutation p, largest shares."""
    rows = []
    for t0, t1 in zip(cutoffs, cutoffs[1:]):
        for k, (g0, g1) in enumerate(zip(partitions[t0], partitions[t1])):
            common = sorted({n for m in g0.values() for n in m} & {n for m in g1.values() for n in m})
            a, b = labels(g0, common), labels(g1, common)
            lo, hi = subsample_ari(a, b, n_boot, seed)
            cs = set(common)
            rows.append({"from": t0, "to": t1, "level": k, "n_common": len(common), "ari": ari(a, b),
                         "sub_lo": lo, "sub_hi": hi, "p_vs_random_labels": permutation_p(a, b, n_perm, seed + 1),
                         "largest_share_from": largest_share(g0, cs), "largest_share_to": largest_share(g1, cs)})
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
