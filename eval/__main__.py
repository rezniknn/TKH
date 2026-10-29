"""Command line of the evaluation: python -m eval {coherence,stability,faithfulness,retrieval,gamma,sweep}.

  coherence  --run DIR [--R 99] [--R-labels 999]   held-out coherence per snapshot and level, unadjusted and
                                                   period-adjusted, against both nulls -> DIR/metrics.json "coherence"
  stability  --run DIR [--seeds 5] [--R 19]        perturbation and cross-snapshot stability (ARI, HARI, CIs,
                                                   new-paper null), change localisation, events -> "stability"
  faithfulness --run DIR [--relabel] [--prompts D] label faithfulness: held-out NLI judge on every L0-L1 label ->
                                                   "faithfulness"; judgements -> DIR/faithfulness_judgements.json
                                                   (--relabel/--prompts/--cutoffs/--levels: DIR/faithfulness_dev.json)
  retrieval  --run DIR [--beam 10 20 40] [--k 10]  T6 extrinsic utility: drill-down retrieval agent vs flat search on
                                                   data/questions.csv, scored with data/ground_truth.json (hit-rate,
                                                   error rate, items inspected, candidates scored) -> "retrieval";
                                                   answers and resolved gold -> DIR/retrieval_answers.json
  gamma      [--out DIR] [--param k=v ...]         temporal-prior variants gamma = 0 ... 1: stability and coherence
                                                   per variant, paired differences to gamma = 0 -> DIR/gamma.json
  sweep      [--out DIR] [--alphas ...] [--summarise-only]
                                                   alpha sweep, every other parameter at its default: a full run and the
                                                   four checks per alpha -> DIR/<alpha>/metrics.json; the comparison
                                                   (headlines, verdicts, paired differences to the pre-sweep default)
                                                   -> the "alpha_sweep" section of the main metrics.json (eval/sweep.py)
coherence, stability, faithfulness and retrieval use the run's own run_config.toml and refuse null-model runs; each updates its own section of
metrics.json.
"""

from pathlib import Path
import argparse
from dataclasses import replace
import json

from eval.experiments import coherence_check
from eval.faithfulness import faithfulness_check
from eval.retrieval import retrieval_check
from eval.stability import gamma_tradeoff, stability_check
from eval.sweep import ALPHAS, summarise, sweep
from tkh.config import REPO_ROOT, add_config_args, config_from_args, load_config, parse_overrides
from tkh.io import load
from tkh.retrieve import BEAM, K
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
    p = sub.add_parser("faithfulness")
    p.add_argument("--run", type=Path, required=True)
    p.add_argument("--cutoffs", type=int, nargs="*", help="snapshots to judge (default: all)")
    p.add_argument("--levels", type=int, nargs="*", help="levels to judge (default: the labelled levels 0-1)")
    p.add_argument("--relabel", action="store_true", help="relabel the run's tree with the current labeller prompt")
    p.add_argument("--prompts", type=Path, help="prompt directory to use instead of the configured one; with --relabel, --cutoffs or --levels the run goes to DIR/faithfulness_dev.json")
    p = sub.add_parser("retrieval")
    p.add_argument("--run", type=Path, required=True)
    p.add_argument("--questions", type=Path, default=REPO_ROOT / "data" / "questions.csv")
    p.add_argument("--gt", type=Path, default=REPO_ROOT / "data" / "ground_truth.json")
    p.add_argument("--beam", type=int, nargs="+", default=list(BEAM), help="super-nodes kept per level, L0 first")
    p.add_argument("--k", type=int, default=K, help="answer length (methods or claims)")
    for name in ("gamma", "sweep"):
        p = add_config_args(sub.add_parser(name))
        p.add_argument("--param", nargs="*", help="override [method] parameters of the base configuration")
        p.add_argument("--out", type=Path)
        p.add_argument("--jobs", type=int, default=8)
        if name == "sweep":
            p.add_argument("--alphas", type=float, nargs="+", default=list(ALPHAS))
            p.add_argument("--summarise-only", action="store_true", help="only recompute the alpha_sweep section from the runs")
    args = ap.parse_args(argv)

    if args.cmd in ("coherence", "stability", "faithfulness", "retrieval"):   # the run's own resolved config, so the check uses exactly its inputs
        if "null" in json.loads((args.run / "run_info.json").read_text()):
            raise SystemExit(f"{args.run} is a null-model run: the checks evaluate real runs")
        cfg = load_config(args.run / "run_config.toml")
        params = Params.from_config(cfg.method)
        if args.cmd == "coherence":
            res, section = coherence_check(cfg, params, args.run, args.R, args.R_labels, args.jobs), "coherence"
        elif args.cmd == "faithfulness":
            if args.relabel:   # the current labeller settings (configs/default.toml), not the run's
                cfg = replace(cfg, labels={**cfg.labels, **load_config().labels})
            if args.prompts:
                cfg = replace(cfg, labels={**cfg.labels, "prompts": str(args.prompts.resolve())})
            res, recs = faithfulness_check(cfg, args.run, args.cutoffs, args.levels, args.relabel)
            if args.relabel or args.prompts or args.cutoffs or args.levels:   # an iteration run: keep the main results
                dev = args.run / "faithfulness_dev.json"
                dev.write_text(json.dumps({"metrics": res, "judgements": recs}, indent=1, ensure_ascii=False) + "\n")
                print(f"faithfulness (iteration run) -> {dev}")
                return
            section = "faithfulness"
            (args.run / "faithfulness_judgements.json").write_text(json.dumps(recs, indent=1, ensure_ascii=False) + "\n")
        elif args.cmd == "retrieval":
            res, answers = retrieval_check(load(cfg), args.run, cfg.cutoffs, args.questions, args.gt, args.beam, args.k)
            section = "retrieval"
            (args.run / "retrieval_answers.json").write_text(json.dumps(answers, indent=1, ensure_ascii=False) + "\n")
        else:
            res, section = stability_check(cfg, params, args.run, range(args.seeds), R=args.R, n_jobs=args.jobs), "stability"
        path = args.run / "metrics.json"
        metrics = json.loads(path.read_text()) if path.exists() else {}
        metrics[section] = res
        if section == "faithfulness":
            metrics.pop("labels", None)   # the earlier label check (controls, nulls) it replaces
        path.write_text(json.dumps(metrics, indent=1, allow_nan=False) + "\n")
        print(f"{section} -> {path}")
        return
    cfg = config_from_args(args)
    base = Params.from_config({**cfg.method, **parse_overrides(args.param)})
    if args.cmd == "gamma":
        res = gamma_tradeoff(cfg, base, out_dir=args.out, n_jobs=args.jobs)
        out = (args.out or cfg.out_dir / "gamma") / "gamma.json"
    else:
        d = args.out or cfg.out_dir / "sweep"
        if args.summarise_only:
            summarise(cfg, d, args.alphas)
        else:
            sweep(cfg, base, args.alphas, d, n_jobs=args.jobs)
        print(f"sweep -> {cfg.out_dir / 'metrics.json'} (alpha_sweep)")
        return
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(res, indent=1, allow_nan=False) + "\n")
    print(f"{args.cmd} -> {out}")

if __name__ == "__main__":
    main()
