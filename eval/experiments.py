"""The held-out coherence check of one run against the nulls, and the worker pool that rebuilds hierarchies for it.

coherence_check: for every snapshot and level of a run (its hierarchy.json), the unadjusted lift and the
  period-adjusted lift under every period scheme (eval/coherence.py; "interval" is primary), under the exact and the fuzzy
  residual filter, with paper-bootstrap CIs, against R configuration-null
  rebuilds at that cutoff (same parameters, real hub sets) and R_labels random-label permutations of the run's tree.
The α sweep is in eval/sweep.py.
"""

from concurrent.futures import ProcessPoolExecutor
from pathlib import Path
import json
import math
import os

from tkh.coarsen import hubs
from tkh.hierarchy import Params, build_concept
from tkh.io import load, snapshot
from tkh.null import label_permutation, null_tkh
from eval.coherence import PERIODS, Ruler, null_summary

_W = {}


def _init(cfg):
    _W["cfg"], _W["tkh"] = cfg, load(cfg)
    _W["raw"] = json.loads(Path(cfg.graph).read_text())


def _levels(job):
    """Concept partitions for (params dict, null seed or None, cutoffs or None = the last cutoff only), built as one
    chain over all cutoffs (the temporal prior couples them) with the real snapshots' hub sets: a list of levels for
    the last cutoff, or {cutoff: levels} when cutoffs are given."""
    pdict, seed, cutoffs = (*job, None)[:3]
    cfg, real = _W["cfg"], _W["tkh"]
    params = Params.from_config(pdict)
    tkh = real if seed is None else null_tkh(_W["raw"], cfg.articles, cfg.cutoffs, seed)[0]
    built = build_concept(tkh, cfg.cutoffs, cfg.budgets, params, real_hubs(real, cfg, params))
    return built[max(cfg.cutoffs)][0] if cutoffs is None else {c: built[c][0] for c in cutoffs}


def real_hubs(tkh, cfg, params):
    return {c: hubs(tkh, snapshot(tkh, c), params.hub_frac) for c in cfg.cutoffs}


def _pool(cfg, jobs, n_jobs, fn=None):
    """Run fn (default _levels) over jobs in worker processes that hold the config, the real TKH and the raw export."""
    for v in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "VECLIB_MAXIMUM_THREADS"):
        os.environ.setdefault(v, "1")   # one BLAS thread per worker process (read by the spawned workers)
    with ProcessPoolExecutor(n_jobs, initializer=_init, initargs=(cfg,)) as ex:
        return list(ex.map(fn or _levels, jobs))


def _concept_levels(hierarchy):
    K = hierarchy["levels"]
    return [{s["id"]: set(s["member_ids"]) for s in hierarchy["supernodes"] if s["level"] == k} for k in range(K)]


def coherence_check(cfg, params, run_dir, R=99, R_labels=999, n_jobs=8):
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
