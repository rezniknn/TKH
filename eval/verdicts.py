"""Verdict rules over a metrics dict (the layout of out/metrics.json), shared by make_tables.py (report tables) and
eval/sweep.py (the alpha_sweep section), so that both apply one definition.

  sig        a lift beats both nulls at ALPHA (configuration and random-label p-values)
  below      a lift lies below the 2.5% quantile of both nulls under every period scheme
  verdict    of a cell (snapshot x level, one filter): robust (significant under all SCHEMES), below both nulls,
             significant under the primary scheme (k/5 schemes), not significant, not evaluable (one interval-scheme
             stratum) or undefined (no co-assigned evaluable pair)
  favoured   which system a drill-down - flat difference favours (point estimate; LOWER_BETTER measures reversed)
  favour_counts  measures of RETRIEVAL_NAMES favouring each system: a descriptive summary of correlated point
             estimates, not independent votes; RETRIEVAL_COST (computation) is excluded
"""

import hashlib
import json

ALPHA = 0.05          # significance level of the null tests
SCHEMES = ("interval", "year1", "year2", "year3", "gap")
RETRIEVAL_NAMES = {"methods": "hit-rate, methods", "method_claims": "hit-rate, method claims, by source article",
                   "claims": "hit-rate, claims, by source article", "citations": "hit-rate, citations",
                   "error_rate": "error rate", "reached": "reach",
                   "inspect_first": "items inspected to first item (median)",
                   "inspect_half": "items inspected to 50% of items (median)"}
RETRIEVAL_COST = {"scored": "candidates scored (median; computation, not counted)"}   # shown, never in favour_counts
LOWER_BETTER = frozenset({"error_rate", "inspect_first", "inspect_half", "scored"})


def ok(b):
    return b is not None and None not in b


def cutoffs(m):
    return sorted(m["coherence"]["snapshots"], key=int)


def sig(x):
    """Both nulls beaten at ALPHA (an undefined lift has p = None and never passes)."""
    a, b = x["configuration_null"]["p"], x["random_labels"]["p"]
    return a is not None and b is not None and max(a, b) <= ALPHA


def below(cell):
    """The lift lies below the 2.5% quantile of both nulls under every scheme."""
    def b(x):
        lo = (x["configuration_null"]["q2.5"], x["random_labels"]["q2.5"])
        return x["lift"] is not None and None not in lo and min(lo) > x["lift"]
    return all(b(cell[s]) for s in SCHEMES)


def passes(cell):
    return sum(sig(cell[s]) for s in SCHEMES)


def verdict(cell, strata):
    iv = cell["interval"]
    if iv["lift"] is None:
        return "undefined"
    if strata < 2:
        return "not evaluable (one interval-scheme stratum)"
    n = passes(cell)
    if n == len(SCHEMES):
        return "robust"
    if below(cell):
        return "below both nulls"
    if sig(iv):
        return f"significant, {n}/{len(SCHEMES)} schemes"
    return f"not significant ({n}/{len(SCHEMES)} schemes)"


def cells(m, pred, f="exact"):
    c = m["coherence"]["snapshots"]
    return [f"≤{t} L{k}" for t in cutoffs(m) for k, lv in enumerate(c[t]["levels"]) if pred(lv[f], c[t]["coverage"][f]["period_strata"])]


def robust(m, f="exact"):
    return cells(m, lambda x, s: s >= 2 and passes(x) == len(SCHEMES), f)


def below_cells(m, f="exact"):
    return cells(m, lambda x, s: s >= 2 and x["interval"]["lift"] is not None and below(x), f)


def above_null(m):
    """(cross-snapshot indices above the new-paper null at ALPHA, all indices)."""
    idx = [v for x in m["stability"]["cross_snapshot"].values() for v in [*x["ari"], x["hari"]]]
    return sum(v["new_paper_null"]["p"] is not None and v["new_paper_null"]["p"] <= ALPHA for v in idx), idx


def localised(m):
    """(level x transition cells whose ratio CI lies above 1, all cells)."""
    loc = [x for lvs in m["stability"]["localisation"].values() for x in lvs]
    return sum(ok(x["ratio_ci95"]) and x["ratio_ci95"][0] > 1 for x in loc), loc


def untouched_share(x):
    tot = x["touched"] * x["reassign_touched"] + x["untouched"] * x["reassign_untouched"]
    return x["untouched"] * x["reassign_untouched"] / tot if tot else None


def favoured(k, d):
    """Which system a paired difference (drill-down - flat) favours; a point estimate (no CIs)."""
    if d is None:
        return None
    return "tie" if abs(d) < 1e-12 else ("drill-down" if (d < 0) == (k in LOWER_BETTER) else "flat")


def section_hash(x):
    """Content hash of a metrics.json section (order-independent), to compare sections across files."""
    return hashlib.sha256(json.dumps(x, sort_keys=True).encode()).hexdigest()


def favour_counts(m):
    fav = {"drill-down": 0, "flat": 0, "tie": 0}
    for s in m["retrieval"]["summary"].values():
        for k in RETRIEVAL_NAMES:
            if k in s and (fv := favoured(k, s[k]["hier_minus_flat"])):
                fav[fv] += 1
    return fav
