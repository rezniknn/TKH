"""Static figures of an evaluated run, read from DIR/metrics.json (no recomputation of any check; nothing calls the
pipeline or an LLM): python -m eval.figures --run out --out docs/figures; alpha_sweep.png from the alpha_sweep section
(eval/sweep.py) when it is present.

  coherence_lift.png                primary lift (period scheme "interval", exact matching) with its 95% bootstrap
                                    interval per snapshot and level, next to the 95% bands of the configuration null
                                    (R = 99 rebuilds) and the random-label null (R = 999 permutations)
  coherence_period_sensitivity.png  lift per period scheme at the last cutoff, exact and fuzzy citation matching
  stability.png                     perturbation ARI per level and HARI per snapshot (mean, t-interval over seeds);
                                    cross-snapshot ARI per level and HARI vs the 95% band of the new-paper null
  localisation.png                  reassignment rate of old concept nodes touched vs untouched by new papers, and
                                    their ratio with its node-bootstrap interval, per transition and level
  faithfulness.png                  over-claim rate (share of labels with >= 1 claim unsupported by held-out
                                    evidence) with its bootstrap interval by cutoff and level, and overall
  retrieval.png                     drill-down vs flat search per question type: (a) rates (hit-rates, error rate,
                                    reach; means, no CIs); (b) median steps to the first item and to 50% of items
  alpha_sweep.png                   per alpha: (a) last-snapshot lift per level (exact, interval scheme) with its
                                    bootstrap CI; (b) perturbation HARI per snapshot (t-interval); (c) over-claim rate,
                                    overall and per level (bootstrap CI); (d) retrieval hit-rates, drill-down minus flat
"""

from pathlib import Path
import argparse
import json

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402

# Okabe-Ito (colour-blind safe); one colour per level throughout, black for HARI and overall rates
LEVEL = ["#0072B2", "#E69F00", "#009E73"]
CFG, RL, MODEL = "#7F7F7F", "#CC79A7", "#000000"
PERIODS = ["unadjusted", "interval", "year1", "year2", "year3", "gap"]
plt.rcParams.update({"font.size": 9, "axes.titlesize": 9.5, "axes.labelsize": 9, "legend.fontsize": 8, "xtick.labelsize": 8.5,
                     "ytick.labelsize": 8.5, "axes.spines.top": False, "axes.spines.right": False, "savefig.dpi": 200,
                     "savefig.bbox": "tight", "font.family": "DejaVu Sans"})


def _err(ax, x, v, lo, hi, **kw):
    """Point with an asymmetric interval; None values are skipped."""
    if v is None:
        return
    ax.errorbar([x], [v], yerr=[[v - lo], [hi - v]] if lo is not None else None, fmt=kw.pop("fmt", "o"), ms=kw.pop("ms", 5),
                capsize=2.5, lw=1.2, **kw)


def _band(ax, x, lo, hi, color, w=0.16, label=None):
    """A null's 95% band as a translucent bar centred at x."""
    ax.bar([x], [hi - lo], bottom=[lo], width=w, color=color, alpha=0.35, edgecolor=color, lw=0.8, label=label)


# ---------------------------------------------------------------- coherence

def coherence_lift(coh, out):
    snaps = sorted(coh["snapshots"])
    lo_y, hi_y = 0.02, 16.0
    fig, axes = plt.subplots(1, 3, figsize=(10, 3.4), sharey=True)
    for k, ax in enumerate(axes):
        for i, c in enumerate(snaps):
            s = coh["snapshots"][c]
            r = s["levels"][k]["exact"][coh["primary"]]
            if r["lift"] is None:
                ax.text(i, 1.0, "undefined\n(no pairs)", ha="center", va="center", fontsize=7.5, color="0.35")
                continue
            for off, key, col, lab in ((-0.24, "configuration_null", CFG, "configuration null 95%"),
                                       (0.24, "random_labels", RL, "random-label null 95%")):
                _band(ax, i + off, r[key]["q2.5"], r[key]["q97.5"], col, label=lab if i == 1 else None)
            lo, hi = r["ci95"]
            lo_c, hi_c = max(lo, lo_y * 1.05), min(hi, hi_y / 1.05)
            _err(ax, i, r["lift"], lo_c, hi_c, color=LEVEL[k], label="model lift, 95% CI" if i == 1 else None)
            if lo < lo_y * 1.05:   # interval clipped at the axis: mark it
                ax.plot([i], [lo_y * 1.12], marker="v", color=LEVEL[k], ms=4)
            if hi > hi_y / 1.05:
                ax.plot([i], [hi_y / 1.12], marker="^", color=LEVEL[k], ms=4)
            ax.text(i, hi_y * 0.78, f"n={s['coverage']['exact']['no_overlap_pairs']}", ha="center", fontsize=7, color="0.35")
        ax.axhline(1, color="0.5", lw=0.8, ls="--", zorder=0)
        ax.set_yscale("log")
        ax.set_ylim(lo_y, hi_y)
        ax.set_xticks(range(len(snaps)), snaps)
        ax.set_xlim(-0.6, len(snaps) - 0.4)
        ax.set_title(f"level {k} ({coh['budgets'][k]} super-nodes)")
        ax.set_xlabel("snapshot cutoff")
    axes[0].set_ylabel("period-adjusted lift (interval scheme, log scale)")
    axes[0].set_yticks([0.05, 0.1, 0.2, 0.5, 1, 2, 5, 10], ["0.05", "0.1", "0.2", "0.5", "1", "2", "5", "10"])
    h, lab = [], []
    for ax in axes:
        for hh, ll in zip(*ax.get_legend_handles_labels()):
            if ll not in lab:
                h.append(hh); lab.append(ll)
    fig.legend(h, lab, loc="upper center", ncol=3, frameon=False, bbox_to_anchor=(0.5, 1.06))
    fig.text(0.5, -0.04, "Held-out bibliographic-coupling lift on no-overlap paper pairs, exact matching; 1 = chance (dashed). "
             "n = no-overlap pairs among citing papers; triangles: interval clipped at the axis.", ha="center", fontsize=7.5, color="0.3")
    fig.savefig(out / "coherence_lift.png")
    plt.close(fig)


def coherence_periods(coh, out):
    c = sorted(coh["snapshots"])[-1]
    s = coh["snapshots"][c]
    fig, axes = plt.subplots(1, 3, figsize=(10, 3.3), sharey=True)
    x = np.arange(len(PERIODS))
    for k, ax in enumerate(axes):
        for off, match, mk, fill in ((-0.13, "exact", "o", LEVEL[k]), (0.13, "fuzzy", "s", "white")):
            for i, p in enumerate(PERIODS):
                r = s["levels"][k][match][p]
                _err(ax, x[i] + off, r["lift"], *r["ci95"], color=LEVEL[k], fmt=mk, mfc=fill, mec=LEVEL[k],
                     label=f"{match} matching" if i == 0 else None)
        ax.axhline(1, color="0.5", lw=0.8, ls="--", zorder=0)
        ax.axvspan(0.6, 1.4, color="0.92", zorder=-1)   # the primary scheme
        ax.set_xticks(x, PERIODS, rotation=30, ha="right")
        ax.set_title(f"level {k} ({coh['budgets'][k]} super-nodes)")
        ax.legend(loc="upper left", frameon=False, ncol=2)
    axes[0].set_ylabel(f"lift at cutoff {c}, 95% CI")
    axes[0].set_ylim(0, 4.3)
    cov = s["coverage"]
    fig.text(0.5, -0.1, f"Shaded: primary scheme. No-overlap pairs: exact {cov['exact']['no_overlap_pairs']}, "
             f"fuzzy {cov['fuzzy']['no_overlap_pairs']}; period strata (interval): {cov['exact']['period_strata']}.",
             ha="center", fontsize=7.5, color="0.3")
    fig.savefig(out / "coherence_period_sensitivity.png")
    plt.close(fig)


# ---------------------------------------------------------------- stability

def stability(st, out):
    pert, cross = st["perturbation"], st["cross_snapshot"]
    snaps, trans = sorted(pert), sorted(cross)
    fig, (a, b) = plt.subplots(1, 2, figsize=(10, 3.6), gridspec_kw={"width_ratios": [1, 1.25]})
    x = np.arange(len(snaps))
    for k in range(len(st["budgets"])):
        r = [pert[c]["ari"][k] for c in snaps]
        a.errorbar(x + (k - 1.5) * 0.08, [e["mean"] for e in r], yerr=[[e["mean"] - e["lo"] for e in r], [e["hi"] - e["mean"] for e in r]],
                   fmt="o-", color=LEVEL[k], ms=4, capsize=2.5, lw=1.2, label=f"ARI level {k} ({st['budgets'][k]})")
    r = [pert[c]["hari"] for c in snaps]
    a.errorbar(x + 1.5 * 0.08, [e["mean"] for e in r], yerr=[[e["mean"] - e["lo"] for e in r], [e["hi"] - e["mean"] for e in r]],
               fmt="D--", color=MODEL, ms=4, capsize=2.5, lw=1.2, label="HARI")
    a.set_xticks(x, snaps)
    a.set_ylim(0, 1)
    a.set_xlabel("snapshot cutoff")
    a.set_ylabel("agreement with unperturbed run")
    p = st["protocol"]
    a.set_title(f"(a) perturbation: {p['frac']:.0%} of hyper-edges removed, {len(p['seeds'])} seeds\n(mean, 95% t-interval)")
    a.legend(frameon=False, loc="upper center", ncol=2, bbox_to_anchor=(0.5, -0.2), fontsize=7.5)
    x = np.arange(len(trans))
    series = [(f"level {k}", LEVEL[k], lambda t, k=k: cross[t]["ari"][k]) for k in range(len(st["budgets"]))]
    series.append(("HARI", MODEL, lambda t: cross[t]["hari"]))
    w = 0.2
    for j, (name, col, get) in enumerate(series):
        for i, t in enumerate(trans):
            r = get(t)
            xi = x[i] + (j - 1.5) * w
            _band(b, xi, r["new_paper_null"]["q2.5"], r["new_paper_null"]["q97.5"], CFG, w=0.15,
                  label="new-paper null 95%" if i == 0 and j == 0 else None)
            _err(b, xi, r["value"], *r["ci95"], color=col, fmt="D" if name == "HARI" else "o", ms=4,
                 label=(name if name == "HARI" else f"ARI {name}") if i == 0 else None)
    b.set_xticks(x, [f"{t}\n{cross[t]['common_nodes']} common nodes" for t in trans], fontsize=7.5)
    b.set_xlabel("transition")
    b.set_ylabel("agreement on common concept nodes")
    b.set_title(f"(b) cross-snapshot vs new-paper null (R = {p['R']})\n(95% half-subsample interval)")
    lo = min(min(get(t)["new_paper_null"]["q2.5"], get(t)["ci95"][0]) for _, _, get in series for t in trans)
    b.set_ylim(np.floor(lo * 20) / 20, 1)
    b.legend(frameon=False, loc="upper center", ncol=3, bbox_to_anchor=(0.5, -0.27), fontsize=7.5)
    fig.tight_layout()
    fig.savefig(out / "stability.png")
    plt.close(fig)


def localisation(st, out):
    loc = st["localisation"]
    trans = sorted(loc)
    K = len(st["budgets"])
    fig, (a, b) = plt.subplots(1, 2, figsize=(10, 3.5))
    x = np.arange(len(trans))
    w = 0.13
    for k in range(K):
        for side, (key, hatch, alpha) in enumerate((("reassign_touched", None, 1.0), ("reassign_untouched", "////", 0.35))):
            xs = x + (k * 2 + side - (2 * K - 1) / 2) * w
            a.bar(xs, [loc[t][k][key] for t in trans], width=w, color=LEVEL[k], alpha=alpha, hatch=hatch,
                  edgecolor=LEVEL[k], lw=0.6, label=f"level {k}, {'touched' if side == 0 else 'untouched'}")
    a.set_xticks(x, [f"{t}\ntouched {loc[t][0]['touched']}\nuntouched {loc[t][0]['untouched']}" for t in trans], fontsize=7.5)
    a.set_ylabel("reassignment rate (1 - Jaccard of co-members)")
    a.set_title("(a) old concept nodes touched vs untouched by new papers")
    a.set_ylim(0, 1)
    a.legend(frameon=False, ncol=3, fontsize=7, loc="upper left")
    for k in range(K):
        r = [loc[t][k] for t in trans]
        b.errorbar(x + (k - 1) * 0.1, [e["ratio"] for e in r], yerr=[[e["ratio"] - e["ratio_ci95"][0] for e in r],
                   [e["ratio_ci95"][1] - e["ratio"] for e in r]], fmt="o", color=LEVEL[k], ms=5, capsize=2.5, lw=1.2,
                   label=f"level {k} ({st['budgets'][k]})")
    b.axhline(1, color="0.5", lw=0.8, ls="--", zorder=0)
    b.set_xticks(x, trans)
    b.set_xlabel("transition")
    b.set_ylabel("touched / untouched reassignment rate")
    b.set_title("(b) ratio, 95% node-bootstrap interval (1 = no localisation)")
    b.set_ylim(0, None)
    b.legend(frameon=False, loc="upper left")
    fig.tight_layout()
    fig.savefig(out / "localisation.png")
    plt.close(fig)


# ---------------------------------------------------------------- label faithfulness

def faithfulness(f, out):
    lvls = f["protocol"]["levels"]
    cuts = f["protocol"]["cutoffs"]
    fig, (a, b) = plt.subplots(1, 2, figsize=(9, 3.4), width_ratios=[1.6, 1])
    for j, k in enumerate(lvls):
        for i, cu in enumerate(cuts):
            o = f["by_cutoff_level"][f"{cu}:L{k}"]["over_claim"]
            _err(a, i + (j - 0.5) * 0.2, o["value"], *o["ci95"], color=LEVEL[k], label=f"level {k}" if i == 0 else None)
    for i, cu in enumerate(cuts):
        a.text(i, 0.93, "n = " + " / ".join(str(f["by_cutoff_level"][f"{cu}:L{k}"]["over_claim"]["n"]) for k in lvls),
               ha="center", fontsize=7, color="0.35")
    a.set_xticks(range(len(cuts)), cuts)
    a.set_xlim(-0.6, len(cuts) - 0.4)
    a.set_ylim(0, 1.05)
    a.set_xlabel("snapshot cutoff")
    a.set_ylabel("over-claim rate, 95% CI")
    a.set_title("(a) by cutoff and level (n = labels judged, " + " / ".join(f"L{k}" for k in lvls) + ")")
    a.legend(frameon=False, loc="lower left", ncol=2)
    entries = [("all", f["over_claim"], MODEL)] + [(f"L{k}", f["by_level"][f"L{k}"]["over_claim"], LEVEL[k]) for k in lvls]
    for i, (name, o, col) in enumerate(entries):
        _err(b, i, o["value"], *o["ci95"], color=col)
        b.text(i, 0.05, f"n={o['n']}", ha="center", fontsize=7, color="0.35")
    b.set_xticks(range(len(entries)), [e[0] for e in entries])
    b.set_xlim(-0.6, len(entries) - 0.4)
    b.set_ylim(0, 1.05)
    b.set_ylabel("over-claim rate, 95% CI")
    b.set_title(f"(b) all cutoffs; claim-level unsupported {f['claim_unsupported']:.2f}")
    fig.suptitle("Share of labels with >= 1 claim unsupported by held-out evidence", fontsize=9.5)
    fig.tight_layout()
    fig.savefig(out / "faithfulness.png")
    plt.close(fig)


# ---------------------------------------------------------------- retrieval

def retrieval(ret, out):
    s = ret["summary"]
    rates = [(t, k) for t in sorted(s) for k in ("methods", "method_claims", "claims", "citations", "error_rate", "reached")
             if k in s[t]]
    steps = [(t, k) for t in sorted(s) for k in ("steps_first", "steps_half") if k in s[t]]
    name = {"methods": "methods", "method_claims": "method claims", "claims": "claims", "citations": "citations",
            "error_rate": "error rate", "reached": "reach", "steps_first": "first item", "steps_half": "50% of items"}
    fig, (a, b) = plt.subplots(1, 2, figsize=(10, 3.4), width_ratios=[1.8, 1])
    for ax, items in ((a, rates), (b, steps)):
        x = np.arange(len(items))
        for j, (sysname, key, col) in enumerate([("drill-down", "hier", LEVEL[0]), ("flat", "flat", CFG)]):
            ax.bar(x + (j - 0.5) * 0.38, [s[t][k][key] for t, k in items], width=0.38, color=col, label=sysname)
        ax.set_xticks(x, [f"{t}: {name[k]}" + (f"\n(n={s[t][k]['n']})") for t, k in items], rotation=30, ha="right")
        ax.legend(frameon=False)
    a.set_ylim(0, 1.05)
    a.set_ylabel("mean over questions (error rate: lower is better)")
    a.set_title("(a) rates per question type (point estimates, no CIs)")
    b.set_yscale("log")
    b.set_ylabel("median steps (log scale; lower is better)")
    b.set_title("(b) search effort")
    fig.tight_layout()
    fig.savefig(out / "retrieval.png")
    plt.close(fig)


# ---------------------------------------------------------------- alpha sweep

def alpha_sweep(sw, out):
    """From the alpha_sweep section of metrics.json (eval/sweep.py)."""
    al = sw["protocol"]["alphas"]
    var = {a: sw["variants"][f"{a:g}"] for a in al}
    cuts = sw["protocol"]["cutoffs"]
    last = str(max(cuts))
    x = np.arange(len(al))
    fig, ax = plt.subplots(1, 4, figsize=(14, 3.4))
    a, b, c, d = ax
    for k in range(3):
        for i, al_ in enumerate(al):
            iv = var[al_]["coherence"]["cells"][last][k]["exact"]
            _err(a, i + (k - 1) * 0.15, iv["lift"], *iv["ci95"], color=LEVEL[k], label=f"L{k}" if i == 0 else None)
    a.axhline(1, color="0.5", lw=0.8, ls=":")
    a.set_title(f"(a) held-out lift ≤{last} (1 = chance)")
    a.set_ylabel("lift, 95% CI")
    for j, cu in enumerate(cuts):
        h = [var[al_]["stability"]["perturbation_hari"][str(cu)] for al_ in al]
        col = plt.cm.Greys(0.35 + 0.65 * j / max(1, len(cuts) - 1))
        for i, v in enumerate(h):
            _err(b, i + (j - 1.5) * 0.12, v["mean"], v["lo"], v["hi"], color=col, label=f"≤{cu}" if i == 0 else None)
    b.set_title("(b) perturbation HARI per snapshot")
    b.set_ylabel("HARI, t-interval")
    for j, (name, col) in enumerate([("all", MODEL), ("L0", LEVEL[0]), ("L1", LEVEL[1])]):
        for i, al_ in enumerate(al):
            fa = var[al_]["faithfulness"]
            o = fa["over_claim"] if name == "all" else fa["by_level"][name]
            _err(c, i + (j - 1) * 0.15, o["value"], *o["ci95"], color=col, label=name if i == 0 else None)
    c.set_ylim(0, 1)
    c.set_title("(c) label over-claim rate (lower is better)")
    c.set_ylabel("over-claim, 95% CI")
    meas = [("A", "methods"), ("A", "method_claims"), ("A", "citations"), ("B", "claims"), ("B", "citations")]
    for j, (t, k) in enumerate(meas):
        y = [var[al_]["retrieval"]["summary"][t][k]["hier_minus_flat"] for al_ in al]
        d.plot(x, y, marker="o", ms=4, lw=1, color=plt.cm.tab10(j), label=f"{t}: {k.replace('_', ' ')}")
    d.axhline(0, color="0.5", lw=0.8, ls=":")
    d.set_title("(d) retrieval hit-rate, drill-down − flat")
    d.set_ylabel("paired difference (point estimate)")
    for axis in ax:
        axis.set_xticks(x, [f"{v:g}" for v in al])
        axis.set_xlabel("α (0 = structure only, 1 = semantics only)")
        axis.legend(frameon=False, fontsize=7)
    fig.tight_layout()
    fig.savefig(out / "alpha_sweep.png")
    plt.close(fig)


def main(argv=None):
    ap = argparse.ArgumentParser(prog="python -m eval.figures", description=__doc__.split("\n")[0])
    ap.add_argument("--run", type=Path, default=Path("out"))
    ap.add_argument("--out", type=Path, default=Path("docs/figures"))
    a = ap.parse_args(argv)
    m = json.loads((a.run / "metrics.json").read_text())
    a.out.mkdir(parents=True, exist_ok=True)
    coherence_lift(m["coherence"], a.out)
    coherence_periods(m["coherence"], a.out)
    stability(m["stability"], a.out)
    localisation(m["stability"], a.out)
    faithfulness(m["faithfulness"], a.out)
    retrieval(m["retrieval"], a.out)
    if "alpha_sweep" in m:
        alpha_sweep(m["alpha_sweep"], a.out)
    print("figures ->", a.out)


if __name__ == "__main__":
    main()
