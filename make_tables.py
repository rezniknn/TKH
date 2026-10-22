"""Regenerates every number table in report.md from out/metrics.json (6a.3). No report number may come from anywhere else.

    python make_tables.py [--metrics out/metrics.json] [--report report.md] [--out out/tables.md]

Each table is a list of cells, each selected from metrics.json by exact field values; a cell that matches no row, or
more than one, stops the script (exit 1), so a table can never silently show a stale or invented number. Tables go
to out/tables.md and replace the marked regions of report.md:  <!-- table:NAME --> ... <!-- /table:NAME -->
"""

from pathlib import Path
import argparse
import json
import re
import sys

ROOT = Path(__file__).resolve().parent


class MissingCell(LookupError):
    pass


class Metrics:
    def __init__(self, path):
        d = json.loads(Path(path).read_text())
        self.meta, self.rows, self.tests = d["meta"], d["rows"], d["tests"]

    def get(self, **sel):
        hits = [r for r in self.rows if all(r.get(k) == v for k, v in sel.items())]
        if len(hits) != 1:
            raise MissingCell(f"{len(hits)} rows match {sel}")
        return hits[0]

    def maybe(self, **sel):
        hits = [r for r in self.rows if all(r.get(k) == v for k, v in sel.items())]
        if len(hits) > 1:
            raise MissingCell(f"{len(hits)} rows match {sel}")
        return hits[0] if hits else None

    def test(self, name, **cell):
        hits = [t for t in self.tests if t["name"] == name and all(t["cell"].get(k) == v for k, v in cell.items())]
        if len(hits) != 1:
            raise MissingCell(f"{len(hits)} tests match {name} {cell}")
        return hits[0]


def fmt(x, d=2):
    if x is None:
        return "–"
    if isinstance(x, bool):
        return "yes" if x else "no"
    if isinstance(x, int):
        return str(x)
    return f"{x:.{d}f}"


def ci(r, d=2):
    if r is None:
        return "–"
    v = fmt(r["value"], d)
    return v if r.get("ci_lo") is None else f"{v} [{fmt(r['ci_lo'], d)}, {fmt(r['ci_hi'], d)}]"


def pval(p):
    return "–" if p is None else ("<0.001" if p < 0.001 else f"{p:.3f}")


def md(header, body):
    out = ["| " + " | ".join(header) + " |", "|" + "|".join("---" for _ in header) + "|"]
    out += ["| " + " | ".join(map(str, r)) + " |" for r in body]
    return "\n".join(out)


def name_of(m, cid):
    if cid == "model":
        return f"**SHAC-T (selected, α={m.meta['selected_params']['alpha']:g})**"
    for name, c in m.meta["ablations"].items():
        if c == cid:
            return f"ablation: {name}"
    if cid in m.meta["configs"]:
        return f"α = {m.meta['configs'][cid]:g}"
    if cid == m.meta.get("baseline"):
        return "baseline: paper linkage (not SHAC-T)"
    return cid


def variants(m):
    cfgs = sorted((c for c in m.meta["configs"] if c != m.meta["selected"]), key=lambda c: m.meta["configs"][c])
    return ["model"] + cfgs + list(m.meta["ablations"].values()) + [m.meta["baseline"]]


C, L = 2026, 1


def t_data(m):
    cs = sorted({r["snapshot"] for r in m.rows if r["family"] == "data" and r["snapshot"]})
    spec = [("papers", "papers", 0), ("nodes", "nodes (all types)", 0), ("concept_nodes", "concept nodes (evaluation scope)", 0),
            ("hyperedges", "hyper-edges (all relations)", 0), ("clustering_edges", "concept-relation edges (hubs removed)", 0),
            ("hubs", "hubs (> 20% of papers)", 0), ("share_concept_in_at_most_one_edge", "concept nodes in ≤ 1 concept-relation edge", 2)]
    body = [[label] + [fmt(m.get(family="data", metric=k, snapshot=c)["value"], d) for c in cs] for k, label, d in spec]
    body.append(["papers with citations (M1 ruler)"] + [fmt(m.get(family="M1", metric="coverage_n_citing_papers", variant="ruler", snapshot=c)["value"]) for c in cs])
    return md(["snapshot (cumulative)"] + [f"≤{c}" for c in cs], body)


def t_selection(m):
    rows = sorted((r for r in m.rows if r["family"] == "selection" and r["metric"] == "coupling_lift_dev"), key=lambda r: r["alpha"])
    body = [[f"{r['alpha']:g}", ci(r), fmt(r["se"]), fmt(r["giant_share"]), fmt(r["within_1se"]),
             "**selected**" if r["variant"] == m.meta["selected"] else ""] for r in rows]
    return md(["α", "M1 no-overlap lift, dev half A", "jackknife SE", "level-0 giant share", "within 1 SE", ""], body)


def t_m1(m):
    body = []
    for v in ("model", "configuration-null", "random-labels"):
        cells = [ci(m.get(family="M1", metric="coupling_lift", variant=v, snapshot=C, level=k, stratum="no_overlap", split="B")) for k in (0, 1, 2)]
        body.append([name_of(m, v) if v == "model" else v] + cells)
    t = m.test("M1 coupling lift vs configuration null", snapshot=C, level=L, stratum="no_overlap", split="B")
    strata = [ci(m.get(family="M1", metric="coupling_lift", variant="model", snapshot=C, level=L, stratum=s, split="B")) for s in ("overlap", "pooled")]
    return md(["M1 lift, ≤2026, no-overlap stratum, report half B", "level 0 (15)", "level 1 (60)", "level 2 (240)"], body) + \
        f"\n\nPrimary test, level 1 vs the configuration null: p = {pval(t['p'])} (R = {t['R']}). " \
        f"Descriptive strata of the selected model, level 1: overlap {strata[0]}, pooled {strata[1]}."


def t_m2(m):
    body = []
    for v in ("model", "configuration-null"):
        h = m.get(family="M2", metric="perturbation_hari", variant=v, snapshot=C, stratum="all")
        s = m.maybe(family="M2", metric="perturbation_hari", variant=v, snapshot=C, stratum="concept")
        x = [ci(m.get(family="M2", metric="cross_snapshot_hari", variant=v, snapshot=c)) for c in (2022, 2024, 2026)]
        body.append([name_of(m, v) if v == "model" else v, ci(h), ci(s)] + x)
    lv = [ci(m.get(family="M2", metric="perturbation_ari", variant="model", snapshot=C, level=k, stratum="all")) for k in (0, 1, 2)]
    return md(["variant", "perturbation HARI (10% of all edges)", "… concept relations only", "cross-snapshot HARI 20→22",
               "22→24", "24→26"], body) + f"\n\nPer-level perturbation ARI of the selected model (≤2026): level 0 {lv[0]}, level 1 {lv[1]}, level 2 {lv[2]}."


def t_m2_local(m):
    body = []
    for v in ("model", "configuration-null"):
        cells = [ci(m.get(family="M2", metric="change_localisation", variant=v, snapshot=c, level=k)) for c in (2022, 2024, 2026) for k in (0, 1, 2)]
        body.append([name_of(m, v) if v == "model" else v] + cells)
    head = ["variant"] + [f"{t} L{k}" for t in ("20→22", "22→24", "24→26") for k in (0, 1, 2)]
    return md(head, body)


def t_events(m):
    kinds = ("continue", "growth", "change", "merge", "split", "birth", "death")
    body = []
    for c in (2022, 2024, 2026):
        for k in (0, 1, 2):
            body.append([f"→{c}", k] + [fmt(m.get(family="M2", metric=f"events_{e}", variant="model", snapshot=c, level=k)["value"]) for e in kinds])
    return md(["transition", "level"] + list(kinds), body)


def t_m3_det(m):
    det = [m.get(family="M3", metric=f"det_{k}_rate", variant="model") for k in ("year_after_cutoff", "named_non_member", "future_entity")]
    return "Deterministic checks (all snapshots, levels 0–1): " + \
        ", ".join(f"{n} {d['k']}/{d['n']} {ci(d)}" for n, d in zip(("year after cutoff", "named non-member", "future entity"), det)) + "."


def t_m3(m):
    g = lambda k: m.get(family="M3", metric=k, variant="model")  # noqa: E731
    if not m.maybe(family="M3", metric="valid", variant="model"):
        return "The M3 LLM judge is deferred in this run (`[m3] enabled = false` in `configs/eval.toml`). " + t_m3_det(m)
    valid = g("valid")["value"]
    body = [["over-claim, held-out evidence (raw)", ci(g("raw_over_claim_held_out")), g("raw_over_claim_held_out")["n"]],
            ["over-claim, all members (raw)", ci(g("raw_over_claim_all")), g("raw_over_claim_all")["n"]],
            ["over-claim, held-out, corrected for judge error", ci(g("corrected_over_claim_held_out")), g("corrected_over_claim_held_out")["n"]]]
    for t in ("swap", "sibling", "inflation", "temporal"):
        r = m.maybe(family="M3", metric=f"Se_{t}", variant="model")
        if r:
            body.append([f"judge sensitivity Se, {t} controls", ci(r), r["n"]])
    body.append(["judge specificity Sp, true controls", ci(g("Sp")), g("Sp")["n"]])
    body.append(["Youden J on hard (sibling) controls", fmt(g("J_sibling")["value"]), g("J_sibling")["n"]])
    body.append(["decompositions passing the check", fmt(g("decomposition_ok")["value"]), "–"])
    body.append(["'supported' verdicts rejected by the quote check", fmt(g("quote_rejections")["value"]), "–"])
    return md(["M3 (judge: " + str(m.meta["labels"]["judge_model"]) + ", ≤2026, levels 0–1)", "value", "n"], body) + \
        f"\n\nValidity gate (J ≥ 0.4): **{'passed' if valid else 'FAILED — the over-claim rate is not interpretable'}**. " + t_m3_det(m)


def t_m4(m):
    body = []
    for v, s in (("model", "hierarchy (members)"), ("model", "hierarchy (labels)"), ("flat", "flat"), ("ppr", "ppr"),
                 ("degree", "degree"), ("best flat", "best flat"), ("configuration-null", "hierarchy (members)")):
        c = m.get(family="M4", metric="first_cost", variant=v, snapshot=C, stratum=s)
        r50 = m.maybe(family="M4", metric="recall@50", variant=v, snapshot=C, stratum=s)
        r200 = m.maybe(family="M4", metric="recall@200", variant=v, snapshot=C, stratum=s)
        label = {"model": f"{name_of(m, 'model')}, {s.split('(')[1][:-1]} profiles"}.get(v, v)
        body.append([label, ci(c, 0), ci(r50), ci(r200)])
    q = m.get(family="M4", metric="first_cost", variant="model", snapshot=C, stratum="hierarchy (members)")
    return md(["method (≤2026)", "mean cost to the target", "recall@50", "recall@200"], body) + \
        f"\n\n{q.get('queries')} known-item queries over {q['n']} targets; means and 95% intervals by bootstrap over targets."


def t_m4_degree(m):
    bins = sorted({r["split"] for r in m.rows if r["family"] == "M4" and r["metric"] == "first_cost_by_target_degree"})
    body = []
    for v, s in (("model", "hierarchy (members)"), ("flat", "flat"), ("ppr", "ppr"), ("degree", "degree")):
        body.append([v if v != "model" else "selected hierarchy"] + [ci(m.get(family="M4", metric="first_cost_by_target_degree", variant=v, snapshot=C, stratum=s, split=b), 0) for b in bins])
    return md(["mean cost by target popularity"] + bins, body)


def t_mde(m):
    fr = sorted({r["split"] for r in m.rows if r["family"] == "MDE"}, key=lambda s: float(s.split()[1]))
    b1 = [ci(m.get(family="MDE", metric="coupling_lift_dev", variant="model", split=f)) for f in fr]
    b4 = [ci(m.maybe(family="MDE", metric="m4_first_cost", variant="model", split=f), 0) for f in fr]
    return md(["metric under path-swap degradation"] + [f.replace("swap ", "") for f in fr],
              [["M1 no-overlap lift (dev, level 1)"] + b1, ["M4 mean cost (members)"] + b4])


def t_variants(m):
    body = []
    for v in variants(m):
        e1 = m.maybe(family="M1", metric="coupling_lift", variant=v, snapshot=C, level=L, stratum="no_overlap", split="B")
        e2 = m.maybe(family="M2", metric="perturbation_hari", variant=v, snapshot=C, stratum="all")
        x = m.maybe(family="M2", metric="cross_snapshot_hari", variant=v, snapshot=C)
        e4 = m.maybe(family="M4", metric="first_cost", variant=v, snapshot=C, stratum="hierarchy (members)")
        d = [m.maybe(family="compare", metric=f"delta_{f}", variant=v) for f in ("M1", "M2", "M4")]
        body.append([name_of(m, v), ci(e1), ci(e2), fmt(x["value"]) if x else "–", ci(e4, 0)] + [ci(x_, 2 if i < 2 else 0) if v != "model" else "–" for i, x_ in enumerate(d)])
    return md(["run", "M1 no-overlap (B)", "perturbation HARI", "cross-snapshot HARI 24→26", "M4 mean cost",
               "Δ M1 (dev A)", "Δ perturbation HARI", "Δ M4 cost"], body) + \
        "\n\nΔ = run minus the selected model, paired: M1 by jackknife over shared citing papers, M2 by perturbation seed, M4 by target."


def t_tests(m):
    body = [[t["family"], t["name"], fmt(t["model"], 3), fmt(t.get("null_mean"), 3), pval(t["p"]), pval(t["p_holm"])]
            for t in m.tests if t["primary"]]
    return md(["family", "pre-registered primary test", "model", "null / baseline", "p", "p (Holm)"], body)


SECONDARY = [("M1 coupling lift vs random-labels", dict(snapshot=C, level=L, stratum="no_overlap", split="B")),
             ("M2 cross-snapshot HARI vs configuration null", dict(snapshot=C)),
             ("M4 cost hierarchy (members) vs best flat", dict(snapshot=C)),
             ("M4 cost hierarchy (members) vs configuration null", dict(snapshot=C))]


def t_tests_secondary(m):
    body = []
    for name, cell in SECONDARY:
        t = m.test(name, **cell)
        body.append([t["family"], name, fmt(t["model"], 3), fmt(t.get("null_mean"), 3), pval(t["p"])])
    return md(["family", "secondary test (descriptive, no correction)", "model", "null / baseline", "p"], body)


TABLES = {"data": t_data, "selection": t_selection, "m1": t_m1, "m2": t_m2, "m2_local": t_m2_local, "events": t_events,
          "m3": t_m3, "m4": t_m4, "m4_degree": t_m4_degree, "mde": t_mde, "variants": t_variants, "tests": t_tests,
          "tests_secondary": t_tests_secondary}


def figures(m, figdir):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    figdir.mkdir(parents=True, exist_ok=True)
    grid = sorted(m.meta["configs"], key=lambda c: m.meta["configs"][c])
    alphas = [m.meta["configs"][c] for c in grid]
    name = lambda c: "model" if c == m.meta["selected"] else c  # noqa: E731
    panels = [("M1 no-overlap lift (≤2026, L1, report half B)", dict(family="M1", metric="coupling_lift", snapshot=C, level=L, stratum="no_overlap", split="B")),
              ("perturbation HARI (≤2026, 10% of all edges)", dict(family="M2", metric="perturbation_hari", snapshot=C, stratum="all")),
              ("M4 mean cost to target (≤2026, lower is better)", dict(family="M4", metric="first_cost", snapshot=C, stratum="hierarchy (members)"))]
    fig, axes = plt.subplots(1, 3, figsize=(12, 3.3))
    for ax, (title, sel) in zip(axes, panels):
        vals = [m.get(variant=name(c), **sel) for c in grid]
        y = [r["value"] for r in vals]
        lo = [r["value"] - (r["ci_lo"] if r["ci_lo"] is not None else r["value"]) for r in vals]
        hi = [(r["ci_hi"] if r["ci_hi"] is not None else r["value"]) - r["value"] for r in vals]
        ax.errorbar(alphas, y, yerr=[lo, hi], marker="o", capsize=3, color="C0", label="SHAC-T")
        nr = m.get(variant="configuration-null", **sel)
        if nr["ci_lo"] is not None:
            ax.axhspan(nr["ci_lo"], nr["ci_hi"], color="0.85", label="configuration null 95% range")
        ax.axhline(nr["value"], color="0.5", lw=1)
        bl = m.maybe(variant=m.meta["baseline"], **sel)
        if bl:
            ax.axhline(bl["value"], color="C3", ls=":", lw=1, label="paper-linkage baseline")
        ax.axvline(m.meta["selected_params"]["alpha"], color="C1", lw=0.8, ls="-.")
        ax.set_title(title, fontsize=9); ax.set_xlabel("α (semantic weight)")
    axes[0].legend(frameon=False, fontsize=7)
    fig.tight_layout(); fig.savefig(figdir / "report_alpha.png", dpi=160); plt.close(fig)
    fr = sorted({r["split"] for r in m.rows if r["family"] == "MDE"}, key=lambda s: float(s.split()[1]))
    xs = [float(f.split()[1]) for f in fr]
    fig, axes = plt.subplots(1, 2, figsize=(8, 3))
    for ax, (met, title) in zip(axes, (("coupling_lift_dev", "M1 no-overlap lift (dev)"), ("m4_first_cost", "M4 mean cost (members)"))):
        rs = [m.maybe(family="MDE", metric=met, variant="model", split=f) for f in fr]
        ok = [(x, r) for x, r in zip(xs, rs) if r]
        ax.errorbar([x for x, _ in ok], [r["value"] for _, r in ok],
                    yerr=[[r["value"] - (r["ci_lo"] or r["value"]) for _, r in ok], [(r["ci_hi"] or r["value"]) - r["value"] for _, r in ok]],
                    marker="o", capsize=3)
        ax.set_xlabel("share of nodes whose path is swapped"); ax.set_title(title, fontsize=9)
    fig.tight_layout(); fig.savefig(figdir / "report_mde.png", dpi=160); plt.close(fig)
    return [figdir / "report_alpha.png", figdir / "report_mde.png"]


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    p.add_argument("--metrics", type=Path, default=ROOT / "out" / "metrics.json")
    p.add_argument("--report", type=Path, default=ROOT / "report.md")
    p.add_argument("--out", type=Path, default=ROOT / "out" / "tables.md")
    p.add_argument("--figures", type=Path, default=None)
    args = p.parse_args(argv)
    m = Metrics(args.metrics)
    try:
        tables = {k: f(m) for k, f in TABLES.items()}
    except MissingCell as e:
        print(f"make_tables: missing cell: {e}", file=sys.stderr)
        return 1
    args.out.write_text("\n\n".join(f"## {k}\n\n{v}" for k, v in tables.items()) + "\n")
    report = args.report if str(args.report) not in ("", ".") and args.report.is_file() else None
    try:
        figs = figures(m, args.figures or (ROOT / "figures" if report else args.out.parent / "figures"))
    except MissingCell as e:
        print(f"make_tables: missing cell for a figure: {e}", file=sys.stderr)
        return 1
    if report:
        text = report.read_text()
        for k, v in tables.items():
            text = re.sub(rf"(<!-- table:{k} -->)(.*?)(<!-- /table:{k} -->)", lambda mm: f"{mm.group(1)}\n{v}\n{mm.group(3)}", text, flags=re.S)
        report.write_text(text)
    print(f"{len(tables)} tables -> {args.out}" + (f" and {report}" if report else "") + f"; {len(figs)} figures -> {figs[0].parent}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
