"""T6 stability of a SHAC run: perturbation stability, real cross-snapshot stability with a null, change localisation.

All scores are on concept nodes (anchored nodes follow their anchor and would inflate agreement).

  ARI     adjusted Rand index of two partitions of the same nodes, per level (0 = chance, 1 = identical)
  HARI    level-pooled laminar analogue: sum_k (I_k - E_k) / sum_k (M_k - E_k) over the levels, with the per-level
          pair-counting terms of ARI (index, expected, maximum); 1 for identical trees, expectation 0 under a node
          permutation applied at all levels. Levels weigh by their pair mass M_k - E_k, so the coarsest level
          dominates (about 75% at the default budgets); the per-level ARIs are reported next to it

1. Perturbation (the brief's protocol): remove 10% of all hyper-edges, stratified by period and relation, for seeds
   0-4; rebuild the whole chain with the run's parameters; ARI per snapshot and level and HARI per snapshot against
   the unperturbed run; mean and t-interval over the seeds.
2. Cross-snapshot: per transition t-1 -> t, ARI per level and HARI on the concept nodes present in both, with a
   percentile interval over half-subsamples of the nodes, against a random-attachment null (tkh/null.attachment_null):
   the new papers keep their edges, but every old endpoint is redrawn among the old nodes of its type in proportion
   to their degree, so a random set of old nodes is touched; snapshot t is then rebuilt from the real t-1 hierarchy.
   p = (1 + #null >= obs) / (R + 1): is the observed persistence more than random attachment would leave?
3. Change localisation: per transition and level, the reassignment rate (1 - Jaccard of a node's old co-members) of
   old concept nodes that new papers touch (members of any edge of a new paper, any relation) vs untouched ones,
   their ratio and a node-bootstrap interval. Good: change concentrated on touched nodes (P5).
4. Events: counts per transition, level and type from temporal_events.json (deaths cannot occur: snapshots only grow).
"""

from collections import Counter
from dataclasses import replace
from pathlib import Path
import bisect
import json
import random

import numpy as np
from scipy import stats
from sklearn.metrics import adjusted_rand_score

from eval.experiments import _W, _concept_levels, _finite, _pool, real_hubs
from eval.coherence import null_summary
from tkh.coarsen import concept_nodes
from tkh.hierarchy import Params, build_concept, build_snapshot, stable_nodes
from tkh.io import load, snapshot
from tkh.null import attachment_null


# ---------------------------------------------------------------- agreement

def _labels(level, nodes):
    where = {v: g for g, mem in level.items() for v in mem}
    return [where[v] for v in nodes]


def _terms(a, b):
    _, ai = np.unique(np.asarray(a), return_inverse=True)
    _, bi = np.unique(np.asarray(b), return_inverse=True)
    c2 = lambda x: x * (x - 1) / 2.0  # noqa: E731
    cont = np.bincount(ai * (bi.max() + 1) + bi).astype(float)
    sa, sb, total = c2(np.bincount(ai).astype(float)).sum(), c2(np.bincount(bi).astype(float)).sum(), c2(len(ai))
    return c2(cont).sum(), (sa * sb / total if total else 0.0), (sa + sb) / 2.0


def hari(levels_a, levels_b, nodes):
    """Level-pooled ARI of two hierarchies over `nodes` (present in both)."""
    num = den = 0.0
    for ga, gb in zip(levels_a, levels_b):
        i, e, mx = _terms(_labels(ga, nodes), _labels(gb, nodes))
        num, den = num + i - e, den + mx - e
    return float(num / den) if den else 1.0


def agreement(levels_a, levels_b, nodes):
    """(ARI per level, HARI) of two hierarchies on `nodes`."""
    return [float(adjusted_rand_score(_labels(a, nodes), _labels(b, nodes))) for a, b in zip(levels_a, levels_b)], \
        hari(levels_a, levels_b, nodes)


def t_interval(values, conf=0.95):
    v = np.asarray(values, dtype=float)
    if len(v) < 2:
        return {"mean": float(v.mean()) if len(v) else None, "lo": None, "hi": None, "n": len(v)}
    h = float(stats.t.ppf(0.5 + conf / 2, len(v) - 1) * v.std(ddof=1) / np.sqrt(len(v)))
    return {"mean": float(v.mean()), "lo": float(v.mean() - h), "hi": float(v.mean() + h), "n": len(v)}


def _subsample(levels_a, levels_b, nodes, n_rep=200, seed=0):
    """Percentile intervals of ARI per level and HARI over random half-subsamples of the nodes."""
    rng = np.random.default_rng(seed)
    nodes = np.asarray(nodes)
    reps = [agreement(levels_a, levels_b, list(rng.choice(nodes, len(nodes) // 2, replace=False))) for _ in range(n_rep)]
    q = lambda x: [float(np.percentile(x, 2.5)), float(np.percentile(x, 97.5))]  # noqa: E731
    return [q([r[0][k] for r in reps]) for k in range(len(levels_a))], q([r[1] for r in reps])


# ---------------------------------------------------------------- perturbation

def remove_edges(tkh, frac, seed, cutoffs):
    """tkh without round(frac * n) randomly chosen hyper-edges of each (publication period, relation) stratum, so
    every seed removes 10% of all hyper-edges and 10% of each relation in every period. Node entry years are kept,
    so every snapshot keeps its node set."""
    rng = random.Random(seed)
    period = tkh.edges["article_year"].map(lambda y: bisect.bisect_left(sorted(cutoffs), y))
    strata = tkh.edges.groupby([period, tkh.edges["relation_type"]]).groups
    drop = [e for key in sorted(strata) for e in rng.sample(sorted(strata[key]), round(frac * len(strata[key])))]
    return replace(tkh, edges=tkh.edges.drop(index=drop)), drop


def _perturbed(job):
    pdict, seed, frac = job
    cfg, tkh = _W["cfg"], _W["tkh"]
    pert, _ = remove_edges(tkh, frac, seed, cfg.cutoffs)
    return {c: lv for c, (lv, _, _) in build_concept(pert, cfg.cutoffs, cfg.budgets, Params.from_config(pdict)).items()}


def _new_paper_null(job):
    """Snapshot c1 rebuilt from the real hierarchy at c0 on a graph whose (c0, c1] edges attach to random old nodes."""
    pdict, seed, c0, c1, prev_levels = job
    cfg, real = _W["cfg"], _W["tkh"]
    params = Params.from_config(pdict)
    tkh = attachment_null(real, c0, c1, seed)
    rh = real_hubs(real, cfg, params)
    s0, s1 = snapshot(tkh, c0), snapshot(tkh, c1)
    stable = stable_nodes(tkh, s0, s1, set(rh[c0]), rh[c1])
    return build_snapshot(tkh, s1, cfg.budgets, params, rh[c1], prev_levels, stable)[0]


# ---------------------------------------------------------------- the check

def stability_check(cfg, params, run_dir, seeds=range(5), frac=0.10, R=99, n_sub=200, n_jobs=8):
    tkh = load(cfg)
    cs = sorted(cfg.cutoffs)
    concept = {c: set(concept_nodes(tkh, snapshot(tkh, c))) for c in cs}
    run = {c: [{g: m & concept[c] for g, m in lv.items()}
               for lv in _concept_levels(json.loads((Path(run_dir) / str(c) / "hierarchy.json").read_text()))] for c in cs}
    K = len(run[cs[0]])
    pd = params.as_dict()
    jobs_p = [(pd, s, frac) for s in seeds]
    jobs_n = [(pd, s, c0, c1, run[c0]) for c0, c1 in zip(cs, cs[1:]) for s in range(R)]
    pert = _pool(cfg, jobs_p, n_jobs, _perturbed)
    nulls = _pool(cfg, jobs_n, n_jobs, _new_paper_null) if R else []

    out = {"params": pd, "budgets": list(cfg.budgets), "perturbation": {}, "cross_snapshot": {}, "localisation": {},
           "events": _events(run_dir), "protocol": {"frac": frac, "seeds": list(seeds), "R": R, "n_sub": n_sub}}
    for c in cs:   # 1. perturbation
        nodes = sorted(concept[c])
        per = [agreement(run[c], p[c], nodes) for p in pert]
        out["perturbation"][str(c)] = {"ari": [t_interval([a[0][k] for a in per]) for k in range(K)],
                                       "hari": t_interval([a[1] for a in per]), "per_seed_hari": [a[1] for a in per]}
    for i, (c0, c1) in enumerate(zip(cs, cs[1:])):   # 2. cross-snapshot, 3. localisation
        nodes = sorted(concept[c0])
        ari, h = agreement(run[c0], run[c1], nodes)
        ci_ari, ci_h = _subsample(run[c0], run[c1], nodes, n_sub)
        nl = [agreement(run[c0], n, nodes) for n in nulls[i * R:(i + 1) * R]]
        out["cross_snapshot"][f"{c0}-{c1}"] = {
            "common_nodes": len(nodes),
            "ari": [{"value": ari[k], "ci95": ci_ari[k], "new_paper_null": null_summary(ari[k], [x[0][k] for x in nl])} for k in range(K)],
            "hari": {"value": h, "ci95": ci_h, "new_paper_null": null_summary(h, [x[1] for x in nl])}}
        out["localisation"][f"{c0}-{c1}"] = _localisation(tkh, run[c0], run[c1], nodes, c0, c1)
    return _finite(out)


def _reassignment(g0, g1, nodes):
    """1 - Jaccard of each node's co-members among `nodes`, before and after."""
    cs = set(nodes)
    w0 = {v: k for k, m in g0.items() for v in m}
    w1 = {v: k for k, m in g1.items() for v in m}
    m0, m1 = {k: m & cs for k, m in g0.items()}, {k: m & cs for k, m in g1.items()}
    out = []
    for v in nodes:
        a, b = m0[w0[v]] - {v}, m1[w1[v]] - {v}
        u = len(a | b)
        out.append(0.0 if u == 0 else 1.0 - len(a & b) / u)
    return np.array(out)


def _localisation(tkh, lv0, lv1, nodes, c0, c1, n_boot=1000, seed=0):
    new = tkh.edges[(tkh.edges["article_year"] > c0) & (tkh.edges["article_year"] <= c1)]
    touched = {v for m in new["members"] for v in m}
    t = np.array([v in touched for v in nodes])
    rng = np.random.default_rng(seed)
    rows = []
    for g0, g1 in zip(lv0, lv1):
        r = _reassignment(g0, g1, nodes)
        mt, mu = float(r[t].mean()), float(r[~t].mean())
        boot = []
        for _ in range(n_boot):
            bt, bu = rng.choice(r[t], t.sum()), rng.choice(r[~t], (~t).sum())
            boot.append(bt.mean() / bu.mean() if bu.mean() > 0 else np.nan)
        b = np.array(boot)[np.isfinite(boot)]
        rows.append({"touched": int(t.sum()), "untouched": int((~t).sum()), "reassign_touched": mt, "reassign_untouched": mu,
                     "ratio": mt / mu if mu > 0 else None,
                     "ratio_ci95": [float(np.percentile(b, 2.5)), float(np.percentile(b, 97.5))] if len(b) else None})
    return rows


def _events(run_dir):
    ev = json.loads((Path(run_dir) / "temporal_events.json").read_text())["events"]
    cnt = Counter((f"{e['from_snapshot']}-{e['to_snapshot']}", e["level"], e["event"]) for e in ev if e["from_snapshot"] is not None)
    out = {}
    for (tr, k, kind), n in sorted(cnt.items()):
        out.setdefault(tr, {}).setdefault(str(k), {})[kind] = n
    return out


# ---------------------------------------------------------------- variants: what the temporal prior buys and costs

def gamma_tradeoff(cfg, base, gammas=(0.0, 0.25, 0.5, 0.75, 1.0), out_dir=None, R_p3=19, R_labels=199, R=19, n_jobs=8):
    """Each gamma is built as a full run (out_dir/<gamma>/) and scored on stability (this module) and on the
    period-adjusted P3 coherence (eval/experiments.p3_check, fewer nulls). Differences to gamma = 0 are paired: by
    seed for perturbation, by node subsample for cross-snapshot HARI."""
    from eval.experiments import p3_check
    from tkh.pipeline import run
    out_dir = Path(out_dir or Path(cfg.out_dir) / "gamma")
    res, runs = {}, {}
    for g in gammas:
        p = Params.from_config({**base.as_dict(), "gamma": g})
        d = out_dir / f"{g:g}"
        run(cfg, p, d)
        st = stability_check(cfg, p, d, R=R, n_jobs=n_jobs)
        co = p3_check(cfg, p, d, R=R_p3, R_labels=R_labels, n_jobs=n_jobs)
        runs[g] = (d, st)
        res[f"{g:g}"] = {"stability": st, "coherence": co}
    tkh = load(cfg)
    cs = sorted(cfg.cutoffs)
    concept = {c: set(concept_nodes(tkh, snapshot(tkh, c))) for c in cs}
    trees = {g: {c: [{k: m & concept[c] for k, m in lv.items()} for lv in
                     _concept_levels(json.loads((d / str(c) / "hierarchy.json").read_text()))] for c in cs} for g, (d, _) in runs.items()}
    g0 = gammas[0]
    for g in gammas[1:]:
        paired = {"perturbation_hari": {}, "cross_snapshot_hari": {}}
        for c in cs:
            a, b = runs[g][1]["perturbation"][str(c)]["per_seed_hari"], runs[g0][1]["perturbation"][str(c)]["per_seed_hari"]
            paired["perturbation_hari"][str(c)] = t_interval(np.subtract(a, b))
        for c0, c1 in zip(cs, cs[1:]):
            nodes = np.asarray(sorted(concept[c0]))
            rng = np.random.default_rng(0)
            d = []
            for _ in range(200):
                sub = list(rng.choice(nodes, len(nodes) // 2, replace=False))
                d.append(hari(trees[g][c0], trees[g][c1], sub) - hari(trees[g0][c0], trees[g0][c1], sub))
            paired["cross_snapshot_hari"][f"{c0}-{c1}"] = {"mean": float(np.mean(d)), "ci95": [float(np.percentile(d, 2.5)), float(np.percentile(d, 97.5))]}
        res[f"{g:g}"]["vs_gamma0"] = paired
    return _finite({"gammas": list(gammas), "base": base.as_dict(), "variants": res})
