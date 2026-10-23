"""Experiments on the last snapshot: the held-out P3 check of one run against the nulls, and the configuration sweep.

p3_check: lift per level of a run (its hierarchy.json) under the exact and the fuzzy residual filter, with
  paper-bootstrap CIs, against R configuration-null rebuilds (same parameters, real hub sets) and R_labels
  random-label permutations of the run's own tree.
sweep: every configuration of a grid is built once; over `splits` seeded halves (A, B) of the cited works,
  each split selects on half A by the one-SE rule (criterion: mean lift over levels; SE: paper bootstrap;
  among configurations within one SE of the best, the one closest to the default, compared parameter by
  parameter in the order alpha, rho, edge_weight, hub_frac) and reports that choice on half B.
"""

from concurrent.futures import ProcessPoolExecutor
from collections import Counter
from itertools import product
from pathlib import Path
import json
import os

import numpy as np

from tkh.coarsen import hubs
from tkh.hierarchy import Params, build_snapshot
from tkh.io import load, snapshot
from tkh.null import label_permutation, null_tkh
from tkh.p3 import Ruler, null_summary, split_works

_W = {}


def _init(cfg):
    _W["cfg"], _W["tkh"] = cfg, load(cfg)
    _W["raw"] = json.loads(Path(cfg.graph).read_text())


def _levels(job):
    """Concept partitions at the last cutoff for (params dict, null seed or None)."""
    pdict, seed = job
    cfg, real = _W["cfg"], _W["tkh"]
    params, c = Params.from_config(pdict), max(cfg.cutoffs)
    hubset = hubs(real, snapshot(real, c), params.hub_frac)
    tkh = real if seed is None else null_tkh(_W["raw"], cfg.articles, cfg.cutoffs, seed)[0]
    return build_snapshot(tkh, snapshot(tkh, c), cfg.budgets, params, hubset)[0]


def _pool(cfg, jobs, n_jobs):
    for v in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "VECLIB_MAXIMUM_THREADS"):
        os.environ.setdefault(v, "1")   # one BLAS thread per worker process (read by the spawned workers)
    with ProcessPoolExecutor(n_jobs, initializer=_init, initargs=(cfg,)) as ex:
        return list(ex.map(_levels, jobs))


def _concept_levels(hierarchy):
    K = hierarchy["levels"]
    return [{s["id"]: set(s["member_ids"]) for s in hierarchy["supernodes"] if s["level"] == k} for k in range(K)]


def p3_check(cfg, params, run_dir, R=99, R_labels=999, n_jobs=8):
    tkh = load(cfg)
    c = max(cfg.cutoffs)
    snap = snapshot(tkh, c)
    levels = _concept_levels(json.loads((Path(run_dir) / str(c) / "hierarchy.json").read_text()))
    rulers = {f: Ruler(tkh, snap, fuzzy=f == "fuzzy") for f in ("exact", "fuzzy")}
    nulls = _pool(cfg, [(params.as_dict(), s) for s in range(R)], n_jobs) if R else []
    out = {"snapshot": c, "params": params.as_dict(), "budgets": list(cfg.budgets), "levels": []}
    perms = [label_permutation(tkh, snap, cfg.cutoffs, s) for s in range(R_labels)]
    for k, lv in enumerate(levels):
        row = {"level": k, "super_nodes": len(lv)}
        for f, ru in rulers.items():
            g = ru.labels(lv)
            a = ru.coassign(g=g)
            obs = ru.lift(a)
            se, lo, hi = ru.bootstrap(a)
            idx = {v: i for i, v in enumerate(ru.nodes)}
            # node perm[v] takes v's super-node: g'[idx[perm[v]]] = g[idx[v]]
            rl = []
            for pm in perms:
                src, dst = zip(*((idx[v], idx[u]) for v, u in pm.items()))
                gp = g.copy()
                gp[list(dst)] = g[list(src)]
                rl.append(ru.lift(ru.coassign(g=gp)))
            row[f] = {"lift": obs, "ci95": [lo, hi], "se": se,
                      "configuration_null": null_summary(obs, [ru.lift(ru.coassign(n[k])) for n in nulls]),
                      "random_labels": null_summary(obs, rl)}
        out["levels"].append(row)
    out["coverage"] = {f: ru.coverage() for f, ru in rulers.items()}
    return out


DEFAULT = Params()
GRID = {"alpha": [0.25, 0.5, 0.75], "rho": [2.0, 4.0], "edge_weight": ["inverse_size", "relation_balanced"],
        "hub_frac": [0.1, 0.15, 0.2, 0.3, 1.0]}
ABLATIONS = [{"alpha": 0.0}, {"alpha": 1.0}]


def _distance(p):
    return (abs(p["alpha"] - DEFAULT.alpha), abs(p["rho"] - DEFAULT.rho), p["edge_weight"] != DEFAULT.edge_weight,
            abs(p["hub_frac"] - DEFAULT.hub_frac))


def sweep(cfg, grid=GRID, splits=20, n_jobs=8, B=200):
    tkh = load(cfg)
    snap = snapshot(tkh, max(cfg.cutoffs))
    configs = [dict(zip(grid, v)) for v in product(*grid.values())]
    configs += [{**DEFAULT.as_dict(), **a} for a in ABLATIONS]
    configs = [Params.from_config({**DEFAULT.as_dict(), **c}).as_dict() for c in configs]
    levels = _pool(cfg, [(c, None) for c in configs], n_jobs)
    selectable = len(configs) - len(ABLATIONS)
    picks, table = [], []
    for s in range(splits):
        A, Bw = split_works(tkh, snap, s)
        ra, rb = Ruler(tkh, snap, A), Ruler(tkh, snap, Bw)
        crit = []
        for lv in levels:
            aa = [ra.coassign(x) for x in lv]
            vals = [np.mean([ra.lift(a, w) for a in aa]) for w in [None] + _boot_weights(len(ra.papers), B, s)]
            ab = [rb.coassign(x) for x in lv]
            crit.append((vals[0], float(np.std(vals[1:], ddof=1)), float(np.mean([rb.lift(a) for a in ab]))))
        best = max(range(selectable), key=lambda i: crit[i][0])
        within = [i for i in range(selectable) if crit[i][0] >= crit[best][0] - crit[best][1]]
        pick = min(within, key=lambda i: _distance(configs[i]))
        picks.append(pick)
        table.append({"split": s, "best": best, "pick": pick, "pick_A": crit[pick][0], "pick_B": crit[pick][2],
                      "default_B": crit[configs.index(DEFAULT.as_dict())][2] if DEFAULT.as_dict() in configs else None,
                      "per_config": [{"A": a, "se_A": se, "B": b} for a, se, b in crit]})
    modal, n_modal = Counter(picks).most_common(1)[0]
    return {"snapshot": snap.cutoff, "budgets": list(cfg.budgets), "configs": configs, "n_selectable": selectable,
            "splits": table, "selected": configs[modal], "selected_share": n_modal / splits,
            "selected_B": [t["pick_B"] for t in table]}


def _boot_weights(n, B, seed):
    rng = np.random.default_rng(1000 + seed)
    return [np.bincount(rng.integers(0, n, n), minlength=n).astype(float) for _ in range(B)]
