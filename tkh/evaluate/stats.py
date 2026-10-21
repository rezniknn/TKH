"""Shared statistics for the evaluation: model vs null summaries, Wilson intervals, paired tests and Holm correction.

null_compare(obs, null_values, higher_is_better)
    null mean, 2.5-97.5% range of the null replicates, z = (obs - mean) / sd and the
    empirical one-sided p = (1 + #{null at least as good as obs}) / (R + 1).
holm(pvalues)
    Holm-Bonferroni step-down adjusted p-values (family-wise error control), applied to
    the pre-registered primary tests only; everything else is descriptive.
"""

import math

import numpy as np
from scipy import stats


def null_compare(obs, null_values, higher_is_better=True):
    v = np.asarray([x for x in null_values if x is not None and np.isfinite(x)], float)
    if obs is None or not np.isfinite(obs) or len(v) == 0:
        return {"null_mean": None, "null_lo": None, "null_hi": None, "z": None, "p": None, "R": int(len(v))}
    sd = float(v.std(ddof=1)) if len(v) > 1 else 0.0
    hits = int((v >= obs).sum() if higher_is_better else (v <= obs).sum())
    return {"null_mean": float(v.mean()), "null_lo": float(np.quantile(v, 0.025)), "null_hi": float(np.quantile(v, 0.975)),
            "z": (obs - float(v.mean())) / sd if sd > 0 else None, "p": (1 + hits) / (len(v) + 1), "R": int(len(v))}


def wilson(k, n, conf=0.95):
    """Wilson score interval for a binomial proportion k / n."""
    if n == 0:
        return None, None
    z = stats.norm.ppf(0.5 + conf / 2)
    p = k / n
    den = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / den
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / den
    return centre - half, centre + half


def holm(pvalues):
    """{name: p} -> {name: Holm-adjusted p}; None values are passed through."""
    items = sorted(((p, k) for k, p in pvalues.items() if p is not None))
    m = len(items)
    out, running = {k: None for k, p in pvalues.items() if p is None}, 0.0
    for i, (p, k) in enumerate(items):
        running = max(running, min(1.0, (m - i) * p))
        out[k] = running
    return out


def wilcoxon_paired(a, b, alternative="greater"):
    """Wilcoxon signed-rank test of a - b (paired, e.g. by question); None if all differences are zero."""
    d = np.asarray(a, float) - np.asarray(b, float)
    if len(d) == 0 or np.all(d == 0):
        return None
    return float(stats.wilcoxon(d, alternative=alternative, zero_method="wilcox").pvalue)
