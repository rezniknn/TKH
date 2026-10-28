"""Command line of the evaluation: python -m eval {coherence,stability,labels,retrieval,retrieval-sweep,gamma,sweep}.

  coherence  --run DIR [--R 99] [--R-labels 999]   held-out coherence per snapshot and level, unadjusted and
                                                   period-adjusted, against both nulls -> DIR/metrics.json "coherence"
  stability  --run DIR [--seeds 5] [--R 19]        perturbation and cross-snapshot stability (ARI, HARI, CIs,
                                                   new-paper null), change localisation, events -> "stability"
  labels     --run DIR [--rigor standard]          label faithfulness: held-out NLI judge, controls, nulls -> "labels"
                                                   (rigor: quick | standard | full; judgements -> DIR/label_judgements.json)
  retrieval  --run DIR [--beam 3 4 5] [--k 10]     T6 extrinsic utility: drill-down retrieval agent vs flat search on
                                                   data/questions.csv, scored with data/ground_truth.json (hit-rate,
                                                   steps-to-target) -> "retrieval"; answers -> DIR/retrieval_answers.json
  retrieval-sweep --run DIR                       staged experiments over the agent's settings -> DIR/retrieval_experiments.json
                                                   and docs/figures/retrieval_pareto.png (the hierarchy is not changed)
  gamma      [--out DIR] [--param k=v ...]         temporal-prior variants gamma = 0 ... 1: stability and coherence
                                                   per variant, paired differences to gamma = 0 -> DIR/gamma.json
  sweep      --out FILE [--param k=v ...]          configuration grid and one-SE selection on cited-work halves
coherence, stability, labels and retrieval use the run's own run_config.toml and refuse null-model runs; each updates its own section of
metrics.json.
"""

from pathlib import Path
import argparse
from dataclasses import replace
import json

from eval.experiments import coherence_check, sweep
from eval.labels import RIGOR, label_check
from eval.retrieval import retrieval_check
from eval.retrieval_experiments import pareto_figure, sweep as retrieval_sweep
from eval.stability import gamma_tradeoff, stability_check
from tkh.config import REPO_ROOT, add_config_args, config_from_args, load_config, parse_overrides
from tkh.io import load
from tkh.retrieve import LEAF_INFO, NODE_INFO, QUERY, SCORERS, Settings
from tkh.hierarchy import Params


def main(argv=None):
    ap = argparse.ArgumentParser(prog="python -m eval", description=__doc__.split("\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name in ("coherence", "stability"):
        p = sub.add_parser(name)
        p.add_argument("--run", type=Path, required=True)
        p.add_argument("--R", type=int, default=99)
        p.add_argument("--jobs", type=int, default=8)
        if name == "coherence":
            p.add_argument("--R-labels", type=int, default=999)
        else:
            p.add_argument("--seeds", type=int, default=5)
    p = sub.add_parser("labels")
    p.add_argument("--run", type=Path, required=True)
    p.add_argument("--rigor", choices=sorted(RIGOR), default="standard")
    p.add_argument("--cutoffs", type=int, nargs="*", help="override the rigor's snapshots")
    p.add_argument("--levels", type=int, nargs="*", help="override the rigor's levels")
    p.add_argument("--no-nulls", action="store_true", help="judge the run only (prompt iteration)")
    p.add_argument("--relabel", action="store_true", help="relabel the run's tree with the current labeller prompt")
    p.add_argument("--prompts", type=Path, help="prompt directory to use instead of the configured one (comparisons)")
    p.add_argument("--tag", help="write metrics and judgements to DIR/label_dev/<tag>.json instead (iteration log)")
    p = sub.add_parser("retrieval")
    p.add_argument("--run", type=Path, required=True)
    p.add_argument("--questions", type=Path, default=REPO_ROOT / "data" / "questions.csv")
    p.add_argument("--gt", type=Path, default=REPO_ROOT / "data" / "ground_truth.json")
    d = Settings()
    p.add_argument("--beam", type=int, nargs="+", default=list(d.beam), help="super-nodes kept (or cap) per level, L0 first")
    p.add_argument("--rel", type=float, default=d.rel, help="keep children scoring >= rel x the level's best")
    p.add_argument("--min-keep", type=int, default=d.min_keep)
    p.add_argument("--node-info", choices=NODE_INFO, default=d.node_info)
    p.add_argument("--leaf-info", choices=LEAF_INFO, default=d.leaf_info)
    p.add_argument("--scorer", choices=SCORERS, default=d.scorer)
    p.add_argument("--query", choices=QUERY, default=d.query)
    p.add_argument("--k", type=int, default=d.k, help="answer length (methods or claims)")
    p = sub.add_parser("retrieval-sweep")
    p.add_argument("--run", type=Path, required=True)
    p.add_argument("--figure", type=Path, default=REPO_ROOT / "docs" / "figures" / "retrieval_pareto.png")
    for name in ("gamma", "sweep"):
        p = add_config_args(sub.add_parser(name))
        p.add_argument("--param", nargs="*", help="override [method] parameters of the base configuration")
        p.add_argument("--out", type=Path)
        p.add_argument("--jobs", type=int, default=8)
    args = ap.parse_args(argv)

    if args.cmd == "retrieval-sweep":
        cfg = load_config(args.run / "run_config.toml")
        res = retrieval_sweep(load(cfg), args.run, cfg.cutoffs)
        out = args.run / "retrieval_experiments.json"
        out.write_text(json.dumps(res, indent=1, allow_nan=False) + "\n")
        pareto_figure(res, args.figure)
        print(f"retrieval-sweep -> {out}, {args.figure}; best: {res['best']}")
        return
    if args.cmd in ("coherence", "stability", "labels", "retrieval"):   # the run's own resolved config, so the check uses exactly its inputs
        if "null" in json.loads((args.run / "run_info.json").read_text()):
            raise SystemExit(f"{args.run} is a null-model run: the checks evaluate real runs")
        cfg = load_config(args.run / "run_config.toml")
        params = Params.from_config(cfg.method)
        if args.cmd == "coherence":
            res, section = coherence_check(cfg, params, args.run, args.R, args.R_labels, args.jobs), "coherence"
        elif args.cmd == "labels":
            if args.relabel:   # the current labeller settings (configs/default.toml), not the run's
                cfg = replace(cfg, labels={**cfg.labels, **load_config().labels})
            if args.prompts:
                cfg = replace(cfg, labels={**cfg.labels, "prompts": str(args.prompts.resolve())})
            res, recs = label_check(cfg, params, args.run, args.rigor, args.cutoffs, args.levels, not args.no_nulls, args.relabel)
            if args.tag:
                d = args.run / "label_dev"
                d.mkdir(exist_ok=True)
                (d / f"{args.tag}.json").write_text(json.dumps({"metrics": res, "judgements": recs}, indent=1, ensure_ascii=False) + "\n")
                print(f"labels -> {d / (args.tag + '.json')}")
                return
            section = "labels"
            (args.run / "label_judgements.json").write_text(json.dumps(recs, indent=1, ensure_ascii=False) + "\n")
        elif args.cmd == "retrieval":
            st = Settings(beam=tuple(args.beam), rel=args.rel, min_keep=args.min_keep, node_info=args.node_info,
                          leaf_info=args.leaf_info, scorer=args.scorer, query=args.query, k=args.k)
            res, answers = retrieval_check(load(cfg), args.run, cfg.cutoffs, args.questions, args.gt, st)
            section = "retrieval"
            (args.run / "retrieval_answers.json").write_text(json.dumps(answers, indent=1, ensure_ascii=False) + "\n")
        else:
            res, section = stability_check(cfg, params, args.run, range(args.seeds), R=args.R, n_jobs=args.jobs), "stability"
        path = args.run / "metrics.json"
        metrics = json.loads(path.read_text()) if path.exists() else {}
        metrics[section] = res
        path.write_text(json.dumps(metrics, indent=1, allow_nan=False) + "\n")
        print(f"{section} -> {path}")
        return
    cfg = config_from_args(args)
    base = Params.from_config({**cfg.method, **parse_overrides(args.param)})
    if args.cmd == "gamma":
        res = gamma_tradeoff(cfg, base, out_dir=args.out, n_jobs=args.jobs)
        out = (args.out or cfg.out_dir / "gamma") / "gamma.json"
    else:
        res = sweep(cfg, base, n_jobs=args.jobs)
        out = args.out or cfg.out_dir / "sweep.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(res, indent=1, allow_nan=False) + "\n")
    print(f"{args.cmd} -> {out}")

if __name__ == "__main__":
    main()
