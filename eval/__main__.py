"""Command line of the evaluation: python -m eval {p3,stability,gamma,sweep}.

  p3         --run DIR [--R 99] [--R-labels 999]   held-out P3 coherence per snapshot and level, unadjusted and
                                                   period-adjusted, against both nulls -> DIR/metrics.json "coherence"
  stability  --run DIR [--seeds 5] [--R 19]        perturbation and cross-snapshot stability (ARI, HARI, CIs,
                                                   new-paper null), change localisation, events -> "stability"
  labels     --run DIR [--rigor standard]          label faithfulness: held-out NLI judge, controls, nulls -> "labels"
                                                   (rigor: quick | standard | full; judgements -> DIR/label_judgements.json)
  gamma      [--out DIR] [--param k=v ...]         temporal-prior variants gamma = 0 ... 1: stability and coherence
                                                   per variant, paired differences to gamma = 0 -> DIR/gamma.json
  sweep      --out FILE [--param k=v ...]          configuration grid and one-SE selection on cited-work halves
p3 and stability use the run's own run_config.toml and refuse null-model runs; each updates its own section of
metrics.json.
"""

from pathlib import Path
import argparse
import json

from eval.experiments import p3_check, sweep
from eval.labels import RIGOR, label_check
from eval.stability import gamma_tradeoff, stability_check
from tkh.config import add_config_args, config_from_args, load_config, parse_overrides
from tkh.hierarchy import Params


def main(argv=None):
    ap = argparse.ArgumentParser(prog="python -m eval", description=__doc__.split("\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name in ("p3", "stability"):
        p = sub.add_parser(name)
        p.add_argument("--run", type=Path, required=True)
        p.add_argument("--R", type=int, default=99)
        p.add_argument("--jobs", type=int, default=8)
        if name == "p3":
            p.add_argument("--R-labels", type=int, default=999)
        else:
            p.add_argument("--seeds", type=int, default=5)
    p = sub.add_parser("labels")
    p.add_argument("--run", type=Path, required=True)
    p.add_argument("--rigor", choices=sorted(RIGOR), default="standard")
    for name in ("gamma", "sweep"):
        p = add_config_args(sub.add_parser(name))
        p.add_argument("--param", nargs="*", help="override [method] parameters of the base configuration")
        p.add_argument("--out", type=Path)
        p.add_argument("--jobs", type=int, default=8)
    args = ap.parse_args(argv)

    if args.cmd in ("p3", "stability", "labels"):   # the run's own resolved config, so the check uses exactly its inputs
        if "null" in json.loads((args.run / "run_info.json").read_text()):
            raise SystemExit(f"{args.run} is a null-model run: the checks evaluate real runs")
        cfg = load_config(args.run / "run_config.toml")
        params = Params.from_config(cfg.method)
        if args.cmd == "p3":
            res, section = p3_check(cfg, params, args.run, args.R, args.R_labels, args.jobs), "coherence"
        elif args.cmd == "labels":
            res, recs = label_check(cfg, params, args.run, args.rigor)
            section = "labels"
            (args.run / "label_judgements.json").write_text(json.dumps(recs, indent=1, ensure_ascii=False) + "\n")
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
