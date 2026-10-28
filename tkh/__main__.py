"""Command line of the method: python -m tkh {build,null} [--config CFG] [--param k=v ...] [overrides].

  build  --out DIR                    one SHAC run (tkh/pipeline.py)
  null   --seed S --out DIR           configuration-null export DIR/graph.json and a run built on it
                                      (validate: validate.py DIR --config DIR/run_config.toml)

[method] parameters come from the config (tkh/hierarchy.py Params); --param overrides single values.
Budgets, cutoffs and inputs can be overridden with --budgets, --cutoffs, --graph, --articles.
Evaluation (coherence, stability, faithfulness and retrieval checks, alpha sweep) lives in eval/: python -m eval {coherence,stability,faithfulness,retrieval,gamma,sweep}.
"""

from pathlib import Path
import argparse
import json

from tkh.coarsen import hubs
from tkh.config import add_config_args, config_from_args, parse_overrides
from tkh.hierarchy import Params
from tkh.io import load, snapshot
from tkh.null import null_tkh
from tkh.pipeline import run, with_graph


def main(argv=None):
    ap = argparse.ArgumentParser(prog="python -m tkh", description=__doc__.split("\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name in ("build", "null"):
        p = add_config_args(sub.add_parser(name))
        p.add_argument("--param", nargs="*", help="override [method] parameters, e.g. alpha=0.25 hub_frac=0.3")
        p.add_argument("--out", type=Path, required=name == "null")
        if name == "null":
            p.add_argument("--seed", type=int, required=True)
    args = ap.parse_args(argv)

    cfg = config_from_args(args)
    params = Params.from_config({**cfg.method, **parse_overrides(args.param)})
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


if __name__ == "__main__":
    main()
