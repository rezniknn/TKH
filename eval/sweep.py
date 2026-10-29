"""α sweep: the structure-semantics trade-off of P3, every other parameter at its configured default.

sweep(cfg, base, alphas, out_dir) builds one full run per α in out_dir/<α>/ (tkh/pipeline.run: hierarchy, ids,
events, labels) and computes the four checks on it with the main run's protocol, each from the run's own
run_config.toml, exactly as `python -m eval <check>` does:
  coherence     eval/experiments.coherence_check (R configuration-null rebuilds at that α, R_labels random labels)
  stability     eval/stability.stability_check (perturbation seeds, new-paper null R)
  faithfulness  eval/faithfulness.faithfulness_check (new labels need TKH_LLM_MODE=live once; then cache replay)
  retrieval     eval/retrieval.retrieval_check
-> out_dir/<α>/metrics.json (the layout of out/metrics.json), faithfulness_judgements.json, retrieval_answers.json.

summarise(cfg, out_dir, alphas, ref) -> the "alpha_sweep" section of the main run's metrics.json (cfg.out_dir), the
only source of the sweep numbers that make_tables.py and eval/figures.py read:
  protocol      alphas, the reference α (REFERENCE, the default before the sweep), cutoffs, the fixed non-α parameters
                (asserted identical across runs), the per-α evaluation protocols, the run directories, and how the
                variant at the main run's α compares with the main run (hierarchy.json bytes at summarise time; content
                hashes of its four metric sections, which make_tables.py compares with the main run's current ones)
  variants.<α>  per criterion the values the comparison needs, with the verdict rules of eval/verdicts.py:
                coherence cells (verdict, schemes passed, interval-scheme lift and CI per filter), robust and
                below-null cells; perturbation HARI per snapshot, cross-snapshot indices above the new-paper null,
                localised cells and untouched share; over-claim overall and per level; retrieval per type and measure
                and the favour counts; tree statistics; and the comparisons with the reference that need the trees:
    tree.ari_vs_reference   ARI per snapshot and level between the α tree and the reference tree (concept nodes)
    paired.perturbation     HARI difference per snapshot, paired by seed (the same removed edges): mean, t-interval
    paired.cross_snapshot   HARI difference per transition, paired by node half-subsample: mean, percentile interval
Eligibility, the recommendation and the trade-off verdicts are computed from this section by make_tables.py.
"""

from pathlib import Path
import json

import numpy as np
from sklearn.metrics import adjusted_rand_score

from eval.experiments import _concept_levels, _finite, coherence_check
from eval.faithfulness import faithfulness_check
from eval.retrieval import retrieval_check
from eval.stability import _labels, hari, stability_check, t_interval
from eval import verdicts as V
from tkh.coarsen import concept_nodes
from tkh.config import REPO_ROOT, load_config
from tkh.hierarchy import Params
from tkh.io import load, snapshot
from tkh.pipeline import run

ALPHAS = (0.0, 0.25, 0.5, 0.75, 1.0)
REFERENCE = 0.5   # the configured default before the sweep: the reference of the paired comparisons and the rule
QUESTIONS, GT = REPO_ROOT / "data" / "questions.csv", REPO_ROOT / "data" / "ground_truth.json"


def _dir(out_dir, a):
    return Path(out_dir) / f"{a:g}"


def run_alpha(cfg, base, alpha, out_dir, R=99, R_labels=999, seeds=5, n_jobs=8):
    d = _dir(out_dir, alpha)
    run(cfg, Params.from_config({**base.as_dict(), "alpha": alpha}), d)
    rc = load_config(d / "run_config.toml")
    params = Params.from_config(rc.method)
    metrics = {"coherence": coherence_check(rc, params, d, R, R_labels, n_jobs),
               "stability": stability_check(rc, params, d, range(seeds), R=R, n_jobs=n_jobs)}
    metrics["faithfulness"], recs = faithfulness_check(rc, d)
    metrics["retrieval"], answers = retrieval_check(load(rc), d, rc.cutoffs, QUESTIONS, GT)
    (d / "faithfulness_judgements.json").write_text(json.dumps(recs, indent=1, ensure_ascii=False) + "\n")
    (d / "retrieval_answers.json").write_text(json.dumps(answers, indent=1, ensure_ascii=False) + "\n")
    (d / "metrics.json").write_text(json.dumps(metrics, indent=1, allow_nan=False) + "\n")


def sweep(cfg, base, alphas=ALPHAS, out_dir=None, n_jobs=8):
    out_dir = Path(out_dir or Path(cfg.out_dir) / "sweep")
    for a in alphas:
        run_alpha(cfg, base, a, out_dir, n_jobs=n_jobs)
        print(f"alpha {a:g} -> {_dir(out_dir, a)}", flush=True)
    return summarise(cfg, out_dir, alphas)


def write_section(path, name, value):
    """Read-modify-write one section of a metrics.json (the other sections are kept as they are)."""
    path = Path(path)
    metrics = json.loads(path.read_text()) if path.exists() else {}
    metrics[name] = value
    path.write_text(json.dumps(metrics, indent=1, allow_nan=False) + "\n")


def _variant(m, info, rc):
    """The comparison values of one variant, from its metrics.json, run_info.json and resolved config."""
    coh, cs = m["coherence"]["snapshots"], V.cutoffs(m)
    cells = {c: [{f: {"verdict": V.verdict(lv[f], coh[c]["coverage"][f]["period_strata"]), "schemes_passed": V.passes(lv[f]),
                      "lift": lv[f]["interval"]["lift"], "ci95": lv[f]["interval"]["ci95"]} for f in ("exact", "fuzzy")}
                 for lv in coh[c]["levels"]] for c in cs}
    st = m["stability"]
    above, idx = V.above_null(m)
    nloc, loc = V.localised(m)
    share = [x for x in map(V.untouched_share, loc) if x is not None]
    fa = m["faithfulness"]
    oc = lambda x: {"value": x["over_claim"]["value"], "ci95": x["over_claim"]["ci95"], "n": x["over_claim"]["n"]}
    ret = {t: {k: {x: s[k][x] for x in ("n", "hier", "flat", "hier_minus_flat")} for k in V.RETRIEVAL_NAMES if k in s}
           for t, s in m["retrieval"]["summary"].items()}
    last = info["snapshots"][str(cs[-1])]["levels"]
    return {"protocol": {"coherence": {"R": m["coherence"]["R"], "R_labels": m["coherence"]["R_labels"]},
                         "stability": st["protocol"],
                         "labels": {"labeller_model": rc.labels["labeller_model"], "judge_model": rc.labels["judge_model"]},
                         "retrieval": {"beam": m["retrieval"]["config"]["beam"], "k": m["retrieval"]["config"]["k"]}},
            "coherence": {"cells": cells, "n_cells": sum(len(v) for v in cells.values()),
                          "robust": {f: V.robust(m, f) for f in ("exact", "fuzzy")},
                          "below": {f: V.below_cells(m, f) for f in ("exact", "fuzzy")}},
            "stability": {"perturbation_hari": {c: st["perturbation"][c]["hari"] for c in st["perturbation"]},
                          "above_null": [above, len(idx)], "localised": [nloc, len(loc)],
                          "untouched_share": [min(share), max(share)] if share else None},
            "faithfulness": {"over_claim": oc(fa), "by_level": {k: oc(v) for k, v in fa["by_level"].items()},
                             "claim_unsupported": fa["claim_unsupported"],
                             "named_non_member": fa["deterministic"]["named_non_member"]},
            "retrieval": {"summary": ret, "favour": V.favour_counts(m)},
            "tree": {"last": [{k: lv[k] for k in ("merges", "linked", "max_size", "cap", "singletons")} for lv in last]}}


def _rel(d, base):
    d, base = Path(d).resolve(), Path(base).resolve()
    return str(d.relative_to(base)) if d.is_relative_to(base) else str(d)


def summarise(cfg, out_dir, alphas=ALPHAS, ref=REFERENCE, n_sub=200):
    out_dir, alphas, main = Path(out_dir), sorted(alphas), Path(cfg.out_dir)
    tkh = load(cfg)
    cs = sorted(cfg.cutoffs)
    concept = {c: set(concept_nodes(tkh, snapshot(tkh, c))) for c in cs}
    trees = {a: {c: [{k: m & concept[c] for k, m in lv.items()} for lv in
                     _concept_levels(json.loads((_dir(out_dir, a) / str(c) / "hierarchy.json").read_text()))] for c in cs}
             for a in alphas}
    mets = {a: json.loads((_dir(out_dir, a) / "metrics.json").read_text()) for a in alphas}
    infos = {a: json.loads((_dir(out_dir, a) / "run_info.json").read_text()) for a in alphas}
    fixed = {a: {k: v for k, v in infos[a]["params"].items() if k != "alpha"} for a in alphas}
    assert all(x == fixed[ref] for x in fixed.values()), f"sweep runs differ in more than alpha: {fixed}"
    assert all(infos[a]["params"]["alpha"] == a for a in alphas)
    assert all(infos[a]["budgets"] == infos[ref]["budgets"] for a in alphas)
    res = {}
    for a in alphas:
        nodes = {c: sorted(concept[c]) for c in cs}
        v = _variant(mets[a], infos[a], load_config(_dir(out_dir, a) / "run_config.toml"))
        v["tree"]["ari_vs_reference"] = {str(c): [float(adjusted_rand_score(_labels(x, nodes[c]), _labels(y, nodes[c])))
                                                  for x, y in zip(trees[a][c], trees[ref][c])] for c in cs}
        pert = {str(c): t_interval(np.subtract(mets[a]["stability"]["perturbation"][str(c)]["per_seed_hari"],
                                               mets[ref]["stability"]["perturbation"][str(c)]["per_seed_hari"])) for c in cs}
        cross = {}
        for c0, c1 in zip(cs, cs[1:]):
            common = np.asarray(nodes[c0])
            rng = np.random.default_rng(0)
            d = []
            for _ in range(n_sub):
                sub = list(rng.choice(common, len(common) // 2, replace=False))
                d.append(hari(trees[a][c0], trees[a][c1], sub) - hari(trees[ref][c0], trees[ref][c1], sub))
            cross[f"{c0}-{c1}"] = {"mean": float(np.mean(d)), "ci95": [float(np.percentile(d, 2.5)), float(np.percentile(d, 97.5))]}
        v["paired"] = {"perturbation": pert, "cross_snapshot": cross}
        res[f"{a:g}"] = v
    path = main / "metrics.json"
    main_m = json.loads(path.read_text()) if path.exists() else {}
    da = main_m.get("coherence", {}).get("params", {}).get("alpha")
    match = None
    if da in alphas:
        same = [c for c in cs if (_dir(out_dir, da) / str(c) / "hierarchy.json").read_bytes()
                == (main / str(c) / "hierarchy.json").read_bytes()]
        match = {"alpha": da, "hierarchy_identical": len(same), "snapshots": len(cs),
                 "section_sha256": {k: V.section_hash(v) for k, v in mets[da].items()}}
    out = _finite({"protocol": {"alphas": [float(a) for a in alphas], "reference": float(ref), "cutoffs": cs,
                                "fixed": fixed[ref], "budgets": infos[ref]["budgets"], "runs": {f"{a:g}": _rel(_dir(out_dir, a), main) for a in alphas},
                                "main_run": match},
                   "variants": res})
    write_section(path, "alpha_sweep", out)
    return out
