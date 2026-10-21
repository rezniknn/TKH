"""Regenerates every number table in report.md from out/metrics.json (6a.3). No report number may come from anywhere else.

    python make_tables.py [--metrics out/metrics.json] [--report report.md] [--out out/tables.md]

Each table is a list of cells, each selected from metrics.json by exact field values; a
cell that matches no row, or more than one, stops the script (exit 1), so a table can
never silently show a stale or invented number. Tables go to out/tables.md and replace the
marked regions of report.md:  <!-- table:NAME --> ... <!-- /table:NAME -->
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
    v = fmt(r["value"], d)
    return v if r["ci_lo"] is None else f"{v} [{fmt(r['ci_lo'], d)}, {fmt(r['ci_hi'], d)}]"


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
    return cid


def variants(m):
    abl = list(m.meta["ablations"].values())
    cfgs = sorted((c for c in m.meta["configs"] if c != m.meta["selected"]), key=lambda c: m.meta["configs"][c])
    return ["model"] + cfgs + abl


NULLS = ["struct-null", "sem-null", "full-null", "random-labels"]


def t_data(m):
    cs = sorted({r["snapshot"] for r in m.rows if r["family"] == "data" and r["snapshot"]})
    spec = [("papers", "papers", 0), ("nodes", "nodes (all types)", 0), ("concept_nodes", "concept nodes (clustered)", 0),
            ("hyperedges", "hyper-edges (all relations)", 0), ("clustering_edges", "clustering edges (concept relations, hubs removed)", 0),
            ("clustering_edges_per_paper", "clustering edges per paper", 1), ("max_clustering_arity", "max clustering-edge arity", 0),
            ("hubs", "hubs removed (> 20% of papers)", 0), ("share_concept_in_at_most_one_edge", "concept nodes in ≤ 1 clustering edge", 2),
            ("share_pairs_H_zero_singletons", "node pairs sharing no clustering edge", 3)]
    body = [[label] + [fmt(m.get(family="data", metric=k, snapshot=c)["value"], d) for c in cs] for k, label, d in spec]
    cit = [m.get(family="E1", metric="coverage_n_citing_papers", variant="ruler", snapshot=c, split="all")["value"] for c in cs]
    body.append(["papers with citations (E1a ruler)"] + [fmt(v) for v in cit])
    q = m.get(family="data", metric="usable_questions")
    return md(["snapshot (cumulative)"] + [f"≤{c}" for c in cs], body) + \
        f"\n\nGround-truth questions usable for E1b/E4 (≥ 1 expected method matches a node): {q['value']} of {q['n']}."


def t_selection(m):
    rows = sorted((r for r in m.rows if r["family"] == "selection" and r["metric"] == "coupling_lift_halfA"), key=lambda r: r["alpha"])
    body = [[f"{r['alpha']:g}", fmt(r["value"]), fmt(r["value"] - r["ci_lo"]), fmt(r["giant_share"]), fmt(r["eligible"]),
             fmt(r["within_1se"]), "**selected**" if r["variant"] == m.meta["selected"] else ""] for r in rows]
    agr = m.get(family="selection", metric="winner_agreement")
    return md(["α", "E1a lift (half A)", "SE", "level-0 giant share", "eligible", "within 1 SE", ""], body) + \
        f"\n\nSame winner under {agr['n']} other cited-work splits: {fmt(agr['value'])}."


def t_e1(m):
    body = []
    for v in ["model"] + NULLS:
        cells = [m.get(family="E1", metric="coupling_lift", variant=v, snapshot=2026, level=k, stratum="pooled", split="B") for k in (0, 1, 2)]
        body.append([name_of(m, v) if v == "model" else v] + [ci(c) for c in cells])
    return md(["variant (E1a lift, ≤2026, split B, pooled)", "level 0 (15)", "level 1 (60)", "level 2 (240)"], body)


def t_e1_strict(m):
    body = []
    for v in ["model", "full-null", "random-labels"]:
        a = m.get(family="E1", metric="coupling_lift", variant=v, snapshot=2026, level=1, stratum="pooled", split="B")
        b = m.get(family="E1", metric="coupling_lift_strict_filter", variant=v, snapshot=2026, level=1, stratum="pooled", split="B")
        body.append([name_of(m, v) if v == "model" else v, ci(a), ci(b)])
    d0 = m.get(family="E1", metric="coverage_cited_works_dropped_by_residual_filter", variant="ruler", snapshot=2026, split="all")
    d1 = m.get(family="E1", metric="coverage_cited_works_dropped_by_residual_filter", variant="ruler-strict", snapshot=2026, split="B")
    return md(["E1a lift, ≤2026, level 1, split B, pooled", "pre-registered filter (exact name)", "strict filter (substring), sensitivity"], body) + \
        f"\n\nCited works removed by the residual filter at ≤2026: {d0['value']} (exact, all works); {d1['value']} (strict, half B)."


def t_e1_strata(m):
    body = []
    for v in ["model", "full-null"]:
        cells = [m.get(family="E1", metric="coupling_lift", variant=v, snapshot=2026, level=1, stratum=s, split="B")
                 for s in ("overlap", "no_overlap", "pooled", "all")]
        body.append([name_of(m, v) if v == "model" else v] + [ci(c) for c in cells])
    n = [m.get(family="E1", metric="coupling_lift", variant="model", snapshot=2026, level=1, stratum=s, split="B")["n"]
         for s in ("overlap", "no_overlap")]
    return md(["level 1, ≤2026, split B", "overlap pairs", "no-overlap pairs", "pooled", "unstratified"], body) + \
        f"\n\nPaper pairs: {n[0]} with a shared non-hub concept, {n[1]} without."


def t_configs(m):
    body = []
    for v in variants(m):
        e1 = m.get(family="E1", metric="coupling_lift", variant=v, snapshot=2026, level=1, stratum="pooled", split="B")
        e2 = m.get(family="E2", metric="perturbation_ari", variant=v, snapshot=2026, level=1)
        cx = m.get(family="E2", metric="cross_snapshot_ari", variant=v, snapshot=2026, level=1)
        lo = m.get(family="E2", metric="change_localisation_ratio", variant=v, snapshot=2026, level=1)
        e4 = m.get(family="E4", metric="first_cost_median", variant=v, snapshot=2026)
        r2 = m.get(family="E4", metric="recall@200", variant=v, snapshot=2026)
        g = m.get(family="structure", metric="giant_share_level0", variant=v, snapshot=2026)
        body.append([name_of(m, v), ci(e1), ci(e2), fmt(cx["value"]), fmt(lo["value"]), ci(e4, 0), fmt(r2["value"]), fmt(g["value"])])
    for v in ("full-null", "struct-null", "sem-null"):
        e1 = m.get(family="E1", metric="coupling_lift", variant=v, snapshot=2026, level=1, stratum="pooled", split="B")
        e2 = m.get(family="E2", metric="perturbation_ari", variant=v, snapshot=2026, level=1)
        cx = m.get(family="E2", metric="cross_snapshot_ari", variant=v, snapshot=2026, level=1)
        lo = m.get(family="E2", metric="change_localisation_ratio", variant=v, snapshot=2026, level=1)
        e4 = m.get(family="E4", metric="first_cost_median", variant=v, snapshot=2026)
        r2 = m.get(family="E4", metric="recall@200", variant=v, snapshot=2026)
        body.append([v, ci(e1), ci(e2), fmt(cx["value"]), fmt(lo["value"]), ci(e4, 0), fmt(r2["value"]), "–"])
    return md(["configuration (≤2026, level 1)", "E1a lift (B)", "perturbation ARI", "cross-snapshot ARI 2024→26",
               "change localisation", "E4 median cost", "E4 recall@200", "level-0 giant share"], body) + \
        "\n\nα = 1 ignores edges, so its perturbation ARI is 1 by construction (not a stability result). " \
        "Change localisation is undefined (–) when no untouched old node is reassigned."


def t_e2_localisation(m):
    body = []
    for v in ["model", m.meta["ablations"]["gamma0"], "full-null", "struct-null", "sem-null"]:
        cells = []
        for c in (2022, 2024, 2026):
            for k in (0, 1, 2):
                cells.append(fmt(m.get(family="E2", metric="change_localisation_ratio", variant=v, snapshot=c, level=k)["value"]))
        body.append([name_of(m, v) if not v.endswith("-null") else v] + cells)
    head = ["variant"] + [f"{t} L{k}" for t in ("20→22", "22→24", "24→26") for k in (0, 1, 2)]
    return md(head, body)


def t_e2_levels(m):
    body = []
    for v in ["model", m.meta["ablations"]["gamma0"], m.meta["ablations"]["freeze"], "full-null"]:
        cells = [m.get(family="E2", metric="perturbation_ari", variant=v, snapshot=2026, level=k) for k in (0, 1, 2)]
        xs = [m.get(family="E2", metric="cross_snapshot_ari", variant=v, snapshot=2026, level=k) for k in (0, 1, 2)]
        body.append([name_of(m, v) if v != "full-null" else v] + [ci(c) for c in cells] + [fmt(x["value"]) for x in xs])
    return md(["variant (≤2026)", "pert. ARI L0", "pert. ARI L1", "pert. ARI L2", "2024→26 ARI L0", "L1", "L2"], body)


def t_e3(m):
    judges = sorted({r["stratum"] for r in m.rows if r["family"] == "E3" and r["metric"] == "identification_rate"},
                    key=lambda j: (j != m.meta["labels"]["judge_model"], j))
    body = []
    for j in judges:
        for v in ("model", "random-clusters"):
            g = m.get(family="E3", metric="identification_rate", variant=v, snapshot=2026, level=None, stratum=j, split="forced_choice")
            o = m.get(family="E3", metric="over_claim_rate", variant=v, snapshot=2026, level=None, stratum=j, split="forced_choice")
            pz = m.get(family="E3", metric="choice_position_max_share", variant=v, snapshot=None, level=None, stratum=j, split="forced_choice")
            tag = " (primary)" if j == m.meta["labels"]["judge_model"] else ""
            body.append([j + tag, name_of(m, v) if v == "model" else v, g["n"], ci(g), ci(o), fmt(pz["value"])])
    allsnap = m.get(family="E3", metric="identification_rate", variant="model", snapshot=None, level=None,
                    stratum=m.meta["labels"]["judge_model"], split="forced_choice")
    fc = md(["judge", "labels (≤2026, levels 0–1)", "n", "identified among 4 (chance 0.25)", "over-claim = not identified",
             "most-chosen position share"], body)
    ab = []
    for v, split in (("model", "held_out"), ("swapped-gloss", "swapped"), ("random-clusters", "random_labels")):
        g = {k: m.get(family="E3", metric=f"abs_{k}_rate", variant=v, snapshot=2026, level=None, split=split)
             for k in ("over_claim", "vague", "accurate")}
        ab.append([v, g["accurate"]["n"], ci(g["accurate"]), ci(g["vague"]), ci(g["over_claim"])])
    det = {k: m.get(family="E3", metric=f"{k}_rate", variant="model", snapshot=None, level=None, split="held_out")
           for k in ("year_after_cutoff", "named_non_member", "future_entity")}
    single = m.get(family="E3", metric="single_concept_supernodes", variant="model")
    return fc + f"\n\nPrimary judge over all four snapshots: {ci(allsnap)} identified (n = {allsnap['n']}). " \
        f"'random-clusters' = the model's tree with concept nodes permuted, relabelled by the same labeller and judged on its own held-out half. " \
        f"{single['value']} of {single['n']} labelled super-nodes have a single concept; their judge sees only paper texts.\n\n" + \
        "Absolute rating by the primary judge (failed its negative control):\n\n" + \
        md(["labels judged against own held-out evidence (≤2026)", "n", "accurate", "vague", "wrong"], ab) + \
        "\n\nDeterministic checks (all snapshots, levels 0–1): " + \
        ", ".join(f"{k.replace('_', ' ')} {det[k]['k']}/{det[k]['n']}" for k in det) + "."


def t_e4(m):
    body = []
    for v in ["model", "flat-lexical", "ppr", "degree-popularity", "full-null", "struct-null", "sem-null", "random-labels"]:
        c = m.get(family="E4", metric="first_cost_median", variant=v, snapshot=2026)
        r5 = m.get(family="E4", metric="recall@50", variant=v, snapshot=2026)
        r2 = m.get(family="E4", metric="recall@200", variant=v, snapshot=2026)
        w = m.get(family="E4", metric="wrong@200", variant=v, snapshot=2026)
        body.append([name_of(m, v) if v == "model" else v, ci(c, 0), ci(r5), ci(r2), ci(w)])
    return md(["method (≤2026, 12 questions)", "median cost to first target", "recall@50", "recall@200", "wrong-domain@200"], body) + \
        "\n\nRanked baselines are scored by their expected value under random tie-breaking. 'degree-popularity' ignores the question."


def t_tests(m):
    body = [[t["family"], t["name"] + (f" — {t['note']}" if t.get("note") else ""), fmt(t["model"], 3), fmt(t.get("null_mean"), 3),
             pval(t["p"]), pval(t["p_holm"])] for t in m.tests if t["primary"]]
    return md(["family", "pre-registered primary test", "model", "null / baseline", "p", "p (Holm)"], body)


SECONDARY = ["E3 forced-choice identification model vs chance", "E3 forced-choice identification model vs random-clusters",
             "E3 absolute rating discriminates", "E4 cost hierarchy vs ppr", "E4 cost hierarchy vs degree-popularity",
             "E4 median cost model vs random-labels", "E4 median cost model vs full-null"]


def t_tests_secondary(m):
    body = [[t["family"], t["name"] + (f" — {t['note']}" if t.get("note") else ""), fmt(t["model"], 3), fmt(t.get("null_mean"), 3), pval(t["p"])]
            for t in m.tests if not t["primary"] and any(t["name"].startswith(x) for x in SECONDARY)]
    if not body:
        raise MissingCell("no secondary tests")
    return md(["family", "secondary / post-hoc test (descriptive, no correction)", "model", "null / baseline", "p"], body)


TABLES = {"data": t_data, "selection": t_selection, "e1": t_e1, "e1_strata": t_e1_strata, "e1_strict": t_e1_strict,
          "configs": t_configs, "e2_levels": t_e2_levels, "e2_localisation": t_e2_localisation, "e3": t_e3, "e4": t_e4,
          "tests": t_tests, "tests_secondary": t_tests_secondary}


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    p.add_argument("--metrics", type=Path, default=ROOT / "out" / "metrics.json")
    p.add_argument("--report", type=Path, default=ROOT / "report.md")
    p.add_argument("--out", type=Path, default=ROOT / "out" / "tables.md")
    args = p.parse_args(argv)
    m = Metrics(args.metrics)
    try:
        tables = {k: f(m) for k, f in TABLES.items()}
    except MissingCell as e:
        print(f"make_tables: missing cell: {e}", file=sys.stderr)
        return 1
    args.out.write_text("\n\n".join(f"## {k}\n\n{v}" for k, v in tables.items()) + "\n")
    report = args.report if str(args.report) not in ("", ".") and args.report.is_file() else None
    if report:
        text = report.read_text()
        for k, v in tables.items():
            text = re.sub(rf"(<!-- table:{k} -->)(.*?)(<!-- /table:{k} -->)", lambda mm: f"{mm.group(1)}\n{v}\n{mm.group(3)}", text, flags=re.S)
        report.write_text(text)
    print(f"{len(tables)} tables -> {args.out}" + (f" and {report}" if report else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())
