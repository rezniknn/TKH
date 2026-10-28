"""α sweep: the structure-semantics trade-off of P3, every other parameter at its configured default.

sweep(cfg, base, alphas, out_dir) builds one full run per α in out_dir/<α>/ (tkh/pipeline.run: hierarchy, ids,
events, labels) and computes the four checks on it with the main run's protocol, each from the run's own
run_config.toml, exactly as `python -m eval <check>` does:
  coherence     eval/experiments.coherence_check (R configuration-null rebuilds at that α, R_labels random labels)
  stability     eval/stability.stability_check (perturbation seeds, new-paper null R)
  faithfulness  eval/faithfulness.faithfulness_check (new labels need TKH_LLM_MODE=live once; then cache replay)
  retrieval     eval/retrieval.retrieval_check
-> out_dir/<α>/metrics.json (the layout of out/metrics.json), faithfulness_judgements.json, retrieval_answers.json.

summarise(out_dir, alphas, ref) -> out_dir/sweep.json: the runs and, against the reference α (the default), the
comparisons that need the trees rather than metrics.json:
  tree_ari          ARI per snapshot and level between the α tree and the reference tree (concept nodes)
  perturbation      HARI difference per snapshot, paired by seed (the same removed edges): mean and t-interval
  cross_snapshot    HARI difference per transition, paired by node half-subsample: mean and percentile interval
Verdicts and the recommendation are computed from these files by make_tables.py, with the rules of the report.
"""

from pathlib import Path
import json

import numpy as np
from sklearn.metrics import adjusted_rand_score

from eval.experiments import _concept_levels, _finite, coherence_check
from eval.faithfulness import faithfulness_check
from eval.retrieval import retrieval_check
from eval.stability import _labels, hari, stability_check, t_interval
from tkh.coarsen import concept_nodes
from tkh.config import REPO_ROOT, load_config
from tkh.hierarchy import Params
from tkh.io import load, snapshot
from tkh.pipeline import run

ALPHAS = (0.0, 0.25, 0.5, 0.75, 1.0)
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
    return summarise(cfg, out_dir, alphas, base.alpha)


def summarise(cfg, out_dir, alphas=ALPHAS, ref=0.5, n_sub=200):
    out_dir, alphas = Path(out_dir), sorted(alphas)
    tkh = load(cfg)
    cs = sorted(cfg.cutoffs)
    concept = {c: set(concept_nodes(tkh, snapshot(tkh, c))) for c in cs}
    trees = {a: {c: [{k: m & concept[c] for k, m in lv.items()} for lv in
                     _concept_levels(json.loads((_dir(out_dir, a) / str(c) / "hierarchy.json").read_text()))] for c in cs}
             for a in alphas}
    stab = {a: json.loads((_dir(out_dir, a) / "metrics.json").read_text())["stability"] for a in alphas}
    res = {}
    for a in alphas:
        nodes = {c: sorted(concept[c]) for c in cs}
        tree_ari = {str(c): [float(adjusted_rand_score(_labels(x, nodes[c]), _labels(y, nodes[c])))
                             for x, y in zip(trees[a][c], trees[ref][c])] for c in cs}
        pert = {str(c): t_interval(np.subtract(stab[a]["perturbation"][str(c)]["per_seed_hari"],
                                               stab[ref]["perturbation"][str(c)]["per_seed_hari"])) for c in cs}
        cross = {}
        for c0, c1 in zip(cs, cs[1:]):
            common = np.asarray(nodes[c0])
            rng = np.random.default_rng(0)
            d = []
            for _ in range(n_sub):
                sub = list(rng.choice(common, len(common) // 2, replace=False))
                d.append(hari(trees[a][c0], trees[a][c1], sub) - hari(trees[ref][c0], trees[ref][c1], sub))
            cross[f"{c0}-{c1}"] = {"mean": float(np.mean(d)), "ci95": [float(np.percentile(d, 2.5)), float(np.percentile(d, 97.5))]}
        res[f"{a:g}"] = {"run": f"{a:g}", "tree_ari": tree_ari, "perturbation": pert, "cross_snapshot": cross}
    out = _finite({"alphas": [float(a) for a in alphas], "reference": float(ref), "cutoffs": cs, "variants": res})
    (out_dir / "sweep.json").write_text(json.dumps(out, indent=1, allow_nan=False) + "\n")
    return out
