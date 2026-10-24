"""Static figures of an evaluated run, read from DIR/metrics.json and DIR/label_judgements.json (no recomputation of
any check; nothing calls the pipeline or an LLM): python -m eval.figures --run out --out docs/figures.

  coherence_lift.png                primary lift (period scheme "interval", exact matching) with its 95% bootstrap
                                    interval per snapshot and level, next to the 95% bands of the configuration null
                                    (R = 99 rebuilds) and the random-label null (R = 999 permutations)
  coherence_period_sensitivity.png  lift per period scheme at the last cutoff, exact and fuzzy citation matching
  stability.png                     perturbation ARI per level and HARI per snapshot (mean, t-interval over seeds);
                                    cross-snapshot ARI per level and HARI vs the 95% band of the new-paper null
  localisation.png                  reassignment rate of old concept nodes touched vs untouched by new papers, and
                                    their ratio with its node-bootstrap interval, per transition and level
  labels.png                        over-claim rate (share of labels with >= 1 unsupported claim) with its bootstrap
                                    interval per tree and pooled per null kind; Youden J of the known-answer controls
                                    (J = Se + Sp - 1 with eval/labels.py's Se = P(unsupported | false member claim),
                                    Sp = P(supported | true member claim)); over-claim by cutoff and level of the model
                                    tree, recomputed from the judgement records

Configuration-null label trees: eval/labels.py keys their super-nodes "cfg<s>:<cutoff>:<group id>", and the group ids
restart at 0 on every level, so level-0 and level-1 groups with the same id share a key and their claims are pooled
(metrics.json reports judged = 60 of 75 labels). labels.png therefore also shows the per-label rate recomputed from the
records, which come in label order (one run of label claims followed by its controls per label); the same split
reproduces metrics.json exactly on the model and random-label trees, where the keys are unique.
"""

from pathlib import Path
import argparse
import json

import matplotlib
matplotlib.use("Agg")
from matplotlib.lines import Line2D  # noqa: E402
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402

# Okabe-Ito (colour-blind safe); one colour per level throughout, black for HARI and the model tree
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


def _boot(x, B=2000, seed=0):
    """Mean and percentile interval of a 0/1 array, as eval/labels.py _ci."""
    x = np.asarray(x, float)
    rng = np.random.default_rng(seed)
    b = [x[rng.integers(0, len(x), len(x))].mean() for _ in range(B)]
    return float(x.mean()), float(np.percentile(b, 2.5)), float(np.percentile(b, 97.5))


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


# ---------------------------------------------------------------- labels

def _label_rows(recs, tree):
    """Per label: list of its records, split by record order (a new label starts at a label claim after controls)."""
    rows, prev = [], None
    for r in recs:
        if r["tree"] != tree:
            continue
        if not rows or r["supernode"] != rows[-1][0]["supernode"] or (r["kind"] == "label" and prev != "label"):
            rows.append([])
        rows[-1].append(r)
        prev = r["kind"]
    return [[r for r in row if r["kind"] == "label"] for row in rows if any(r["kind"] == "label" for r in row)]


def _over(rows):
    return [any(not r["supported"] for r in row) for row in rows]


def labels(lab, recs, out):
    trees = lab["trees"]
    cfgs = sorted(t for t in trees if t.startswith("configuration_null"))
    rls = sorted(t for t in trees if t.startswith("random_labels"))
    last = max(int(r["supernode"].split(":")[0]) for r in recs if r["tree"] == "model")
    # recomputed per label row, to show the configuration-null key collision (module docstring)
    split = {t: _over(_label_rows(recs, t)) for t in trees}
    for t in ["model", *rls]:
        assert abs(np.mean(split[t]) - trees[t]["over_claim"]["value"]) < 1e-12 and len(split[t]) == trees[t]["judged"], t
    entries = [("model\n(all cutoffs)", trees["model"]["over_claim"], MODEL, None),
               (f"model\n({last})", lab["model_on_null_cutoffs"], MODEL, None)]
    entries += [(f"config.\nnull {t[-1]}", trees[t]["over_claim"], CFG, _boot(split[t])) for t in cfgs]
    entries += [("config.\npooled", lab["nulls"]["configuration_null"]["over_claim"], CFG, _boot([o for t in cfgs for o in split[t]]))]
    entries += [(f"random\nlabels {t[-1]}", trees[t]["over_claim"], RL, None) for t in rls]
    entries += [("random\npooled", lab["nulls"]["random_labels"]["over_claim"], RL, None)]

    fig = plt.figure(figsize=(10, 6.4))
    gs = fig.add_gridspec(2, 2, height_ratios=[1.15, 1], width_ratios=[1.35, 1], hspace=0.55, wspace=0.25)
    a, b, c = fig.add_subplot(gs[0, :]), fig.add_subplot(gs[1, 0]), fig.add_subplot(gs[1, 1])
    x = np.arange(len(entries))
    for i, (name, o, col, re) in enumerate(entries):
        pooled = "pooled" in name
        _err(a, x[i], o["value"], *o["ci95"], color=col, fmt="D" if pooled else "o", ms=6 if pooled else 5,
             label=None)
        a.text(x[i], 0.05, f"n={o['n']}", ha="center", fontsize=7, color="0.35")
        if re is not None:
            _err(a, x[i] + 0.25, re[0], re[1], re[2], color=col, fmt="o", mfc="white", ms=5, alpha=0.9)
    a.axhline(lab["model_on_null_cutoffs"]["value"], color=MODEL, lw=0.7, ls=":", zorder=0)
    a.axvline(1.5, color="0.8", lw=0.8)
    a.set_xticks(x, [e[0] for e in entries], fontsize=7.5)
    a.set_xlim(-0.5, len(entries) - 0.3)
    a.set_ylim(0, 1)
    a.set_ylabel("over-claim rate, 95% CI")
    a.set_title(f"(a) share of labels with >= 1 claim unsupported by held-out evidence; nulls at cutoff {last}, levels "
                f"{', '.join(map(str, lab['protocol']['levels']))}", pad=16)
    mm = lab["nulls"]
    txt = "model - null (at {}):  configuration {:+.2f} [{:+.2f}, {:+.2f}];  random labels {:+.2f} [{:+.2f}, {:+.2f}]".format(
        last, mm["configuration_null"]["model_minus_null"]["value"], *mm["configuration_null"]["model_minus_null"]["ci95"],
        mm["random_labels"]["model_minus_null"]["value"], *mm["random_labels"]["model_minus_null"]["ci95"])
    a.text(0.5, 1.01, txt + "  (dotted: model at the nulls' cutoff)", transform=a.transAxes, fontsize=7.5, va="bottom", ha="center", color="0.25")
    a.legend([Line2D([], [], marker="o", color="0.3", ls=""), Line2D([], [], marker="D", color="0.3", ls=""),
              Line2D([], [], marker="o", mfc="white", color=CFG, ls="")],
             ["per tree (metrics.json)", "pooled over null trees (metrics.json)",
              "config. null recomputed per label (L0/L1 key collision removed)"],
             frameon=False, fontsize=7, loc="lower right", ncol=3, bbox_to_anchor=(1.0, 0.08))

    names = ["model", *cfgs, *rls]
    cols = [MODEL] + [CFG] * len(cfgs) + [RL] * len(rls)
    J = [trees[t]["J"] for t in names]
    b.bar(range(len(names)), J, color=cols, alpha=0.8, width=0.6)
    for i, t in enumerate(names):
        b.text(i, J[i] + 0.015, f"{J[i]:.2f}", ha="center", fontsize=7)
    b.axhline(lab["j_min"], color="#D55E00", lw=1, ls="--")
    b.set_xticks(range(len(names)), ["model"] + [f"cfg {t[-1]}" for t in cfgs] + [f"rl {t[-1]}" for t in rls], fontsize=7.5)
    b.set_ylim(0, 1.1)
    b.set_ylabel("Youden J = Se + Sp - 1")
    b.set_title("(b) known-answer controls: Se = P(unsupp. | false member),\n"
                f"Sp = P(supp. | true member); dashed: validity gate J >= {lab['j_min']}", fontsize=8.5)

    by = {}
    for row in _label_rows(recs, "model"):
        cut, lv = row[0]["supernode"].split(":")
        by.setdefault((int(cut), int(lv[1:].split(".")[0])), []).append(any(not r["supported"] for r in row))
    cuts = sorted({k[0] for k in by})
    lvls = sorted({k[1] for k in by})
    for j, k in enumerate(lvls):
        for i, cu in enumerate(cuts):
            v, lo, hi = _boot(by[(cu, k)])
            _err(c, i + (j - 0.5) * 0.2, v, lo, hi, color=LEVEL[k], label=f"level {k}" if i == 0 else None)
    for i, cu in enumerate(cuts):
        c.text(i, 0.9, "n = " + " / ".join(str(len(by[(cu, k)])) for k in lvls), ha="center", fontsize=7, color="0.35")
    c.set_xticks(range(len(cuts)), cuts)
    c.set_xlim(-0.6, len(cuts) - 0.4)
    c.set_ylim(0, 1.12)
    c.set_yticks(np.linspace(0, 1, 6))
    c.set_xlabel("snapshot cutoff")
    c.set_ylabel("over-claim rate, 95% CI")
    c.set_title("(c) model tree by cutoff and level\n(from label_judgements.json; n = labels judged, level 0 / 1)", fontsize=8.5)
    c.legend(frameon=False, loc="upper center", ncol=2)
    fig.savefig(out / "labels.png")
    plt.close(fig)
    return {"model_by_cutoff_level": {f"{cu}:L{k}": dict(zip(("value", "lo", "hi"), _boot(v)), n=len(v)) for (cu, k), v in sorted(by.items())},
            "configuration_null_recomputed": {t: dict(zip(("value", "lo", "hi"), _boot(split[t])), n=len(split[t])) for t in cfgs}}


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
    derived = labels(m["labels"], json.loads((a.run / "label_judgements.json").read_text()), a.out)
    print(json.dumps(derived, indent=1))
    print("figures ->", a.out)


if __name__ == "__main__":
    main()
