"""Pipeline step 'metrics': runs all T6 evaluations and writes out/metrics.json.

    python scripts/compute_metrics.py [--config CFG] [--eval configs/eval.toml] [--out DIR]
    TKH_LLM_MODE=live python scripts/compute_metrics.py     # fill the LLM cache for E3 (judge calls)

Inputs: the shipped outputs (<out>/<cutoff>/hierarchy.json), <out>/selection.json and the
partitions of scripts/sweep.py (<out>/runs/). Every metric is computed on concept nodes,
against the REAL graph, for the selected model ("model"), every swept configuration and
ablation (variant = its cid), every null kind and the baselines.

Output rows (schema/metrics.schema.json):
    family, metric, variant, snapshot, level, stratum, split, value, ci_lo, ci_hi, n
and tests: name, family, metric, cell, model, null, statistic, p, p_holm, primary.
Four primary tests, one per family, pre-registered and Holm-corrected:
    E1  model vs full-null: E1a lift, <=2026, level 1, pooled strata, split B (empirical p)
    E2  model vs full-null: perturbation ARI, <=2026, level 1 (Wilcoxon paired by perturbation seed)
    E3  model vs random-labels: forced-choice identification of the label from held-out evidence,
        <=2026, levels 0-1, primary judge (Fisher exact). The pre-registered absolute rating
        ('wrong' share) failed its swapped-gloss control and is reported as such (see faithfulness.py).
    E4  hierarchy vs flat lexical: cost to the first target, <=2026 (Wilcoxon paired by question)
"""

import os

for _v in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "VECLIB_MAXIMUM_THREADS"):
    os.environ.setdefault(_v, "1")

from pathlib import Path
import argparse
import json
import sys
import time

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import numpy as np  # noqa: E402
from scipy import stats as sps  # noqa: E402

from scripts.sweep import SPLIT_PATH, load_eval  # noqa: E402
from tkh.config import add_config_args, config_from_args  # noqa: E402
from tkh.evaluate import runs  # noqa: E402
from tkh.evaluate.coherence import Ruler, coupling_lift, coverage, gt_comembership, load_split  # noqa: E402
from tkh.evaluate.extrinsic import Index, evaluate as e4_evaluate, load_questions, penalised_first_cost  # noqa: E402
from tkh.evaluate.faithfulness import Judge, evaluate_labels, forced_choice, summarise  # noqa: E402
from tkh.evaluate.stats import wilson  # noqa: E402
from tkh.llm import CachedLLM  # noqa: E402
from tkh.label import _mode  # noqa: E402
from tkh.evaluate.groundtruth import load_ground_truth, question_targets  # noqa: E402
from tkh.evaluate.nulls import permute_hierarchy  # noqa: E402
from tkh.evaluate.stability import (ari, change_localisation, cross_snapshot_stability, labels,  # noqa: E402
                                    read_partitions, t_interval)
from tkh.evaluate.stats import holm, null_compare, wilcoxon_paired  # noqa: E402
from tkh.export import assemble_hierarchies  # noqa: E402
from tkh.hierarchy import Params, concept_only  # noqa: E402
from tkh.io import load  # noqa: E402
from tkh.label import LLMLabeller  # noqa: E402
from tkh.semantic import CONCEPT_TYPES  # noqa: E402
from tkh.temporal import match_and_name  # noqa: E402

STRATA = ("overlap", "no_overlap", "pooled", "all")


def row(family, metric, variant, value, snapshot=None, level=None, stratum=None, split=None,
        ci_lo=None, ci_hi=None, n=None, **extra):
    f = lambda x: None if x is None or (isinstance(x, float) and not np.isfinite(x)) else (float(x) if isinstance(x, (float, np.floating)) else x)  # noqa: E731
    return {"family": family, "metric": metric, "variant": variant, "snapshot": snapshot, "level": level,
            "stratum": stratum, "split": split, "value": f(value), "ci_lo": f(ci_lo), "ci_hi": f(ci_hi),
            "n": None if n is None else int(n), **extra}


def null_rows(family, metric, variant, values, **cell):
    v = [x for x in values if x is not None and np.isfinite(x)]
    if not v:
        return row(family, metric, variant, None, n=0, **cell)
    return row(family, metric, variant, float(np.mean(v)), ci_lo=float(np.quantile(v, 0.025)),
               ci_hi=float(np.quantile(v, 0.975)), n=len(v), **cell)


# ---------------------------------------------------------------- E1

def e1(tkh, cfg, ev, model, variants, null_parts, out_rows, tests, log):
    split = load_split(SPLIT_PATH)
    hf = ev["eval"]["hub_frac"]
    rulers = {(c, s): Ruler(tkh, c, None if s == "all" else split[s], hub_frac=hf) for c in cfg.cutoffs for s in ("A", "B", "all")}
    for c in cfg.cutoffs:
        for k, v in coverage(rulers[(c, "all")]).items():
            out_rows.append(row("E1", f"coverage_{k}", "ruler", v, snapshot=c, split="all"))
    cells = [(c, k) for c in cfg.cutoffs for k in range(len(cfg.budgets))]
    obs = {}
    for name, parts in variants.items():
        for (c, k) in cells:
            for s in ("A", "B", "all"):
                res = coupling_lift(rulers[(c, s)], parts[c][k])
                for st in STRATA:
                    r = res[st]
                    out_rows.append(row("E1", "coupling_lift", name, r["value"], c, k, st, s, r.get("lo"), r.get("hi"), r["n_pairs"]))
                    obs[(name, c, k, st, s)] = r["value"]
    log(f"E1a: {len(variants)} variants")
    nulls = {}
    for kind, plist in null_parts.items():
        for parts in plist:
            for (c, k) in cells:
                for s in ("B", "all"):
                    res = coupling_lift(rulers[(c, s)], parts[c][k], jackknife=False)
                    for st in STRATA:
                        nulls.setdefault((kind, c, k, st, s), []).append(res[st]["value"])
    rl = []
    R = ev["nulls"]["random_labels_R"]
    for seed in range(R):
        perm = permute_hierarchy(model, tkh, seed, cfg.cutoffs)
        for (c, k) in cells:
            res = coupling_lift(rulers[(c, "B")], perm[c][k], jackknife=False)
            for st in STRATA:
                nulls.setdefault(("random-labels", c, k, st, "B"), []).append(res[st]["value"])
        rl.append(perm)
    log(f"E1a nulls: {', '.join(null_parts)} + random-labels R={R}")
    for (kind, c, k, st, s), vals in sorted(nulls.items(), key=str):
        out_rows.append(null_rows("E1", "coupling_lift", f"{kind}-null" if kind != "random-labels" else kind, vals,
                                  snapshot=c, level=k, stratum=st, split=s))
        cmp_ = null_compare(obs[("model", c, k, st, s)], vals, higher_is_better=True)
        primary = (kind == "full" and c == 2026 and k == 1 and st == "pooled" and s == "B")
        tests.append({"name": f"E1a model vs {kind}", "family": "E1", "metric": "coupling_lift",
                      "cell": {"snapshot": c, "level": k, "stratum": st, "split": s}, "model": obs[("model", c, k, st, s)],
                      "null": kind, "statistic": cmp_["z"], "p": cmp_["p"], "null_mean": cmp_["null_mean"],
                      "R": cmp_["R"], "primary": primary})
    # E1b (descriptive)
    gt = load_ground_truth(cfg.ground_truth)
    targets = question_targets(tkh, gt, CONCEPT_TYPES)
    for name, parts in {**variants, **{f"{k}-null[0]": v[0] for k, v in null_parts.items()}, "random-labels[0]": rl[0]}.items():
        for k in range(len(cfg.budgets)):
            r = gt_comembership(tkh, parts[2026][k], targets, 2026)
            for m in ("exp_same_paper", "exp_cross_paper", "exp_wrong"):
                out_rows.append(row("E1", f"gt_comembership_{m}", name, r[m]["rate"], 2026, k, ci_lo=r[m]["lo"], ci_hi=r[m]["hi"],
                                    n=r[m]["pairs"], hits=r[m]["hits"]))
            out_rows.append(row("E1", "gt_comembership_chance", name, r["chance"], 2026, k, n=r["n_questions"]))
    return rl


# ---------------------------------------------------------------- E2

def e2(tkh, cfg, ev, out, sel, variants, null_parts, out_rows, tests, log):
    st = ev["stability"]
    seeds = st["seeds"]
    cells = [(c, k) for c in cfg.cutoffs for k in range(len(cfg.budgets))]
    cids = {"model": sel["winner"], **{v: v for v in variants if v != "model"}}
    per_seed = {}
    for name, cid in cids.items():
        base = variants[name]
        for s in seeds:
            p = runs.run_path(out, "perturb", cid, s)
            if not p.exists():
                continue
            pert, _ = runs.load(p)
            for (c, k) in cells:
                nodes = sorted(set().union(*base[c][k].values()))
                per_seed.setdefault((name, c, k), {})[s] = ari(labels(base[c][k], nodes), labels(pert[c][k], nodes))
    for (name, c, k), d in per_seed.items():
        ti = t_interval(list(d.values()))
        out_rows.append(row("E2", "perturbation_ari", name, ti["mean"], c, k, ci_lo=ti["lo"], ci_hi=ti["hi"], n=ti["n"]))
    nul = {}
    for kind in null_parts:
        for ns in range(st["null_R"]):
            base, _ = runs.load(runs.run_path(out, "null", kind, ns))
            for s in seeds:
                pert, _ = runs.load(runs.run_path(out, "perturb_null", kind, ns, s))
                for (c, k) in cells:
                    nodes = sorted(set().union(*base[c][k].values()))
                    nul.setdefault((kind, c, k), {}).setdefault(s, []).append(ari(labels(base[c][k], nodes), labels(pert[c][k], nodes)))
    for (kind, c, k), d in nul.items():
        flat = [x for v in d.values() for x in v]
        ti = t_interval([np.mean(v) for v in d.values()])
        out_rows.append(row("E2", "perturbation_ari", f"{kind}-null", float(np.mean(flat)), c, k, ci_lo=ti["lo"], ci_hi=ti["hi"], n=len(flat)))
        m = per_seed.get(("model", c, k), {})
        common = [s for s in seeds if s in m and s in d]
        p = wilcoxon_paired([m[s] for s in common], [np.mean(d[s]) for s in common], "greater") if len(common) >= 2 else None
        tests.append({"name": f"E2 perturbation ARI model vs {kind}", "family": "E2", "metric": "perturbation_ari",
                      "cell": {"snapshot": c, "level": k}, "model": float(np.mean([m[s] for s in common])) if common else None,
                      "null": kind, "statistic": None, "p": p, "null_mean": float(np.mean(flat)), "R": len(flat),
                      "primary": kind == "full" and c == 2026 and k == 1})
    log("E2 perturbation")
    cs = list(cfg.cutoffs)
    for name, parts in variants.items():
        for r in cross_snapshot_stability(parts, cs, n_boot=200, n_perm=199):
            out_rows.append(row("E2", "cross_snapshot_ari", name, r["ari"], r["to"], r["level"], ci_lo=r["sub_lo"], ci_hi=r["sub_hi"],
                                n=r["n_common"], transition=f"{r['from']}-{r['to']}", p_vs_random_labels=r["p_vs_random_labels"]))
        for r in change_localisation(tkh, parts, cs, n_perm=199):
            out_rows.append(row("E2", "change_localisation_ratio", name, r["ratio"], r["to"], r["level"], n=r["n_old"],
                                transition=f"{r['from']}-{r['to']}", n_touched=r["n_touched"], p=r["p_ratio_gt_1"],
                                reassign_touched=r["reassign_touched"], reassign_untouched=r["reassign_untouched"]))
            out_rows.append(row("E2", "reassignment_rate", name, r["reassign_all"], r["to"], r["level"], n=r["n_old"],
                                transition=f"{r['from']}-{r['to']}"))
    for kind, plist in null_parts.items():
        acc = {}
        for parts in plist:
            for r in cross_snapshot_stability(parts, cs, n_boot=2, n_perm=1):
                acc.setdefault(("cross_snapshot_ari", r["to"], r["level"]), []).append(r["ari"])
            for r in change_localisation(tkh, parts, cs, n_perm=1):
                acc.setdefault(("change_localisation_ratio", r["to"], r["level"]), []).append(r["ratio"])
                acc.setdefault(("reassignment_rate", r["to"], r["level"]), []).append(r["reassign_all"])
        for (metric, c, k), vals in acc.items():
            out_rows.append(null_rows("E2", metric, f"{kind}-null", vals, snapshot=c, level=k))
    log("E2 cross-snapshot and localisation")


# ---------------------------------------------------------------- E3

def e3(tkh, cfg, ev, out, model, out_rows, tests, log):
    cs = list(cfg.cutoffs)
    hier = {c: json.loads((Path(out) / str(c) / "hierarchy.json").read_text()) for c in cs}
    judge = Judge(tkh, cfg)
    rows = evaluate_labels(tkh, cfg, hier, judge, passes=("held_out",))
    rows += evaluate_labels(tkh, cfg, {2026: hier[2026]}, judge, passes=("full",), swapped=True)
    # random-labels null: one permuted hierarchy at <=2026, labelled and judged like the model
    seed = ev["nulls"].get("random_labels_e3_seed", 0)
    perm = permute_hierarchy(model, tkh, seed, cs)
    sub = {2026: perm[2026]}
    ids, _ = match_and_name(sub, [2026])
    lab = LLMLabeller(tkh, cfg)
    rl_h = assemble_hierarchies(sub, ids, lab, cfg.budgets)
    rl_rows = evaluate_labels(tkh, cfg, rl_h, judge, passes=("held_out",))
    for r in rl_rows:
        r["pass"] = "random_labels"
    rows += rl_rows
    judge.llm.save()
    lab.llm.save()
    log(f"E3: {len(rows)} judgements ({judge.llm.calls} new judge calls, {lab.llm.calls} new labeller calls)")
    groups = {}
    for r in rows:
        for c in (r["snapshot"], "all"):
            for k in (r["level"], "all"):
                groups.setdefault((r["pass"], c, k), []).append(r)
    for (ps, c, k), rs in sorted(groups.items(), key=str):
        s = summarise([r["rating"] for r in rs])
        variant = {"held_out": "model", "full": "model", "swapped": "swapped-gloss", "random_labels": "random-labels"}[ps]
        for m, key in (("abs_over_claim_rate", "wrong"), ("abs_vague_rate", "vague"), ("abs_accurate_rate", "accurate"), ("abs_unparsed_rate", "unparsed")):
            out_rows.append(row("E3", m, variant, s[key]["share"], None if c == "all" else c, None if k == "all" else k,
                                split=ps, ci_lo=s[key]["lo"], ci_hi=s[key]["hi"], n=s["n"], k=s[key]["k"]))
        if ps in ("held_out", "full"):
            for d in ("det_year_after_cutoff", "det_named_non_member", "det_future_entity"):
                kk = sum(bool(r.get(d)) for r in rs)
                out_rows.append(row("E3", d[4:] + "_rate", variant, kk / len(rs), None if c == "all" else c,
                                    None if k == "all" else k, split=ps, n=len(rs), k=kk))
    m = groups[("held_out", 2026, "all")]
    sw = groups[("swapped", 2026, "all")]
    km, ks = sum(r["rating"] == "wrong" for r in m), sum(r["rating"] == "wrong" for r in sw)
    am, as_ = sum(r["rating"] == "accurate" for r in m), sum(r["rating"] == "accurate" for r in sw)
    _, p = sps.fisher_exact([[am, len(m) - am], [as_, len(sw) - as_]], alternative="greater")
    tests.append({"name": "E3 absolute rating discriminates: accurate share true vs swapped glosses", "family": "E3",
                  "metric": "abs_accurate_rate", "cell": {"snapshot": 2026, "level": "0-1"}, "model": am / len(m),
                  "null": "swapped-gloss", "statistic": None, "p": float(p), "null_mean": as_ / len(sw), "R": 1, "primary": False})

    # forced choice: primary judge on every snapshot; robustness judges at <=2026; model vs random-labels labels
    fc = []
    judges = [cfg.labels["judge_model"]] + list(ev.get("e3", {}).get("robustness_judges", []))
    fseed = ev.get("e3", {}).get("forced_choice_seed", 0)
    for jm in judges:
        jj = judge if jm == cfg.labels["judge_model"] else Judge(tkh, cfg, CachedLLM(jm, cfg.labels["cache"], cfg.labels.get("endpoint", "http://localhost:11434"), _mode(cfg)))
        fc += forced_choice(tkh, cfg, hier if jm == cfg.labels["judge_model"] else {2026: hier[2026]}, jj, seed=fseed, tag="model")
        fc += forced_choice(tkh, cfg, rl_h, jj, seed=fseed, tag="random-labels")
        jj.llm.save()
        log(f"E3 forced choice {jm}: {jj.llm.calls} new calls")
    fgroups = {}
    for r in fc:
        for c in (r["snapshot"], "all"):
            for k in (r["level"], "all"):
                fgroups.setdefault((r["judge"], r["variant"], c, k), []).append(r)
    for (jm, variant, c, k), rs in sorted(fgroups.items(), key=str):
        n, hit = len(rs), sum(r["hit"] for r in rs)
        lo, hi = wilson(hit, n)
        cell = dict(snapshot=None if c == "all" else c, level=None if k == "all" else k, stratum=jm, split="forced_choice")
        out_rows.append(row("E3", "identification_rate", variant, hit / n, ci_lo=lo, ci_hi=hi, n=n, k=hit, **cell))
        out_rows.append(row("E3", "over_claim_rate", variant, 1 - hit / n, ci_lo=1 - hi, ci_hi=1 - lo, n=n, k=n - hit, **cell))
        out_rows.append(row("E3", "identification_chance_corrected", variant, (hit / n - 0.25) / 0.75,
                            ci_lo=(lo - 0.25) / 0.75, ci_hi=(hi - 0.25) / 0.75, n=n, **cell))
        if c == "all" and k == "all":
            pos = {L: sum(r["choice"] == L for r in rs) / n for L in "ABCD"}
            out_rows.append(row("E3", "choice_position_max_share", variant, max(pos.values()), n=n, **cell, positions=pos))
    for jm in judges:
        mm = fgroups[(jm, "model", 2026, "all")]
        nn = fgroups[(jm, "random-labels", 2026, "all")]
        hm, hn = sum(r["hit"] for r in mm), sum(r["hit"] for r in nn)
        _, p = sps.fisher_exact([[hm, len(mm) - hm], [hn, len(nn) - hn]], alternative="greater")
        tests.append({"name": f"E3 forced-choice identification model vs random-labels ({jm})", "family": "E3",
                      "metric": "identification_rate", "cell": {"snapshot": 2026, "level": "0-1", "judge": jm},
                      "model": hm / len(mm), "null": "random-labels", "statistic": None, "p": float(p),
                      "null_mean": hn / len(nn), "R": 1, "primary": jm == cfg.labels["judge_model"]})
        b = sps.binomtest(hm, len(mm), 0.25, alternative="greater")
        tests.append({"name": f"E3 forced-choice identification model vs chance ({jm})", "family": "E3",
                      "metric": "identification_rate", "cell": {"snapshot": 2026, "level": "0-1", "judge": jm},
                      "model": hm / len(mm), "null": "chance 0.25", "statistic": None, "p": float(b.pvalue),
                      "null_mean": 0.25, "R": 1, "primary": False})
    rows += fc
    (Path(out) / "label_judgements.json").write_text(json.dumps(rows, indent=1, ensure_ascii=False) + "\n")


# ---------------------------------------------------------------- E4

def e4(tkh, cfg, ev, model, variants, null_parts, rl, out_rows, tests, log):
    qs = load_questions(cfg.questions)
    targets = question_targets(tkh, load_ground_truth(cfg.ground_truth), CONCEPT_TYPES)
    index = Index(tkh, 2026)
    n_items = len(index.items)
    hf = ev["eval"]["hub_frac"]
    per_q = {}

    def add(name, rs):
        cost = penalised_first_cost(rs, n_items)
        per_q[name] = dict(zip([r["question"] for r in rs], cost))
        return cost, rs

    def summary_rows(name, cost, rs):
        rng = np.random.default_rng(0)
        idx = [rng.integers(0, len(rs), len(rs)) for _ in range(1000)]
        med = [float(np.median(np.asarray(cost)[i])) for i in idx]
        out_rows.append(row("E4", "first_cost_median", name, float(np.median(cost)), 2026, ci_lo=np.quantile(med, 0.025),
                            ci_hi=np.quantile(med, 0.975), n=len(rs)))
        for m in ("recall@50", "recall@200", "wrong@200"):
            v = np.array([r[m] for r in rs], float)
            bs = [float(v[i].mean()) for i in idx]
            out_rows.append(row("E4", m, name, float(v.mean()), 2026, ci_lo=np.quantile(bs, 0.025), ci_hi=np.quantile(bs, 0.975), n=len(rs)))
        out_rows.append(row("E4", "found_any", name, sum(r["first_cost"] is not None for r in rs) / len(rs), 2026, n=len(rs)))

    base = e4_evaluate(tkh, 2026, model[2026], qs, targets, baselines=True, hub_frac=hf, index=index)
    for meth, name in (("hierarchy", "model"), ("flat", "flat-lexical"), ("ppr", "ppr")):
        rs = [r for r in base if r["method"] == meth]
        summary_rows(name, *add(name, rs))
    for name, parts in variants.items():
        if name == "model":
            continue
        summary_rows(name, *add(name, e4_evaluate(tkh, 2026, parts[2026], qs, targets, baselines=False, index=index)))
    nulls = {}
    for kind, plist in {**{f"{k}-null": v for k, v in null_parts.items()},
                        "random-labels": [permute_hierarchy(model, tkh, s, list(cfg.cutoffs)) for s in range(ev["nulls"]["random_labels_R_e4"])]}.items():
        for parts in plist:
            rs = e4_evaluate(tkh, 2026, parts[2026], qs, targets, baselines=False, index=index)
            nulls.setdefault(kind, []).append(rs)
        meds = [float(np.median(penalised_first_cost(rs, n_items))) for rs in nulls[kind]]
        out_rows.append(null_rows("E4", "first_cost_median", kind, meds, snapshot=2026))
        for m in ("recall@50", "recall@200", "wrong@200"):
            out_rows.append(null_rows("E4", m, kind, [float(np.mean([r[m] for r in rs])) for rs in nulls[kind]], snapshot=2026))
        cmp_ = null_compare(float(np.median(list(per_q["model"].values()))), meds, higher_is_better=False)
        tests.append({"name": f"E4 median cost model vs {kind}", "family": "E4", "metric": "first_cost_median",
                      "cell": {"snapshot": 2026}, "model": float(np.median(list(per_q["model"].values()))), "null": kind,
                      "statistic": cmp_["z"], "p": cmp_["p"], "null_mean": cmp_["null_mean"], "R": cmp_["R"], "primary": False})
    log("E4")
    qorder = sorted(per_q["model"])
    for other, primary in (("flat-lexical", True), ("ppr", False)):
        a = [per_q[other][q] for q in qorder]
        b = [per_q["model"][q] for q in qorder]
        tests.append({"name": f"E4 cost hierarchy vs {other}", "family": "E4", "metric": "first_cost",
                      "cell": {"snapshot": 2026}, "model": float(np.median(b)), "null": other, "statistic": None,
                      "p": wilcoxon_paired(a, b, "greater"), "null_mean": float(np.median(a)), "R": len(qorder), "primary": primary})
    return per_q


# ---------------------------------------------------------------- main

def main(argv=None):
    p = add_config_args(argparse.ArgumentParser(description=__doc__.split("\n")[0]))
    p.add_argument("--eval", type=Path, default=ROOT / "configs" / "eval.toml")
    p.add_argument("--out", type=Path, help="output directory (default: the config's out_dir)")
    p.add_argument("--skip-e3", action="store_true", help="skip the LLM judge (E3)")
    args = p.parse_args(argv)
    cfg = config_from_args(args)
    out = Path(args.out or cfg.out_dir)
    sel = json.loads((out / "selection.json").read_text())
    ev = load_eval(args.eval, sel.get("fast", False))
    t0 = time.perf_counter()
    log = lambda m: print(f"[{time.perf_counter() - t0:6.0f}s] {m}", flush=True)  # noqa: E731
    tkh = load(cfg)
    cs = list(cfg.cutoffs)

    model = concept_only(read_partitions(out, cs), tkh)
    winner, _ = runs.load(runs.run_path(out, "config", sel["winner"]))
    same = all(sorted(map(sorted, model[c][k].values())) == sorted(map(sorted, winner[c][k].values()))
               for c in cs for k in range(len(cfg.budgets)))
    if not same:
        raise SystemExit(f"{out}/<cutoff>/hierarchy.json does not match the selected configuration {sel['winner']}; run make build")
    variants = {"model": model}
    for cid in sorted(set(sel["configs"]) | {a["cid"] for a in sel["ablations"].values()}):
        if cid != sel["winner"]:
            variants[cid] = runs.load(runs.run_path(out, "config", cid))[0]
    null_parts = {k: [runs.load(runs.run_path(out, "null", k, s))[0] for s in range(sel["nulls"]["R"])] for k in sel["nulls"]["kinds"]}
    log(f"loaded {len(variants)} variants and {sum(map(len, null_parts.values()))} null builds")

    rows, tests = [], []
    for r in sel["table"]:
        rows.append(row("selection", "coupling_lift_halfA", r["cid"], r["value"], sel["protocol"]["snapshot"], sel["protocol"]["level"],
                        sel["protocol"]["stratum"], "A", ci_lo=r["value"] - (r["se"] or 0), ci_hi=r["value"] + (r["se"] or 0),
                        alpha=r["alpha"], eligible=r["eligible"], within_1se=r["within_1se"], giant_share=r["giant_share"]))
    rows.append(row("selection", "winner_agreement", sel["winner"], sel["stability"]["agreement"], n=len(sel["stability"]["winners"])))
    for name, parts in variants.items():
        for c in cs:
            sizes = [len(m) for m in parts[c][0].values()]
            rows.append(row("structure", "giant_share_level0", name, max(sizes) / sum(sizes), c, 0, n=sum(sizes)))

    rl = e1(tkh, cfg, ev, model, variants, null_parts, rows, tests, log)
    e2(tkh, cfg, ev, out, sel, variants, null_parts, rows, tests, log)
    if not args.skip_e3:
        e3(tkh, cfg, ev, out, model, rows, tests, log)
    e4(tkh, cfg, ev, model, variants, null_parts, rl, rows, tests, log)

    adj = holm({t["name"]: t["p"] for t in tests if t["primary"]})
    for t in tests:
        t["p_holm"] = adj.get(t["name"]) if t["primary"] else None
    meta = {"selected": sel["winner"], "selected_params": sel["selected_params"], "fast": sel.get("fast", False),
            "null_R": sel["nulls"]["R"], "random_labels_R": ev["nulls"]["random_labels_R"],
            "random_labels_R_e4": ev["nulls"]["random_labels_R_e4"], "perturbation_seeds": ev["stability"]["seeds"],
            "labels": {k: cfg.labels.get(k) for k in ("labeller_model", "judge_model")}, "e3": not args.skip_e3,
            "configs": {cid: p["alpha"] for cid, p in sel["configs"].items()},
            "ablations": {name: a["cid"] for name, a in sel["ablations"].items()}}
    (out / "metrics.json").write_text(json.dumps({"meta": meta, "rows": rows, "tests": tests}, indent=1) + "\n")
    log(f"{len(rows)} rows, {len(tests)} tests -> {out / 'metrics.json'}")


if __name__ == "__main__":
    main()
