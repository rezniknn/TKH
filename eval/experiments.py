"""Experiments on the last snapshot: the held-out P3 check of one run against the nulls, and the configuration sweep.

p3_check: for every snapshot and level of a run (its hierarchy.json), the unadjusted lift and the
  period-adjusted lift under every period scheme (eval/p3.py; "interval" is primary), under the exact and the fuzzy
  residual filter, with paper-bootstrap CIs, against R configuration-null
  rebuilds at that cutoff (same parameters, real hub sets) and R_labels random-label permutations of the run's tree.
sweep: every configuration of a grid is built once; over `splits` seeded halves (A, B) of the cited works,
  each split selects on half A by the one-SE rule (criterion: mean lift over levels; SE: paper bootstrap;
  among configurations within one SE of the best, the one closest to the default, compared parameter by
  parameter in the order alpha, rho, edge_weight, hub_frac) and reports that choice on half B. The base
  configuration is the run's [method] (with --param overrides).
"""

from concurrent.futures import ProcessPoolExecutor
from collections import Counter
from itertools import product
from pathlib import Path
import json
import math
import os

import numpy as np

from tkh.coarsen import hubs
from tkh.hierarchy import Params, build_snapshot
from tkh.io import load, snapshot
from tkh.null import label_permutation, null_tkh
from eval.p3 import PERIODS, Ruler, null_summary, split_works

_W = {}


def _init(cfg):
    _W["cfg"], _W["tkh"] = cfg, load(cfg)
    _W["raw"] = json.loads(Path(cfg.graph).read_text())


def _levels(job):
    """Concept partitions for (params dict, null seed or None, cutoffs or None = the last cutoff only):
    a list of levels for one cutoff, or {cutoff: levels} when cutoffs are given (one null graph per seed)."""
    pdict, seed, cutoffs = (*job, None)[:3]
    cfg, real = _W["cfg"], _W["tkh"]
    params = Params.from_config(pdict)
    tkh = real if seed is None else null_tkh(_W["raw"], cfg.articles, cfg.cutoffs, seed)[0]
    one = lambda c: build_snapshot(tkh, snapshot(tkh, c), cfg.budgets, params, hubs(real, snapshot(real, c), params.hub_frac))[0]  # noqa: E731
    return one(max(cfg.cutoffs)) if cutoffs is None else {c: one(c) for c in cutoffs}


def _pool(cfg, jobs, n_jobs):
    for v in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "VECLIB_MAXIMUM_THREADS"):
        os.environ.setdefault(v, "1")   # one BLAS thread per worker process (read by the spawned workers)
    with ProcessPoolExecutor(n_jobs, initializer=_init, initargs=(cfg,)) as ex:
        return list(ex.map(_levels, jobs))


def _concept_levels(hierarchy):
    K = hierarchy["levels"]
    return [{s["id"]: set(s["member_ids"]) for s in hierarchy["supernodes"] if s["level"] == k} for k in range(K)]


def p3_check(cfg, params, run_dir, R=99, R_labels=999, n_jobs=8):
    """Per snapshot and level: unadjusted and period-adjusted lifts (every period scheme; "interval" primary),
    under the exact and the fuzzy residual filter, vs both nulls."""
    tkh = load(cfg)
    cutoffs = sorted(cfg.cutoffs)
    nulls = _pool(cfg, [(params.as_dict(), s, cutoffs) for s in range(R)], n_jobs) if R else []
    out = {"params": params.as_dict(), "budgets": list(cfg.budgets), "primary": "interval", "periods": list(PERIODS),
           "R": R, "R_labels": R_labels, "p": "one-sided, (1 + #null >= obs) / (R + 1)", "snapshots": {}}
    for c in cutoffs:
        snap = snapshot(tkh, c)
        levels = _concept_levels(json.loads((Path(run_dir) / str(c) / "hierarchy.json").read_text()))
        perms = [label_permutation(tkh, snap, cfg.cutoffs, s) for s in range(R_labels)]
        rows = [{"level": k, "super_nodes": len(lv)} for k, lv in enumerate(levels)]
        coverage = {}
        for f in ("exact", "fuzzy"):
            rulers = {p: Ruler(tkh, snap, fuzzy=f == "fuzzy", cutoffs=cutoffs, period=p) for p in PERIODS}
            ru = rulers["interval"]   # pairs, coupling and co-assignment do not depend on the period scheme
            coverage[f] = ru.coverage()
            idx = {v: i for i, v in enumerate(ru.nodes)}
            moves = [tuple(map(list, zip(*((idx[v], idx[u]) for v, u in pm.items())))) for pm in perms]
            for k, lv in enumerate(levels):
                g = ru.labels(lv)
                a = ru.coassign(g=g)
                rand = []
                for src, dst in moves:   # node perm[v] takes v's super-node: g'[idx[perm[v]]] = g[idx[v]]
                    gp = g.copy()
                    gp[dst] = g[src]
                    rand.append(ru.coassign(g=gp))
                conf = [ru.coassign(n[c][k]) for n in nulls]
                res = {}
                for mode in ("unadjusted",) + PERIODS:
                    r_, adj = rulers["interval" if mode == "unadjusted" else mode], mode != "unadjusted"
                    obs = r_.lift(a, adjusted=adj)
                    se, lo, hi, nb = r_.bootstrap(a, adjusted=adj)
                    res[mode] = {"lift": obs, "ci95": [lo, hi], "se": se, "bootstrap_defined": nb,
                                 "configuration_null": null_summary(obs, [r_.lift(x, adjusted=adj) for x in conf]),
                                 "random_labels": null_summary(obs, [r_.lift(x, adjusted=adj) for x in rand])}
                rows[k][f] = res
        out["snapshots"][str(c)] = {"coverage": coverage, "levels": rows}
    return _finite(out)


def _finite(x):
    """NaN/inf -> None, so that metrics.json is strict JSON."""
    if isinstance(x, dict):
        return {k: _finite(v) for k, v in x.items()}
    if isinstance(x, list):
        return [_finite(v) for v in x]
    return None if isinstance(x, float) and not math.isfinite(x) else x


GRID = {"alpha": [0.25, 0.5, 0.75], "rho": [2.0, 4.0], "edge_weight": ["inverse_size", "relation_balanced"],
        "hub_frac": [0.1, 0.15, 0.2, 0.3, 1.0]}
ABLATIONS = [{"alpha": 0.0}, {"alpha": 1.0}]


def _distance(p, base):
    """How far configuration p is from the base, compared parameter by parameter (alpha, rho, edge_weight, hub_frac)."""
    p = Params.from_config(p)
    return (abs(p.alpha - base.alpha), abs(p.rho - base.rho) if p.rho != base.rho else 0.0,
            p.edge_weight != base.edge_weight, abs(p.hub_frac - base.hub_frac))


def sweep(cfg, base, grid=GRID, splits=20, n_jobs=8, n_boot=200):
    """Grid around `base` (the configured parameters, also the one-SE fallback and the reported default)."""
    tkh = load(cfg)
    snap = snapshot(tkh, max(cfg.cutoffs))
    configs = [{**base.as_dict(), **dict(zip(grid, v))} for v in product(*grid.values())]
    configs += [{**base.as_dict(), **a} for a in ABLATIONS]
    configs = [Params.from_config(c).as_dict() for c in configs]
    levels = _pool(cfg, [(c, None) for c in configs], n_jobs)
    selectable = len(configs) - len(ABLATIONS)
    base_i = configs.index(base.as_dict()) if base.as_dict() in configs else None
    picks, table = [], []
    for s in range(splits):
        A, B = split_works(tkh, snap, s)
        ra, rb = Ruler(tkh, snap, A), Ruler(tkh, snap, B)
        boot = _boot_weights(len(ra.papers), n_boot, s)
        crit = []
        for lv in levels:   # criterion: mean lift over levels; SE: paper bootstrap on half A
            aa, ab = [ra.coassign(x) for x in lv], [rb.coassign(x) for x in lv]
            draws = np.array([np.mean([ra.lift(a, w) for a in aa]) for w in boot])   # nan if a draw has no pairs
            crit.append({"A": float(np.mean([ra.lift(a) for a in aa])), "se_A": float(np.nanstd(draws, ddof=1)),
                         "B": float(np.mean([rb.lift(a) for a in ab]))})
        best = max((i for i in range(selectable) if np.isfinite(crit[i]["A"])), key=lambda i: crit[i]["A"])
        within = [i for i in range(selectable) if crit[i]["A"] >= crit[best]["A"] - crit[best]["se_A"]]
        pick = min(within, key=lambda i: _distance(configs[i], base))
        picks.append(pick)
        table.append({"split": s, "best": best, "pick": pick, "n_within_1se": len(within),
                      "base_B": crit[base_i]["B"] if base_i is not None else None, "per_config": crit})
    modal, n_modal = Counter(picks).most_common(1)[0]
    return {"snapshot": snap.cutoff, "budgets": list(cfg.budgets), "base": base.as_dict(), "configs": configs,
            "n_selectable": selectable, "splits": table, "selected": configs[modal], "selected_share": n_modal / splits}


def _boot_weights(n, B, seed):
    rng = np.random.default_rng(1000 + seed)
    return [np.bincount(rng.integers(0, n, n), minlength=n).astype(float) for _ in range(B)]
