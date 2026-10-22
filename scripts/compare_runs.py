"""Paired comparison of two or more evaluated runs (scripts/evaluate.py outputs) on the dev evidence.

    python scripts/compare_runs.py BASE_RUN OTHER_RUN [...] [--out comparison.json]

For each other run vs the base, paired deltas with intervals:
  M1  no-overlap coupling lift, dev half A, primary snapshot/level: delta and a jackknife interval over the shared
      citing papers (the same papers are left out of both runs);
  M2  perturbation HARI paired by perturbation seed (t-interval of the per-seed differences);
  M4  mean cost to the target paired by target (bootstrap over targets), member profiles.
Decision rule (configs/eval.toml, pre-registered): a run improves on the base if its M1 delta interval excludes 0
in the improving direction and neither M2 nor M4 regresses beyond its interval.
"""

from pathlib import Path
import argparse
import json
import math
import sys

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from tkh.evaluate.stability import t_interval  # noqa: E402


def load_units(run):
    return json.loads((Path(run) / "eval" / "units.json").read_text())


def m1_delta(a, b, key):
    ua, ub = a[key], b[key]
    common = sorted(set(ua["jack"]) & set(ub["jack"]))
    d = ub["value"] - ua["value"]
    reps = np.array([ub["jack"][p] - ua["jack"][p] for p in common], float)
    reps = reps[np.isfinite(reps)]
    n = len(reps)
    se = math.sqrt((n - 1) / n * ((reps - reps.mean()) ** 2).sum()) if n > 2 else float("nan")
    return {"delta": d, "lo": d - 1.96 * se, "hi": d + 1.96 * se, "n": n}


def m2_delta(a, b):
    sa, sb = a.get("M2|perturb_hari", {}), b.get("M2|perturb_hari", {})
    common = sorted(set(sa) & set(sb))
    ti = t_interval([sb[s] - sa[s] for s in common]) if common else {"mean": None, "lo": None, "hi": None, "n": 0}
    return {"delta": ti["mean"], "lo": ti["lo"], "hi": ti["hi"], "n": ti["n"]}


def m4_delta(a, b, profile="hierarchy (members)", n_boot=2000, seed=0):
    ca, cb = a["M4|cost_by_target"][profile], b["M4|cost_by_target"][profile]
    common = sorted(set(ca) & set(cb))
    d = np.array([cb[t] - ca[t] for t in common])
    rng = np.random.default_rng(seed)
    bs = [d[rng.integers(0, len(d), len(d))].mean() for _ in range(n_boot)]
    return {"delta": float(d.mean()), "lo": float(np.quantile(bs, .025)), "hi": float(np.quantile(bs, .975)), "n": len(d)}


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    p.add_argument("base")
    p.add_argument("others", nargs="+")
    p.add_argument("--key", default="M1|2026|1|no_overlap|A")
    p.add_argument("--out", type=Path, default=None)
    args = p.parse_args(argv)
    base = load_units(args.base)
    res = {}
    for o in args.others:
        u = load_units(o)
        r = {"M1": m1_delta(base, u, args.key) if args.key in u and args.key in base else None,
             "M2": m2_delta(base, u), "M4": m4_delta(base, u) if "M4|cost_by_target" in u else None}
        better = r["M1"] is not None and r["M1"]["lo"] > 0
        no_reg = (r["M2"]["hi"] is None or r["M2"]["hi"] > 0) and (r["M4"] is None or r["M4"]["lo"] < 0)
        r["improves"] = bool(better and no_reg)
        res[o] = r
        print(o, json.dumps(r, default=float))
    if args.out:
        args.out.write_text(json.dumps(res, indent=1, default=float) + "\n")


if __name__ == "__main__":
    main()
