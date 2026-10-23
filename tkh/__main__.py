"""Command line: python -m tkh {build,null,p3,sweep} [--config CFG] [--param k=v ...] [overrides].

  build  --out DIR                    one SHAC run (tkh/pipeline.py)
  null   --seed S --out DIR           configuration-null export DIR/graph.json and a run built on it
                                      (validate: validate.py DIR --config DIR/run_config.toml)
  p3     --run DIR [--R 99]           held-out P3 check of a run per snapshot and level, unadjusted and
                                      period-adjusted, against both nulls -> DIR/metrics.json
  sweep  --out FILE                   configuration grid and one-SE selection on cited-work halves

[method] parameters come from the config (tkh/hierarchy.py Params); --param overrides single values.
Budgets, cutoffs and inputs can be overridden with --budgets, --cutoffs, --graph, --articles (build, null, sweep);
p3 always uses the run's own run_config.toml.
"""

from pathlib import Path
import argparse
import json

from tkh.coarsen import hubs
from tkh.config import add_config_args, config_from_args, load_config
from tkh.hierarchy import Params
from tkh.io import load, snapshot
from tkh.null import null_tkh
from tkh.pipeline import run, with_graph


def _overrides(pairs):
    out = {}
    for p in pairs or []:
        k, v = p.split("=", 1)
        try:
            out[k] = json.loads(v)
        except json.JSONDecodeError:
            out[k] = v
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(prog="python -m tkh", description=__doc__.split("\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name in ("build", "null", "sweep"):
        p = add_config_args(sub.add_parser(name))
        p.add_argument("--param", nargs="*", help="override [method] parameters, e.g. alpha=0.25 hub_frac=0.3")
        p.add_argument("--out", type=Path, required=name == "null")
        if name == "null":
            p.add_argument("--seed", type=int, required=True)
        if name == "sweep":
            p.add_argument("--jobs", type=int, default=8)
    p = sub.add_parser("p3")   # uses the run's own run_config.toml only
    p.add_argument("--run", type=Path, required=True)
    p.add_argument("--R", type=int, default=99)
    p.add_argument("--R-labels", type=int, default=999)
    p.add_argument("--jobs", type=int, default=8)
    args = ap.parse_args(argv)

    if args.cmd == "p3":   # the run's own resolved config, so the check uses exactly its inputs and parameters
        from tkh.experiments import p3_check
        if "null" in json.loads((args.run / "run_info.json").read_text()):
            raise SystemExit(f"{args.run} is a null-model run: the P3 check evaluates real runs (its ruler is built on the real export)")
        cfg = load_config(args.run / "run_config.toml")
        params = Params.from_config(cfg.method)
        res = p3_check(cfg, params, args.run, args.R, args.R_labels, args.jobs)
        (args.run / "metrics.json").write_text(json.dumps(res, indent=1, allow_nan=False) + "\n")
        for c, snap in res["snapshots"].items():
            for row in snap["levels"]:
                for mode in ("unadjusted", "interval"):
                    e = row["exact"][mode]
                    cn, rl = e["configuration_null"], e["random_labels"]
                    print(f"<={c} level {row['level']} ({row['super_nodes']}) {mode:15s} lift {e['lift']:.3f}"
                          f"  config null {cn.get('mean', float('nan')):.3f} p={cn.get('p')}"
                          f"  random labels {rl.get('mean', float('nan')):.3f} p={rl.get('p')}")
        return

    cfg = config_from_args(args)
    params = Params.from_config({**cfg.method, **_overrides(args.param)})
    if args.cmd == "build":
        out = args.out or cfg.out_dir
        _, events, info = run(cfg, params, out)
        print(f"{params.cid()}: {len(events)} events, {info['runtime_s']}s -> {out}")
    elif args.cmd == "null":
        real = load(cfg)
        tkh, raw_null, diag = null_tkh(json.loads(Path(cfg.graph).read_text()), cfg.articles, cfg.cutoffs, args.seed, real=real)
        args.out.mkdir(parents=True, exist_ok=True)
        graph = args.out / "graph.json"
        graph.write_text(json.dumps(raw_null, ensure_ascii=False) + "\n")
        hubsets = {c: hubs(real, snapshot(real, c), params.hub_frac) for c in cfg.cutoffs}
        _, events, info = run(with_graph(cfg, graph), params, args.out, tkh=tkh, hubsets=hubsets, info={"null": diag})
        print(f"null seed {args.seed} ({diag['moved_share']:.0%} of incidences moved): {len(events)} events -> {args.out}")
    elif args.cmd == "sweep":
        from tkh.experiments import sweep
        res = sweep(cfg, params, n_jobs=args.jobs)
        out = args.out or cfg.out_dir / "sweep.json"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(res, indent=1) + "\n")
        print(f"selected {res['selected']} in {res['selected_share']:.0%} of splits -> {out}")


if __name__ == "__main__":
    main()
