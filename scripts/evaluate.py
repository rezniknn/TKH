"""Method-independent evaluation of ANY run directory (artefact format) -> <run>/eval/metrics.json.

    python scripts/evaluate.py --run out [--name model] [--extra "--param alpha=0.25"] [--stages m1,m2,m3det,m3,m4,nulls,mde]
    FAST=1 python scripts/evaluate.py --run out           # fewer null replicates and seeds ([fast] in eval.toml)

Inputs: <run>/<cutoff>/hierarchy.json, temporal_events.json, label_inputs.json (optional), the export, and the
evaluator's own definitions (tkh/evalkit, tkh/structure.py; configs/eval.toml). Method re-runs (perturbed and null
graphs) go through [eval] build_cmd only; `--extra` is appended to it, so a variant is re-run with ITS parameters.
Nothing here imports the coarsening implementation (tests/test_eval_independence.py).

Metrics (each row: family, metric, variant, snapshot, level, stratum, split, value, ci_lo, ci_hi, n):
  M1 coherence   residual citation-coupling lift per stratum; primary = no-overlap stratum, dev half A / report B
  M2 stability   perturbation (10% of all hyper-edges) per-level ARI + HARI; cross-snapshot HARI/ARI;
                 change localisation (touched = in any edge of a new paper); event counts
  M3 labels      claim-level entailment over-claim rate (raw, Rogan-Gladen corrected), judge Se/Sp, validity gate
  M4 retrieval   known-item queries: drill-down (member / label profiles) vs flat, PPR, degree, best flat
  M5 nulls       type- and period-preserving hypergraph configuration model (frozen exports) + random labels
  MDE            metric response to path-swap degradations of the evaluated tree
Primary tests (Holm): M1 vs M5 null; M2 vs M5 null perturbation (paired by seed); M4 hierarchy vs flat lexical.
M3 is an estimate with a validity gate (no null comparison in this iteration).
"""

import os
from pathlib import Path
import argparse
import json
import sys
import time
import tomllib

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import numpy as np  # noqa: E402
from scipy import stats as sps  # noqa: E402

from tkh.config import load_config  # noqa: E402
from tkh.evalkit import exports, runner  # noqa: E402
from tkh.evalkit.artefacts import Run  # noqa: E402
from tkh.evalkit.degrade import swap_paths  # noqa: E402
from tkh.evalkit.laminar import hari  # noqa: E402
from tkh.evalkit.queries import known_item_queries  # noqa: E402
from tkh.evaluate.coherence import Ruler, _lift_parts, _lifts, coverage, load_split  # noqa: E402
from tkh.evaluate.extrinsic import Index, Tree, degree_scores, expected_score, hierarchy_expected, ppr_scores  # noqa: E402
from tkh.evaluate.nulls import permute_hierarchy  # noqa: E402
from tkh.evaluate.stability import _reassignment, ari, labels, t_interval  # noqa: E402
from tkh.evaluate.stats import holm, null_compare  # noqa: E402
from tkh.io import load  # noqa: E402
from tkh.structure import CONCEPT_TYPES  # noqa: E402

STRATA = ("no_overlap", "overlap", "pooled", "all")


def load_eval(path=ROOT / "configs" / "eval.toml"):
    ev = tomllib.loads(Path(path).read_text())
    if os.environ.get("FAST") == "1":
        f = ev["fast"]
        ev["nulls"]["R"], ev["nulls"]["R_m4"] = f["R"], f["R_m4"]
        ev["m1"]["random_labels_R"], ev["m2"]["seeds"], ev["mde"]["seeds"] = f["random_labels_R"], f["seeds"], f["mde_seeds"]
    ev["eval"]["cache_dir"] = str((Path(path).parent / ev["eval"]["cache_dir"]).resolve())
    return ev


def row(family, metric, variant, value, snapshot=None, level=None, stratum=None, split=None, ci_lo=None, ci_hi=None, n=None, **x):
    f = lambda v: None if v is None or (isinstance(v, float) and not np.isfinite(v)) else (float(v) if isinstance(v, (float, np.floating)) else v)  # noqa: E731
    return {"family": family, "metric": metric, "variant": variant, "snapshot": snapshot, "level": level, "stratum": stratum,
            "split": split, "value": f(value), "ci_lo": f(ci_lo), "ci_hi": f(ci_hi), "n": None if n is None else int(n), **x}


def dist_row(family, metric, variant, vals, **cell):
    v = np.array([x for x in vals if x is not None and np.isfinite(x)], float)
    if not len(v):
        return row(family, metric, variant, None, n=0, **cell)
    return row(family, metric, variant, float(v.mean()), ci_lo=float(np.quantile(v, .025)), ci_hi=float(np.quantile(v, .975)), n=len(v), **cell)


# ---------------------------------------------------------------- M1

def m1_cell(ruler, level, stratum, jackknife=True):
    """(value, leave-one-paper-out replicates {paper: value}) of the lift in one stratum."""
    papers = ruler.papers
    val = _lifts(_lift_parts(ruler, level, papers))[stratum]
    reps = {}
    if jackknife:
        for i, a in enumerate(papers):
            reps[a] = _lifts(_lift_parts(ruler, level, papers[:i] + papers[i + 1:]))[stratum]
    return val, reps


def jack_ci(val, reps):
    x = np.array([r for r in reps.values() if np.isfinite(r) and r > 0])
    if val is None or not np.isfinite(val) or val <= 0 or len(x) < 3:
        return None, None
    lx = np.log(x)
    se = float(np.sqrt((len(lx) - 1) / len(lx) * ((lx - lx.mean()) ** 2).sum()))
    return val * np.exp(-1.96 * se), val * np.exp(1.96 * se)


def m1(tkh, cfg, ev, name, parts, rulers, rows, units, jackknife=True):
    L = len(next(iter(parts.values())))
    for c in cfg.cutoffs:
        for k in range(L):
            for s in ("A", "B", "all"):
                for st in STRATA:
                    val, reps = m1_cell(rulers[(c, s)], parts[c][k], st, jackknife)
                    lo, hi = jack_ci(val, reps) if jackknife else (None, None)
                    r = rulers[(c, s)]
                    n = sum(1 for _ in _pairs(r, st))
                    rows.append(row("M1", "coupling_lift", name, val, c, k, st, s, lo, hi, n))
                    if jackknife and c == ev["eval"]["primary_snapshot"]:
                        units[f"M1|{c}|{k}|{st}|{s}"] = {"value": val, "jack": {str(a): v for a, v in reps.items()}}


def _pairs(r, st):
    P = r.papers
    for i in range(len(P)):
        for j in range(i + 1, len(P)):
            ov = (min(P[i], P[j]), max(P[i], P[j])) in r.overlap_pairs
            if st in ("pooled", "all") or (st == "overlap") == ov:
                yield i, j


def m1_values(parts, rulers, cutoffs, split="B"):
    """Point values only (for null distributions): {(c, k, stratum): lift}."""
    out = {}
    for c in cutoffs:
        for k, lv in enumerate(parts[c]):
            vals = _lifts(_lift_parts(rulers[(c, split)], lv, rulers[(c, split)].papers))
            for st in STRATA:
                out[(c, k, st)] = vals[st]
    return out


# ---------------------------------------------------------------- M2

def cross_snapshot(parts, cutoffs, n_sub=200, seed=0):
    rng = np.random.default_rng(seed)
    out = []
    for t0, t1 in zip(cutoffs, cutoffs[1:]):
        common = sorted(set().union(*parts[t0][0].values()) & set().union(*parts[t1][0].values()))
        h = hari(parts[t0], parts[t1], common)
        subs = [hari(parts[t0], parts[t1], list(rng.choice(common, len(common) // 2, replace=False))) for _ in range(n_sub)]
        per = [ari(labels(a, common), labels(b, common)) for a, b in zip(parts[t0], parts[t1])]
        out.append({"from": t0, "to": t1, "hari": h, "lo": float(np.quantile(subs, .025)), "hi": float(np.quantile(subs, .975)),
                    "per_level": per, "n": len(common)})
    return out


def touched(tkh, t0, t1):
    e = tkh.edges
    new = e[(e["article_year"] > t0) & (e["article_year"] <= t1)]
    return {v for m in new["members"] for v in m}


def localisation(tkh, parts, cutoffs, n_boot=500, seed=0):
    rng = np.random.default_rng(seed)
    ntype = tkh.nodes["type"]
    out = []
    for t0, t1 in zip(cutoffs, cutoffs[1:]):
        tch = touched(tkh, t0, t1)
        for k, (g0, g1) in enumerate(zip(parts[t0], parts[t1])):
            common = sorted(v for v in set().union(*g0.values()) & set().union(*g1.values()) if ntype.at[v] in CONCEPT_TYPES)
            r = _reassignment(g0, g1, common)
            it = np.array([v in tch for v in common])
            if not it.any() or not (~it).any() or r[~it].mean() == 0:
                out.append({"from": t0, "to": t1, "level": k, "ratio": None, "lo": None, "hi": None, "n_touched": int(it.sum())})
                continue
            ratio = r[it].mean() / r[~it].mean()
            bs = []
            for _ in range(n_boot):
                i = rng.integers(0, len(common), len(common))
                rt, ru = r[i][it[i]], r[i][~it[i]]
                if len(rt) and len(ru) and ru.mean() > 0:
                    bs.append(rt.mean() / ru.mean())
            out.append({"from": t0, "to": t1, "level": k, "ratio": float(ratio), "lo": float(np.quantile(bs, .025)),
                        "hi": float(np.quantile(bs, .975)), "n_touched": int(it.sum()), "reassign_all": float(r.mean())})
    return out


def events_summary(run, tkh, cutoffs):
    rows = []
    for t0, t1 in zip(cutoffs, cutoffs[1:]):
        tch = touched(tkh, t0, t1)
        ev = [e for e in run.events if e.get("from_snapshot") == t0 and e.get("to_snapshot") == t1]
        for k in range(run.levels):
            evk = [e for e in ev if e["level"] == k]
            sizes = {g: m for g, m in run.parts[t1][k].items()}
            for kind in ("birth", "continue", "growth", "change", "merge", "split", "death"):
                sel = [e for e in evk if e["event"] == kind]
                share = [np.mean([v in tch for v in sizes[i]]) for e in sel for i in e.get("to_ids", []) if i in sizes]
                rows.append({"from": t0, "to": t1, "level": k, "event": kind, "count": len(sel),
                             "touched_share_of_members": float(np.mean(share)) if share else None})
    return rows


def perturb_scores(base_parts, pert_parts, cutoffs, c):
    nodes = sorted(set().union(*base_parts[c][0].values()) & set().union(*pert_parts[c][0].values()))
    return hari(base_parts[c], pert_parts[c], nodes), [ari(labels(a, nodes), labels(b, nodes))
                                                       for a, b in zip(base_parts[c], pert_parts[c])], len(nodes)


# ---------------------------------------------------------------- M4

def label_tree(index, levels, hier):
    """Drill-down tree whose profiles at labelled levels are the label + gloss text (members below)."""
    t = Tree(index, levels)
    lab = {s["id"]: f"{s['label']} {s['gloss'] or ''}" for s in hier["supernodes"] if s.get("label")}
    for k in range(len(levels)):
        for g in t.keys[k]:
            if g in lab:
                v = index.vec.transform([lab[g]]).toarray().ravel()
                nrm = np.linalg.norm(v)
                t.prof[k][g] = v / nrm if nrm else v
    return t


def m4_run(index, tree, queries, draws, seed=0, budgets=(50, 200)):
    out = []
    for q in queries:
        r = hierarchy_expected(index, tree, q["text"], {q["target"]}, set(), budgets, draws, seed)
        out.append(r)
    return out


def m4_baselines(index, tkh, queries, hub_frac, budgets=(50, 200)):
    out = {"flat": [], "ppr": [], "degree": []}
    deg = degree_scores(index, tkh, hub_frac)
    for q in queries:
        tg = {q["target"]}
        out["flat"].append(expected_score(index, index.query(q["text"]), tg, set(), budgets))
        out["ppr"].append(expected_score(index, ppr_scores(index, tkh, q["text"], hub_frac), tg, set(), budgets))
        out["degree"].append(expected_score(index, deg, tg, set(), budgets))
    return out


def by_target(queries, res, key="first_cost"):
    d = {}
    for q, r in zip(queries, res):
        d.setdefault(q["target"], []).append(r[key])
    return {t: float(np.mean(v)) for t, v in d.items()}


def cluster_ci(queries, res, key, n_boot=1000, seed=0):
    per = by_target(queries, res, key)
    v = np.array(list(per.values()))
    rng = np.random.default_rng(seed)
    bs = [v[rng.integers(0, len(v), len(v))].mean() for _ in range(n_boot)]
    return float(v.mean()), float(np.quantile(bs, .025)), float(np.quantile(bs, .975)), len(v)


# ---------------------------------------------------------------- main

def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    p.add_argument("--run", type=Path, required=True)
    p.add_argument("--name", default=None)
    p.add_argument("--extra", default="", help="appended to build_cmd for re-runs (the run's method parameters)")
    p.add_argument("--stages", default=None, help="default: m1,m2,m4,nulls,mde,m3det, plus m3 if [m3] enabled")
    p.add_argument("--config", default=None)
    p.add_argument("--eval", type=Path, default=ROOT / "configs" / "eval.toml")
    p.add_argument("--out-json", type=Path, default=None)
    p.add_argument("--build-cmd", default=None, help="override [eval] build_cmd (for another method's CLI)")
    p.add_argument("--light", action="store_true", help="fewer M4 draws and member profiles only (for variants)")
    args = p.parse_args(argv)
    cfg = load_config(args.config)
    ev = load_eval(args.eval)
    stages = set((args.stages or "m1,m2,m4,nulls,mde,m3det" + (",m3" if ev["m3"].get("enabled") else "")).split(","))
    name = args.name or args.run.name
    t0 = time.perf_counter()
    log = lambda m: print(f"[{time.perf_counter() - t0:6.0f}s] {m}", flush=True)  # noqa: E731
    tkh = load(cfg)
    import validate
    errs = validate.validate(args.run, cfg, tkh)
    if errs:
        raise SystemExit(f"{args.run} fails validate.py (P1/P2 gate): {errs[:5]}")
    run = Run(args.run, cfg.cutoffs, tkh)
    parts = run.concept_parts()
    cs, C, K = list(cfg.cutoffs), ev["eval"]["primary_snapshot"], ev["eval"]["primary_level"]
    hf, cache = ev["eval"]["hub_frac"], Path(ev["eval"]["cache_dir"])
    tmpl = args.build_cmd or ev["eval"]["build_cmd"]
    if args.light:
        ev["m4"]["draws"] = ev["m4"]["null_draws"]
    rows, tests, units = [], [], {}
    raw = exports.load_raw(cfg.graph)
    tag = runner.command(tmpl, "G", "O", args.extra)          # null / perturbed builds are keyed by the method command
    import hashlib
    mkey = hashlib.sha256(tag.encode()).hexdigest()[:10]

    split = load_split(ROOT / "data" / "eval_splits.json")
    rulers = {(c, s): Ruler(tkh, c, None if s == "all" else split[s], hub_frac=hf) for c in cs for s in ("A", "B", "all")}

    if "m1" in stages:
        for c in cs:
            for k_, v in coverage(rulers[(c, "all")]).items():
                rows.append(row("M1", f"coverage_{k_}", "ruler", v, c, split="all"))
        m1(tkh, cfg, ev, name, parts, rulers, rows, units)
        vals = {k: [] for k in [(c, k_, st) for c in cs for k_ in range(run.levels) for st in STRATA]}
        for s in range(ev["m1"]["random_labels_R"]):
            for kk, v in m1_values(permute_hierarchy(parts, tkh, s, cs), rulers, cs).items():
                vals[kk].append(v)
        model_vals = m1_values(parts, rulers, cs)
        for (c, k_, st), v in vals.items():
            rows.append(dist_row("M1", "coupling_lift", "random-labels", v, snapshot=c, level=k_, stratum=st, split="B"))
            cmp_ = null_compare(model_vals[(c, k_, st)], v)
            tests.append({"name": "M1 coupling lift vs random-labels", "family": "M1", "cell": {"snapshot": c, "level": k_, "stratum": st, "split": "B"},
                          "model": model_vals[(c, k_, st)], "null": "random-labels", "p": cmp_["p"], "null_mean": cmp_["null_mean"], "R": cmp_["R"], "primary": False})
        log("M1")

    # ---- re-runs through build_cmd: perturbed exports (model) and M5 null exports
    pert_runs, null_runs, null_pert_runs = {}, [], {}
    jobs = []
    if "m2" in stages:
        for rel in ("all", ev["m2"]["sensitivity_relations"]):
            for s in ev["m2"]["seeds"]:
                g = cache / "exports" / f"perturb_{rel}_{s}.json"
                if not g.exists():
                    rr = raw if rel == "all" else _only_concept(raw)
                    pr, dropped = exports.perturb(rr, ev["m2"]["frac"], s, cs)
                    if rel != "all":
                        pr = _drop_ids(raw, set(dropped))
                    exports.write(pr, g)
                o = cache / "builds" / mkey / f"perturb_{rel}_{s}"
                jobs.append((g, o, args.extra))
                pert_runs[(rel, s)] = o
    if "nulls" in stages:
        for s in range(ev["nulls"]["R"]):
            g = cache / "exports" / f"null_{s}.json"
            if not g.exists():
                nr, diag = exports.configuration_null(raw, s, cs, ev["nulls"]["sweeps"])
                exports.write(nr, g)
                (cache / "exports" / f"null_{s}.diag.json").write_text(json.dumps(diag))
            o = cache / "builds" / mkey / f"null_{s}"
            jobs.append((g, o, args.extra))
            null_runs.append(o)
        if "m2" in stages:
            for s in ev["m2"]["seeds"]:
                g = cache / "exports" / f"null_{s}_perturb_{s}.json"
                if not g.exists():
                    pr, _ = exports.perturb(exports.load_raw(cache / "exports" / f"null_{s}.json"), ev["m2"]["frac"], s, cs)
                    exports.write(pr, g)
                o = cache / "builds" / mkey / f"null_{s}_perturb_{s}"
                jobs.append((g, o, args.extra))
                null_pert_runs[s] = o
    if jobs:
        log(f"{len(jobs)} method re-runs through build_cmd")
        runner.build_many(tmpl, jobs, ev["eval"]["jobs"], cwd=ROOT, log=log)

    if "m2" in stages:
        for rel in ("all", ev["m2"]["sensitivity_relations"]):
            per_seed = {}
            for s in ev["m2"]["seeds"]:
                pp = Run(pert_runs[(rel, s)], cs, tkh).concept_parts()
                for c in cs:
                    h, per, n = perturb_scores(parts, pp, cs, c)
                    per_seed.setdefault(c, []).append((s, h, per, n))
            for c, lst in per_seed.items():
                ti = t_interval([x[1] for x in lst])
                rows.append(row("M2", "perturbation_hari", name, ti["mean"], c, stratum=rel, ci_lo=ti["lo"], ci_hi=ti["hi"], n=ti["n"]))
                for k_ in range(run.levels):
                    tk = t_interval([x[2][k_] for x in lst])
                    rows.append(row("M2", "perturbation_ari", name, tk["mean"], c, k_, stratum=rel, ci_lo=tk["lo"], ci_hi=tk["hi"], n=tk["n"]))
                if rel == "all" and c == C:
                    units["M2|perturb_hari"] = {str(x[0]): x[1] for x in lst}
        for r_ in cross_snapshot(parts, cs):
            rows.append(row("M2", "cross_snapshot_hari", name, r_["hari"], r_["to"], ci_lo=r_["lo"], ci_hi=r_["hi"], n=r_["n"], transition=f"{r_['from']}-{r_['to']}"))
            for k_, a in enumerate(r_["per_level"]):
                rows.append(row("M2", "cross_snapshot_ari", name, a, r_["to"], k_, n=r_["n"], transition=f"{r_['from']}-{r_['to']}"))
        for r_ in localisation(tkh, parts, cs):
            rows.append(row("M2", "change_localisation", name, r_["ratio"], r_["to"], r_["level"], ci_lo=r_["lo"], ci_hi=r_["hi"],
                            n=r_["n_touched"], transition=f"{r_['from']}-{r_['to']}"))
        for e in events_summary(run, tkh, cs):
            rows.append(row("M2", f"events_{e['event']}", name, e["count"], e["to"], e["level"], transition=f"{e['from']}-{e['to']}",
                            touched_share=e["touched_share_of_members"]))
        log("M2")

    null_parts = [Run(o, cs, tkh).concept_parts() for o in null_runs] if null_runs else []
    if null_parts:
        diags = [json.loads((cache / "exports" / f"null_{i}.diag.json").read_text()) for i in range(len(null_runs))
                 if (cache / "exports" / f"null_{i}.diag.json").exists()]
        rows.append(dist_row("M5", "retained_incidence", "configuration-null", [d["retained_incidence"] for d in diags]))
        if "m1" in stages:
            nv = [m1_values(npp, rulers, cs) for npp in null_parts]
            mv = m1_values(parts, rulers, cs)
            for kk in mv:
                c, k_, st = kk
                vals = [x[kk] for x in nv]
                rows.append(dist_row("M1", "coupling_lift", "configuration-null", vals, snapshot=c, level=k_, stratum=st, split="B"))
                cmp_ = null_compare(mv[kk], vals)
                tests.append({"name": "M1 coupling lift vs configuration null", "family": "M1", "cell": {"snapshot": c, "level": k_, "stratum": st, "split": "B"},
                              "model": mv[kk], "null": "configuration-null", "p": cmp_["p"], "null_mean": cmp_["null_mean"], "R": cmp_["R"],
                              "z": cmp_["z"], "primary": c == C and k_ == K and st == ev["m1"]["primary_stratum"]})
        if "m2" in stages:
            mh = {r_["to"]: r_["hari"] for r_ in cross_snapshot(parts, cs, n_sub=2)}
            nh = [{r_["to"]: r_["hari"] for r_ in cross_snapshot(npp, cs, n_sub=2)} for npp in null_parts]
            for c in mh:
                vals = [x[c] for x in nh]
                rows.append(dist_row("M2", "cross_snapshot_hari", "configuration-null", vals, snapshot=c))
                cmp_ = null_compare(mh[c], vals)
                tests.append({"name": "M2 cross-snapshot HARI vs configuration null", "family": "M2", "cell": {"snapshot": c},
                              "model": mh[c], "null": "configuration-null", "p": cmp_["p"], "null_mean": cmp_["null_mean"], "R": cmp_["R"], "primary": False})
            ml = {(r_["to"], r_["level"]): r_["ratio"] for r_ in localisation(tkh, parts, cs, n_boot=2)}
            nl = [{(r_["to"], r_["level"]): r_["ratio"] for r_ in localisation(tkh, npp, cs, n_boot=2)} for npp in null_parts]
            for kk in ml:
                rows.append(dist_row("M2", "change_localisation", "configuration-null", [x.get(kk) for x in nl], snapshot=kk[0], level=kk[1]))
            # perturbation of null graphs, paired by perturbation seed
            mp = units.get("M2|perturb_hari", {})
            diffs, nvals = [], []
            for s, o in null_pert_runs.items():
                base = null_parts[s]
                pp = Run(o, cs, tkh).concept_parts()
                h, _, _ = perturb_scores(base, pp, cs, C)
                nvals.append(h)
                if str(s) in mp:
                    diffs.append(mp[str(s)] - h)
            ti = t_interval(nvals)
            rows.append(row("M2", "perturbation_hari", "configuration-null", ti["mean"], C, stratum="all", ci_lo=ti["lo"], ci_hi=ti["hi"], n=ti["n"]))
            pt = sps.ttest_1samp(diffs, 0, alternative="greater").pvalue if len(diffs) >= 2 else None
            tests.append({"name": "M2 perturbation HARI model vs configuration null (paired by seed)", "family": "M2", "cell": {"snapshot": C},
                          "model": float(np.mean(list(mp.values()))) if mp else None, "null": "configuration-null",
                          "p": None if pt is None else float(pt), "null_mean": ti["mean"], "R": len(diffs), "primary": True})
        log("M5 null comparisons")

    if "m4" in stages:
        c4 = ev["m4"]["snapshot"]
        index = Index(tkh, c4)
        qs = [q for q in known_item_queries(tkh, c4) if q["target"] in index.pos]
        budgets = tuple(ev["m4"]["budgets"])
        res = {"hierarchy (members)": m4_run(index, Tree(index, parts[c4]), qs, ev["m4"]["draws"], budgets=budgets)}
        if not args.light:
            res["hierarchy (labels)"] = m4_run(index, label_tree(index, parts[c4], run.hier[c4]), qs, ev["m4"]["draws"], budgets=budgets)
        res.update(m4_baselines(index, tkh, qs, hf, budgets))
        res["best flat"] = [min((res[b][i] for b in ("flat", "ppr", "degree")), key=lambda r: r["first_cost"]) for i in range(len(qs))]
        papers_of = {}
        for m_, a in zip(tkh.edges["members"], tkh.edges["article_id"]):
            for v in m_:
                papers_of.setdefault(v, set()).add(a)
        deg_bin = {q["target"]: ("1 paper" if len(papers_of.get(q["target"], ())) <= 1 else "2-4 papers"
                                 if len(papers_of.get(q["target"], ())) <= 4 else "5+ papers") for q in qs}
        for m, rs in res.items():
            for key in ("first_cost", f"recall@{budgets[0]}", f"recall@{budgets[1]}"):
                v, lo, hi, n = cluster_ci(qs, rs, key)
                rows.append(row("M4", key, name if m.startswith("hierarchy") else m, v, c4, stratum=m, ci_lo=lo, ci_hi=hi, n=n, queries=len(qs)))
            for b in sorted(set(deg_bin.values())):
                sel = [i for i, q in enumerate(qs) if deg_bin[q["target"]] == b]
                v, lo, hi, n = cluster_ci([qs[i] for i in sel], [rs[i] for i in sel], "first_cost")
                rows.append(row("M4", "first_cost_by_target_degree", name if m.startswith("hierarchy") else m, v, c4, stratum=m, split=b, ci_lo=lo, ci_hi=hi, n=n))
        units["M4|cost_by_target"] = {m: by_target(qs, rs) for m, rs in res.items()}
        a = by_target(qs, res["hierarchy (members)"])
        for other in ("flat", "best flat"):
            b = by_target(qs, res[other])
            d = np.array([b[t] - a[t] for t in a])
            pw = sps.wilcoxon(d, alternative="greater").pvalue if np.any(d != 0) else None
            tests.append({"name": f"M4 cost hierarchy (members) vs {other}", "family": "M4", "cell": {"snapshot": c4},
                          "model": float(np.mean(list(a.values()))), "null": other, "p": None if pw is None else float(pw),
                          "null_mean": float(np.mean(list(b.values()))), "R": len(d), "primary": other == "flat"})
        if null_parts:
            nm = []
            for npp in null_parts[:ev["nulls"]["R_m4"]]:
                rs = m4_run(index, Tree(index, npp[c4]), qs, ev["m4"]["null_draws"], budgets=budgets)
                nm.append(float(np.mean(list(by_target(qs, rs).values()))))
            rows.append(dist_row("M4", "first_cost", "configuration-null", nm, snapshot=c4, stratum="hierarchy (members)"))
            cmp_ = null_compare(float(np.mean(list(a.values()))), nm, higher_is_better=False)
            tests.append({"name": "M4 cost hierarchy (members) vs configuration null", "family": "M4", "cell": {"snapshot": c4},
                          "model": float(np.mean(list(a.values()))), "null": "configuration-null", "p": cmp_["p"], "null_mean": cmp_["null_mean"], "R": cmp_["R"], "primary": False})
        log(f"M4 ({len(qs)} queries, {len(set(q['target'] for q in qs))} targets)")

    if "mde" in stages:
        c, kprim = C, K
        index = Index(tkh, ev["m4"]["snapshot"]) if "m4" in stages else None
        for f in [0.0] + list(ev["mde"]["fractions"]):
            m1v, m4v = [], []
            for s in ev["mde"]["seeds"]:
                dp = {cc: (swap_paths(parts[cc], f, s) if f else parts[cc]) for cc in cs}
                m1v.append(_lifts(_lift_parts(rulers[(c, "A")], dp[c][kprim], rulers[(c, "A")].papers))[ev["m1"]["primary_stratum"]])
                if index is not None:
                    rs = m4_run(index, Tree(index, dp[ev["m4"]["snapshot"]]), qs, ev["m4"]["null_draws"], budgets=tuple(ev["m4"]["budgets"]))
                    m4v.append(float(np.mean(list(by_target(qs, rs).values()))))
            rows.append(dist_row("MDE", "coupling_lift_dev", name, m1v, snapshot=c, level=kprim, stratum=ev["m1"]["primary_stratum"], split=f"swap {f:g}"))
            if m4v:
                rows.append(dist_row("MDE", "m4_first_cost", name, m4v, snapshot=ev["m4"]["snapshot"], split=f"swap {f:g}"))
        log("MDE")

    if "m3" in stages or "m3det" in stages:   # deterministic label checks: no model involved
        from tkh.evaluate.faithfulness import NameChecker, deterministic_checks
        from tkh.evaluate.stats import wilson
        chk = NameChecker(tkh)
        res3 = {"year_after_cutoff": [], "named_non_member": [], "future_entity": []}
        for c, h in run.hier.items():
            for s_ in h["supernodes"]:
                if s_["level"] in (0, 1) and s_.get("label"):
                    d = deterministic_checks(f"{s_['label']}. {s_['gloss'] or ''}", s_["member_ids"], c, chk)
                    for k_ in res3:
                        res3[k_].append(bool(d[k_]))
        for k_, v in res3.items():
            lo, hi = wilson(sum(v), len(v))
            rows.append(row("M3", f"det_{k_}_rate", name, sum(v) / len(v) if v else None, ci_lo=lo, ci_hi=hi, n=len(v), k=sum(v)))
    if "m3" in stages:
        from tkh.evalkit.entailment import Entailment, summarise
        ent = Entailment(tkh, cfg)
        hs = {c: run.hier[c] for c in ev["m3"]["snapshots"]}
        lr, cr, ct = ent.run(hs, tuple(ev["m3"]["levels"]))
        ent.llm.save()
        s3 = summarise(lr, cr, ct, j_min=ev["m3"]["j_min"])
        for k_, v in s3.items():
            if isinstance(v, dict):
                rows.append(row("M3", k_, name, v.get("value"), ci_lo=v.get("lo"), ci_hi=v.get("hi"), n=v.get("n"),
                                **{x: y for x, y in v.items() if x not in ("value", "lo", "hi", "n")}))
            else:
                rows.append(row("M3", k_, name, v))
        (args.run / "eval").mkdir(exist_ok=True)
        (args.run / "eval" / "m3_judgements.json").write_text(json.dumps({"labels": lr, "claims": cr, "controls": ct}, indent=1, ensure_ascii=False))
        log(f"M3 ({len(lr)} labels, {len(cr)} claim judgements, {len(ct)} controls; {ent.llm.calls} new calls; valid={s3['valid']})")

    adj = holm({t["name"]: t["p"] for t in tests if t["primary"]})
    for t in tests:
        t["p_holm"] = adj.get(t["name"]) if t["primary"] else None
    meta = {"run": str(args.run), "name": name, "extra": args.extra, "build_cmd": tmpl, "stages": sorted(stages),
            "fast": os.environ.get("FAST") == "1", "nulls_R": ev["nulls"]["R"], "seeds": ev["m2"]["seeds"]}
    outp = args.out_json or (args.run / "eval" / "metrics.json")
    outp.parent.mkdir(parents=True, exist_ok=True)
    outp.write_text(json.dumps({"meta": meta, "rows": rows, "tests": tests}, indent=1) + "\n")
    (outp.parent / "units.json").write_text(json.dumps(units) + "\n")
    log(f"{len(rows)} rows, {len(tests)} tests -> {outp}")


def _only_concept(raw):
    from tkh.structure import CONCEPT_RELATIONS
    out = dict(raw)
    out["hyperedges"] = [e for e in raw["hyperedges"] if e["relation_type"] in CONCEPT_RELATIONS]
    return out


def _drop_ids(raw, ids):
    out = dict(raw)
    out["hyperedges"] = [e for e in raw["hyperedges"] if e["id"] not in ids]
    return out


if __name__ == "__main__":
    main()
