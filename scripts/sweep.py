"""Pipeline step 'sweep' (SHAC-T-specific): alpha grid -> selection on M1 (dev half A) -> ablation runs of the winner.

    python scripts/sweep.py [--config CFG] [--eval configs/eval.toml] [--out DIR]
    FAST=1 python scripts/sweep.py

Every variant is built through the evaluator's own re-run hook ([eval] build_cmd, tkh/evalkit/runner.py) as an
ordinary artefact run under <out>/eval_cache/variants/<cid>/, with placeholder labels. Selection uses only the
evaluator's coherence metric M1 on the dev half A of the cited works, in its primary stratum (no-overlap paper
pairs), at the primary snapshot and level, with the one-SE rule (ties toward [selection] tie_toward); eligibility
requires the level-0 giant super-node to hold at most [selection] max_giant_share of the concept nodes. Writes
<out>/selection.json (table, winner, selected parameters, variant run directories, agreement over other splits).
"""

from pathlib import Path
import argparse
import json
import sys

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import numpy as np  # noqa: E402

from scripts.evaluate import jack_ci, load_eval, m1_cell  # noqa: E402
from tkh.config import add_config_args, config_from_args  # noqa: E402
from tkh.evalkit import runner  # noqa: E402
from tkh.evalkit.artefacts import Run  # noqa: E402
from tkh.evaluate.coherence import Ruler, load_split, make_split  # noqa: E402
from tkh.evaluate.selection import one_se  # noqa: E402
from tkh.hierarchy import Params  # noqa: E402
from tkh.io import load  # noqa: E402

SPLIT_PATH = ROOT / "data" / "eval_splits.json"


def ensure_split(tkh, seed):
    want = make_split(tkh, seed)
    if SPLIT_PATH.exists():
        if json.loads(SPLIT_PATH.read_text()) != want:
            raise SystemExit(f"{SPLIT_PATH} does not match make_split(seed={seed}); delete it to regenerate")
    else:
        SPLIT_PATH.write_text(json.dumps(want, indent=1) + "\n")
    return want


def extra_of(params, base):
    """--param arguments for the parameters that differ from the config defaults (alpha always given)."""
    keys = ["alpha"] + [k for k in params if k != "alpha" and params[k] != base.get(k)]
    return " ".join(f"--param {k}={json.dumps(params[k]) if isinstance(params[k], bool) else params[k]}" for k in keys)


def m1_dev(run_dir, tkh, cfg, ev, works):
    run = Run(run_dir, cfg.cutoffs, tkh)
    parts = run.concept_parts()
    c, k = ev["eval"]["primary_snapshot"], ev["eval"]["primary_level"]
    ruler = Ruler(tkh, c, works, hub_frac=ev["eval"]["hub_frac"])
    val, reps = m1_cell(ruler, parts[c][k], ev["m1"]["primary_stratum"])
    x = np.array([r for r in reps.values() if np.isfinite(r)])
    se = float(np.sqrt((len(x) - 1) / len(x) * ((x - x.mean()) ** 2).sum())) if len(x) > 2 else None
    sizes = [len(m) for m in parts[c][0].values()]
    return val, se, max(sizes) / sum(sizes), jack_ci(val, reps)


def main(argv=None):
    p = add_config_args(argparse.ArgumentParser(description=__doc__.split("\n")[0]))
    p.add_argument("--eval", type=Path, default=ROOT / "configs" / "eval.toml")
    p.add_argument("--out", type=Path, help="output directory (default: the config's out_dir)")
    args = p.parse_args(argv)
    cfg = config_from_args(args)
    ev = load_eval(args.eval)
    out = Path(args.out or cfg.out_dir)
    tkh = load(cfg)
    split = ensure_split(tkh, ev["m1"]["split_seed"])
    base = Params.from_config(cfg.method).as_dict()
    sel = ev["selection"]
    vdir = Path(ev["eval"]["cache_dir"]) / "variants"
    tmpl = ev["eval"]["build_cmd"]

    grid = {}
    for a in sel["alpha_grid"]:
        pr = Params.from_config({**base, "alpha": a}).as_dict()
        cid = Params.from_config(pr).cid()
        grid[cid] = {"params": pr, "dir": str(vdir / cid), "extra": extra_of(pr, base)}
    runner.build_many(tmpl, [(cfg.graph, g["dir"], g["extra"]) for g in grid.values()], ev["eval"]["jobs"], cwd=ROOT)

    rows = []
    for cid, g in grid.items():
        val, se, giant, (lo, hi) = m1_dev(g["dir"], tkh, cfg, ev, set(split["A"]))
        rows.append({"cid": cid, "alpha": g["params"]["alpha"], "value": val, "se": se, "ci_lo": lo, "ci_hi": hi,
                     "giant_share": giant, "eligible": giant <= sel["max_giant_share"]})
    winner, rows = one_se(rows, sel["tie_toward"])
    wp = grid[winner]["params"]
    # agreement of the winner over other cited-work splits (dev halves of 20 other seeds)
    others = []
    for s in range(1, 21):
        sp = make_split(tkh, s)
        rr = [{"cid": cid, "alpha": g["params"]["alpha"], "eligible": r["eligible"],
               **dict(zip(("value", "se"), m1_dev(g["dir"], tkh, cfg, ev, set(sp["A"]))[:2]))}
              for (cid, g), r in zip(grid.items(), rows)]
        others.append(one_se(rr, sel["tie_toward"])[0])
    print(f"selected {winner}; agreement over {len(others)} other splits: {others.count(winner) / len(others):.2f}")

    abl = {}
    for name, change in ev["ablations"].items():
        pr = Params.from_config({**wp, **change}).as_dict()
        cid = Params.from_config(pr).cid()
        abl[name] = {"cid": cid, "params": pr, "dir": str(vdir / cid), "extra": extra_of(pr, base)}
    runner.build_many(tmpl, [(cfg.graph, a["dir"], a["extra"]) for a in abl.values()], ev["eval"]["jobs"], cwd=ROOT)

    res = {"protocol": {**sel, "metric": "M1 coupling lift", "stratum": ev["m1"]["primary_stratum"], "split": "A",
                        "snapshot": ev["eval"]["primary_snapshot"], "level": ev["eval"]["primary_level"]},
           "table": rows, "winner": winner, "selected_params": {"alpha": wp["alpha"]},
           "winner_extra": grid[winner]["extra"],
           "stability": {"winners": others, "agreement": others.count(winner) / len(others)},
           "configs": grid, "ablations": abl}
    out.mkdir(parents=True, exist_ok=True)
    (out / "selection.json").write_text(json.dumps(res, indent=1, default=float) + "\n")
    print(f"-> {out / 'selection.json'}")


if __name__ == "__main__":
    main()
