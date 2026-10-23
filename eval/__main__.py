"""Command line of the evaluation: python -m eval {p3,sweep}.

  p3     --run DIR [--R 99] [--R-labels 999]   held-out P3 check of a run per snapshot and level, unadjusted and
                                               period-adjusted, against both nulls -> DIR/metrics.json
                                               (uses the run's own run_config.toml)
  sweep  --out FILE [--param k=v ...]          configuration grid and one-SE selection on cited-work halves,
                                               around the config's [method] (with overrides)
"""

from pathlib import Path
import argparse
import json

from eval.experiments import p3_check, sweep
from tkh.config import add_config_args, config_from_args, load_config, parse_overrides
from tkh.hierarchy import Params


def main(argv=None):
    ap = argparse.ArgumentParser(prog="python -m eval", description=__doc__.split("\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("p3")
    p.add_argument("--run", type=Path, required=True)
    p.add_argument("--R", type=int, default=99)
    p.add_argument("--R-labels", type=int, default=999)
    p.add_argument("--jobs", type=int, default=8)
    p = add_config_args(sub.add_parser("sweep"))
    p.add_argument("--param", nargs="*", help="override [method] parameters of the base configuration")
    p.add_argument("--out", type=Path)
    p.add_argument("--jobs", type=int, default=8)
    args = ap.parse_args(argv)

    if args.cmd == "p3":   # the run's own resolved config, so the check uses exactly its inputs and parameters
        if "null" in json.loads((args.run / "run_info.json").read_text()):
            raise SystemExit(f"{args.run} is a null-model run: the P3 check evaluates real runs (its ruler is built on the real export)")
        cfg = load_config(args.run / "run_config.toml")
        res = p3_check(cfg, Params.from_config(cfg.method), args.run, args.R, args.R_labels, args.jobs)
        (args.run / "metrics.json").write_text(json.dumps(res, indent=1, allow_nan=False) + "\n")
        for c, snap in res["snapshots"].items():
            for row in snap["levels"]:
                for mode in ("unadjusted", "interval"):
                    e = row["exact"][mode]
                    cn, rl = e["configuration_null"], e["random_labels"]
                    print(f"<={c} level {row['level']} ({row['super_nodes']}) {mode:10s} lift {e['lift']}"
                          f"  config null {cn.get('mean')} p={cn.get('p')}  random labels {rl.get('mean')} p={rl.get('p')}")
    else:
        cfg = config_from_args(args)
        res = sweep(cfg, Params.from_config({**cfg.method, **parse_overrides(args.param)}), n_jobs=args.jobs)
        out = args.out or cfg.out_dir / "sweep.json"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(res, indent=1) + "\n")
        print(f"selected {res['selected']} in {res['selected_share']:.0%} of splits -> {out}")


if __name__ == "__main__":
    main()
