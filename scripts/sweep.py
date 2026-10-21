"""Pipeline step 'sweep': alpha grid -> selection on E1a half A -> ablations, nulls and perturbation runs of the winner.

    python scripts/sweep.py [--config CFG] [--eval configs/eval.toml] [--out DIR] [--jobs N] [--force]
    FAST=1 python scripts/sweep.py      # fewer null replicates and seeds ([fast] in eval.toml)

Writes <out>/runs/... (partitions of every build, git-ignored; existing files are reused
unless --force) and <out>/selection.json (the selection table, the winner, its stability
over other split seeds, the selected parameters). data/eval_splits.json is created on the
first run and checked against the split rule afterwards.
"""

import os

for _v in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "VECLIB_MAXIMUM_THREADS"):
    os.environ.setdefault(_v, "1")  # one thread per build; parallelism comes from the process pool

from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path
import argparse
import json
import sys
import time
import tomllib

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from tkh.coarsen import CLUSTER_RELATIONS, hubs  # noqa: E402
from tkh.config import add_config_args, config_from_args  # noqa: E402
from tkh.evaluate import runs  # noqa: E402
from tkh.evaluate.coherence import make_split  # noqa: E402
from tkh.evaluate.nulls import semantic_permutation, shuffle_hypergraph  # noqa: E402
from tkh.evaluate.selection import select, selection_stability  # noqa: E402
from tkh.evaluate.stability import remove_edges  # noqa: E402
from tkh.hierarchy import Params, build, concept_only  # noqa: E402
from tkh.io import load, snapshot  # noqa: E402

SPLIT_PATH = ROOT / "data" / "eval_splits.json"


def load_eval(path, fast=False):
    ev = tomllib.loads(Path(path).read_text())
    if fast:
        f = ev.get("fast", {})
        ev["nulls"]["R"] = f.get("R", ev["nulls"]["R"])
        ev["nulls"]["random_labels_R"] = f.get("random_labels_R", ev["nulls"]["random_labels_R"])
        ev["stability"]["seeds"] = f.get("seeds", ev["stability"]["seeds"])
        ev["stability"]["null_R"] = f.get("null_R", ev["stability"]["null_R"])
        ev["selection"]["stability_seeds"] = f.get("stability_seeds", ev["selection"]["stability_seeds"])
    ev["selection"]["hub_frac"] = ev["eval"]["hub_frac"]
    return ev


def ensure_split(tkh, seed):
    want = make_split(tkh, seed)
    if SPLIT_PATH.exists():
        have = json.loads(SPLIT_PATH.read_text())
        if have != want:
            raise SystemExit(f"{SPLIT_PATH} does not match make_split(seed={seed}); delete it to regenerate")
    else:
        SPLIT_PATH.write_text(json.dumps(want, indent=1) + "\n")
    return want


# ---------------------------------------------------------------- one build (runs in a worker process)

_TKH = {}


def _graph(cfg):
    if "g" not in _TKH:
        _TKH["g"] = load(cfg)
    return _TKH["g"]


def fixed_hubs(tkh, cutoffs, hub_frac):
    return sorted(set().union(*(hubs(tkh, snapshot(tkh, c), hub_frac) for c in cutoffs)))


def job(cfg, spec):
    """spec: {"path", "params", "null": kind|None, "null_seed", "perturb_seed"|None, "frac"}."""
    tkh = _graph(cfg)
    params = Params.from_config(spec["params"])
    g, perm, meta = tkh, None, dict(spec)
    t0 = time.perf_counter()
    if spec.get("null") in ("struct", "full"):
        g, d = shuffle_hypergraph(tkh, spec["null_seed"], cfg.cutoffs, fixed_hubs(tkh, cfg.cutoffs, params.hub_frac))
        meta["shuffle"] = d
    if spec.get("null") in ("sem", "full"):
        perm = semantic_permutation(tkh, spec["null_seed"], cfg.cutoffs)
    if spec.get("perturb_seed") is not None:
        g, dropped = remove_edges(g, spec["frac"], spec["perturb_seed"], cfg.cutoffs, CLUSTER_RELATIONS)
        meta["n_dropped"] = len(dropped)
    parts = concept_only(build(g, cfg.cutoffs, cfg.budgets, params, text_perm=perm), tkh)
    meta["runtime_s"] = round(time.perf_counter() - t0, 1)
    runs.save(spec["path"], parts, meta)
    return spec["path"]


def run_jobs(cfg, specs, n_jobs, force):
    todo = [s for s in specs if force or not Path(s["path"]).exists()]
    print(f"{len(specs)} builds, {len(todo)} to run on {n_jobs} processes", flush=True)
    if not todo:
        return
    t0 = time.perf_counter()
    with ProcessPoolExecutor(n_jobs) as ex:
        futs = [ex.submit(job, cfg, s) for s in todo]
        for i, f in enumerate(as_completed(futs), 1):
            f.result()
            if i % 10 == 0 or i == len(todo):
                print(f"  {i}/{len(todo)} done, {time.perf_counter() - t0:.0f}s", flush=True)


# ---------------------------------------------------------------- the protocol

def main(argv=None):
    p = add_config_args(argparse.ArgumentParser(description=__doc__.split("\n")[0]))
    p.add_argument("--eval", type=Path, default=ROOT / "configs" / "eval.toml")
    p.add_argument("--out", type=Path, help="output directory (default: the config's out_dir)")
    p.add_argument("--jobs", type=int, default=None)
    p.add_argument("--force", action="store_true", help="rebuild runs that already exist")
    args = p.parse_args(argv)
    cfg = config_from_args(args)
    fast = os.environ.get("FAST") == "1"
    ev = load_eval(args.eval, fast)
    out = Path(args.out or cfg.out_dir)
    n_jobs = args.jobs or ev["eval"]["jobs"]
    tkh = load(cfg)
    split = ensure_split(tkh, ev["selection"]["split_seed"])
    base = Params.from_config(cfg.method).as_dict()
    sel = ev["selection"]

    # 1. alpha grid
    grid = {}
    for a in sel["alpha_grid"]:
        pr = Params.from_config({**base, "alpha": a})
        grid[pr.cid()] = {"path": str(runs.run_path(out, "config", pr.cid())), "params": pr.as_dict()}
    run_jobs(cfg, list(grid.values()), n_jobs, args.force)
    configs = {cid: (s["params"]["alpha"], runs.load(s["path"])[0]) for cid, s in grid.items()}

    # 2. selection on half A (+ stability over other split seeds)
    winner, rows = select(tkh, configs, sel, split)
    winners = selection_stability(tkh, configs, sel, sel["stability_seeds"])
    wp = grid[winner]["params"]
    print(f"selected {winner}; agreement over {len(winners)} other splits: {winners.count(winner) / len(winners):.2f}")

    # 3. ablations, nulls and perturbation runs
    abl = {}
    for name, change in ev["ablations"].items():
        pr = Params.from_config({**wp, **change})
        abl[name] = {"path": str(runs.run_path(out, "config", pr.cid())), "params": pr.as_dict()}
    nulls = [{"path": str(runs.run_path(out, "null", k, s)), "params": wp, "null": k, "null_seed": s}
             for k in ev["nulls"]["kinds"] for s in range(ev["nulls"]["R"])]
    st = ev["stability"]
    all_cfgs = {**grid, **{Params.from_config(v["params"]).cid(): v for v in abl.values()}}
    pert = [{"path": str(runs.run_path(out, "perturb", cid, s)), "params": spec["params"], "perturb_seed": s, "frac": st["frac"]}
            for cid, spec in all_cfgs.items() for s in st["seeds"]]
    pert_null = [{"path": str(runs.run_path(out, "perturb_null", k, ns, s)), "params": wp, "null": k, "null_seed": ns,
                  "perturb_seed": s, "frac": st["frac"]}
                 for k in ev["nulls"]["kinds"] for ns in range(st["null_R"]) for s in st["seeds"]]
    run_jobs(cfg, list(abl.values()) + nulls + pert + pert_null, n_jobs, args.force)

    selected = {"alpha": wp["alpha"]}
    res = {"protocol": sel, "fast": fast, "split_seed": split["seed"], "table": rows, "winner": winner,
           "selected_params": selected, "stability": {"winners": winners, "agreement": winners.count(winner) / len(winners)},
           "configs": {cid: s["params"] for cid, s in grid.items()},
           "ablations": {name: {"cid": Params.from_config(s["params"]).cid(), "params": s["params"]} for name, s in abl.items()},
           "nulls": {"kinds": ev["nulls"]["kinds"], "R": ev["nulls"]["R"]},
           "stability_runs": {"seeds": st["seeds"], "null_R": st["null_R"], "frac": st["frac"]}}
    out.mkdir(parents=True, exist_ok=True)
    (out / "selection.json").write_text(json.dumps(res, indent=1) + "\n")
    print(f"-> {out / 'selection.json'}")


if __name__ == "__main__":
    main()
