"""Selection of alpha (the only selected parameter) by the one-SE rule on E1a, split half A.

Protocol (configs/eval.toml [selection], fixed before the sweep):
- eligible: the largest level-0 super-node holds <= max_giant_share of the concept nodes;
- score: E1a residual coupling lift at the primary cell (snapshot, level, stratum), with
  the ruler built from half A of the cited works only; SE from the paper jackknife;
- one-SE rule: among eligible configurations whose score >= best - SE(best), pick the alpha
  closest to `tie_toward`; remaining ties go to the higher score, then the smaller alpha.
Ground truth, labels and the extrinsic task are never used. Half B is used for reporting only.
"""

from tkh.evaluate.coherence import Ruler, coupling_lift, make_split


def giant_share(parts, cutoff):
    lv = parts[cutoff][0]
    sizes = [len(m) for m in lv.values()]
    return max(sizes) / sum(sizes)


def one_se(rows, tie_toward=0.5):
    """rows: [{"cid", "alpha", "value", "se", "eligible"}] -> (winner cid, rows annotated with "within_1se")."""
    ok = [r for r in rows if r["eligible"] and r["value"] is not None]
    if not ok:
        raise ValueError("no eligible configuration")
    best = max(ok, key=lambda r: r["value"])
    bar = best["value"] - (best["se"] or 0.0)
    for r in rows:
        r["within_1se"] = bool(r in ok and r["value"] >= bar)
    cands = [r for r in ok if r["within_1se"]]
    win = min(cands, key=lambda r: (abs(r["alpha"] - tie_toward), -r["value"], r["alpha"]))
    return win["cid"], rows


def score_configs(tkh, configs, sel, works):
    """configs: {cid: (alpha, parts)} -> rows for one_se, scored on the ruler restricted to `works`."""
    ruler = Ruler(tkh, sel["snapshot"], works, hub_frac=sel.get("hub_frac", 0.2))
    rows = []
    for cid, (alpha, parts) in sorted(configs.items()):
        cell = coupling_lift(ruler, parts[sel["snapshot"]][sel["level"]])[sel["stratum"]]
        g = giant_share(parts, sel["snapshot"])
        rows.append({"cid": cid, "alpha": alpha, "value": cell["value"], "se": cell.get("se"),
                     "giant_share": g, "eligible": g <= sel["max_giant_share"]})
    return rows


def select(tkh, configs, sel, split):
    rows = score_configs(tkh, configs, sel, set(split["A"]))
    return one_se(rows, sel["tie_toward"])


def selection_stability(tkh, configs, sel, n_seeds, start=1):
    """Winner under each of n_seeds other split seeds (half A of each)."""
    winners = []
    for s in range(start, start + n_seeds):
        w, _ = select(tkh, configs, sel, make_split(tkh, s))
        winners.append(w)
    return winners
