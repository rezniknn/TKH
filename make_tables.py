"""Regenerate every table of docs/report.md from the run outputs (deliverable §6a.3).

    python make_tables.py [--run out] [--report docs/report.md] [--check]

Each table sits between `<!-- table:NAME -->` and `<!-- /table:NAME -->` in the report; the script rewrites the block
from out/metrics.json (coherence, stability, faithfulness, retrieval), out/run_info.json, out/run_config.toml and
out/<t>/coarse_hyperedges.json. Verdict columns are computed from the p-values and intervals (ALPHA), never typed in.
--check exits 1 if any block is out of date, unknown or missing. Nothing is recomputed: the script only reads out/.
"""

from pathlib import Path
import argparse
import json
import re
import sys
import tomllib

ALPHA = 0.05          # significance level of the null tests
SCHEMES = ("interval", "year1", "year2", "year3", "gap")
BLOCK = re.compile(r"(<!-- table:(\w+) -->\n)(.*?)(<!-- /table:\2 -->)", re.S)


def f(x, nd=2):
    return "—" if x is None else f"{x:.{nd}f}"


def ci(v, lo, hi, nd=2):
    return f"{f(v, nd)} [{f(lo, nd)}, {f(hi, nd)}]"


def p(x):
    return "—" if x is None else f"{x:.3g}"


def md(header, rows):
    out = ["| " + " | ".join(header) + " |", "|" + "---|" * len(header)]
    out += ["| " + " | ".join(str(c) for c in r) + " |" for r in rows]
    return "\n".join(out) + "\n"


class Run:
    def __init__(self, run):
        self.dir = Path(run)
        self.m = json.loads((self.dir / "metrics.json").read_text())
        self.info = json.loads((self.dir / "run_info.json").read_text())
        self.cfg = tomllib.loads((self.dir / "run_config.toml").read_text())
        self.cutoffs = [str(c) for c in self.info["cutoffs"]]
        self.last = self.cutoffs[-1]


# ---------------------------------------------------------------- run, parameters, design

def t_data(r):
    rows = []
    for c in r.cutoffs:
        s = r.info["snapshots"][c]
        lv = s["levels"]
        rows.append([f"≤{c}", s["n_concept"], s["n_edges"], f"{len(s['hubs'])} (≥ {s['hub_threshold_papers']} papers)",
                     s["n_stable"], s["n_anchored"], " / ".join(f"{x['max_size']} ({x['cap']:.1f})" for x in lv)])
    return md(["Snapshot", "Concept nodes n_t", "Clustering edges", "Hubs (threshold)", "Stable set U_t",
               "Anchored nodes", "Largest super-node (cap) L0 / L1 / L2"], rows)


def t_params(r):
    mth, lab = r.cfg["method"], r.cfg["labels"]
    coh, st, ret = r.m["coherence"], r.m["stability"]["protocol"], r.m["retrieval"]["config"]
    rows = [["Snapshots (cutoffs)", ", ".join(r.cutoffs)],
            ["Budgets N_0, N_1, N_2", ", ".join(map(str, r.info["budgets"]))],
            ["α (semantic weight), γ (prior weight), ρ (size cap)", f"{mth['alpha']}, {mth['gamma']}, {mth['rho']}"],
            ["Edge weights, hub fraction h, LSA dimension", f"{mth['edge_weight']}, {mth['hub_frac']}, {mth['lsa_dim']}"],
            ["Labeller / judge (offline replay)", f"{lab['labeller_model']} / {lab['judge_model']}"],
            ["Label evidence: lines per half, split seed, contrast groups", f"{lab['max_items']}, {lab['seed']}, {lab['contrast']}"],
            ["Coherence nulls: configuration rebuilds, random-label permutations", f"{coh['R']}, {coh['R_labels']}"],
            ["Coherence period schemes (primary first); significance level of all null tests", f"{', '.join(SCHEMES)}; {ALPHA}"],
            ["Stability: perturbation seeds × edge fraction; new-paper null R", f"{len(st['seeds'])} × {st['frac']}; {st['R']}"],
            ["Retrieval: beam per level, answer length k", f"{'/'.join(map(str, ret['beam']))}, {ret['k']}"],
            ["Build runtime (s)", f"{r.info['runtime_s']}"]]
    return md(["Parameter", "Value"], rows)


def t_properties(r):
    rows = [["P1 laminarity, P2 budgets", "by construction (merge-only levels; budget lemma)", "`validate.py` on every run"],
            ["P4 hyper-edge fidelity", "by construction (score on the collapsed incidence; multi-way edges kept whole)", "§4"],
            ["No future information (structure, membership)", "by construction (snapshot-only edges, hubs, LSA, anchors)", "`validate.py` member cutoffs"],
            ["P3 semantic coherence", "empirical", "Tables 4–5, Fig. 1"],
            ["P5 temporal stability", "by construction (prior, persistent ids); size empirical", "Tables 6–8, Figs. 2–3"],
            ["P6 faithful labels", "empirical", "Table 9"],
            ["T6 extrinsic utility", "empirical", "Table 10"]]
    return md(["Property", "Status", "Evidence"], rows)


def t_literature(r):
    rows = [["h-Louvain [1]", "hyper-edge-aware affinity on the native incidence; multilevel aggregation",
             "no modularity or resolution parameter; exact nested budgets; a semantic term"],
            ["Featured Graph Coarsening [2]", "joint topology–feature coarsening",
             "on the hyper-edge incidence; greedy merges, not a learned coarse graph; no similarity guarantee claimed"],
            ["DynHAC [3]", "average linkage; confining change to affected regions",
             "a soft prior instead of affected-region recomputation (frozen regions would occupy budget slots); "
             "its locality theorem needs a reducible linkage, which H is not"],
            ["HyperEF 2.0 [4]", "contracting hyper-edges while keeping coarse edges explicit",
             "no ratio or spectral target (P2 fixes the counts); multi-way edges scored by the connectivity cut"]]
    return md(["Work", "Borrowed", "Done differently, and why"], rows)


def t_collapse(r):
    h = json.loads((r.dir / r.last / "coarse_hyperedges.json").read_text())
    lv = r.info["snapshots"][r.last]["levels"]
    rows = []
    for k in sorted(h, key=int):
        s, e = h[k]["summary"], h[k]["edges"]
        mw_p = sum(x["multiway"] and x["class"] == "partial" for x in e)
        mw_u = sum(x["multiway"] and x["class"] == "uncollapsed" for x in e)
        x = lv[int(k)]
        rows.append([f"L{k}", s["internal"], s["partial"], s["uncollapsed"], s["edges"], f"{s['multiway']} ({mw_p} + {mw_u})",
                     f"{x['multi_endpoint']} / {x['merges']}" + (f" ({x['multi_endpoint'] / x['merges']:.0%})" if x["merges"] else "")])
    return md(["Level", "Internal", "Partial", "Uncollapsed", "Edges", "Multi-way (partial + uncollapsed)",
               "Merges where native and clique scores differ"], rows)


# ---------------------------------------------------------------- coherence

def _sig(x):
    """Both nulls beaten at ALPHA (an undefined lift has p = None and never passes)."""
    a, b = x["configuration_null"]["p"], x["random_labels"]["p"]
    return a is not None and b is not None and max(a, b) <= ALPHA


def _below(cell):
    """The lift lies below the 2.5% quantile of both nulls under every scheme."""
    def b(x):
        lo = (x["configuration_null"]["q2.5"], x["random_labels"]["q2.5"])
        return x["lift"] is not None and None not in lo and min(lo) > x["lift"]
    return all(b(cell[s]) for s in SCHEMES)


def _passes(cell):
    return sum(_sig(cell[s]) for s in SCHEMES)


def _verdict(cell, strata):
    iv = cell["interval"]
    if iv["lift"] is None:
        return "undefined"
    if strata < 2:
        return "not evaluable (one interval-scheme stratum)"
    n = _passes(cell)
    if n == len(SCHEMES):
        return "**robust**"
    if _below(cell):
        return "below both nulls"
    if _sig(iv):
        return f"significant, {n}/{len(SCHEMES)} schemes"
    return f"not significant ({n}/{len(SCHEMES)} schemes)"


def t_coherence_coverage(r):
    rows = []
    for c in r.cutoffs:
        cov = r.m["coherence"]["snapshots"][c]["coverage"]
        e, z = cov["exact"], cov["fuzzy"]
        rows.append([f"≤{c}", e["citing_papers"], e["no_overlap_pairs"], f"{e['coupled_no_overlap_pairs']} / {z['coupled_no_overlap_pairs']}",
                     f"{e['filtered_citations']} / {z['filtered_citations']}", e["period_strata"]])
    return md(["Snapshot", "Citing papers", "No-overlap pairs", "Coupled pairs (exact / fuzzy)",
               "Filtered citations (exact / fuzzy)", "Period strata (interval scheme)"], rows)


def t_coherence(r):
    rows = []
    for c in r.cutoffs:
        snap = r.m["coherence"]["snapshots"][c]
        se, sz = snap["coverage"]["exact"]["period_strata"], snap["coverage"]["fuzzy"]["period_strata"]
        for k, lv in enumerate(snap["levels"]):
            e, z = lv["exact"], lv["fuzzy"]
            iv = e["interval"]
            cn, rl = iv["configuration_null"], iv["random_labels"]
            rows.append([f"≤{c}", f"L{k}", ci(iv["lift"], *iv["ci95"]) if iv["lift"] is not None else "—",
                         f"{f(cn['mean'])} / {f(rl['mean'])}", f"{p(cn['p'])} / {p(rl['p'])}",
                         f"{_passes(e)} / {_passes(z)}", _verdict(e, se), _verdict(z, sz)])
    return md(["Snapshot", "Level", "Lift, interval, exact [95% CI]", "Null means (config. / labels)", "p (config. / labels)",
               "Schemes passed (exact / fuzzy)", "Verdict, exact", "Verdict, fuzzy"], rows)


# ---------------------------------------------------------------- stability

def t_perturbation(r):
    rows = []
    for c in r.cutoffs:
        x = r.m["stability"]["perturbation"][c]
        rows.append([f"≤{c}", *(ci(a["mean"], a["lo"], a["hi"]) for a in x["ari"]), ci(x["hari"]["mean"], x["hari"]["lo"], x["hari"]["hi"])])
    return md(["Snapshot", "ARI L0", "ARI L1", "ARI L2", "HARI"], rows)


def t_cross(r):
    rows = []
    for tr, x in r.m["stability"]["cross_snapshot"].items():
        cells = [*x["ari"], x["hari"]]
        sig = [c["new_paper_null"]["p"] is not None and c["new_paper_null"]["p"] <= ALPHA for c in cells]
        rows.append([tr.replace("-", "→"), x["common_nodes"]["value"] if isinstance(x["common_nodes"], dict) else x["common_nodes"],
                     *(f"{f(c['value'])} vs {f(c['new_paper_null']['mean'])} (p {p(c['new_paper_null']['p'])})" for c in cells),
                     f"{sum(sig)}/{len(sig)}"])
    return md(["Transition", "Common nodes", "ARI L0: run vs null mean (p)", "ARI L1", "ARI L2", "HARI",
               f"Indices above the null (p ≤ {ALPHA}, uncorrected)"], rows)


def _untouched_share(x):
    tot = x["touched"] * x["reassign_touched"] + x["untouched"] * x["reassign_untouched"]
    return x["untouched"] * x["reassign_untouched"] / tot if tot else None


def _range_pct(xs):
    xs = [x for x in xs if x is not None]
    return f"{min(xs):.0%}–{max(xs):.0%}" if xs else "—"


def t_localisation(r):
    rows = []
    for tr, lvs in r.m["stability"]["localisation"].items():
        share = [_untouched_share(x) for x in lvs]
        rows.append([tr.replace("-", "→"), f"{lvs[0]['touched']} / {lvs[0]['untouched']}",
                     *(ci(x["ratio"], *x["ratio_ci95"]) if _ok(x["ratio_ci95"]) else f(x["ratio"]) for x in lvs),
                     " / ".join(f"{f(x['reassign_untouched'])}" for x in lvs), _range_pct(share),
                     f"{sum(_ok(x['ratio_ci95']) and x['ratio_ci95'][0] > 1 for x in lvs)}/{len(lvs)}"])
    return md(["Transition", "Old nodes touched / untouched", "Ratio L0 [95% CI]", "Ratio L1", "Ratio L2",
               "Untouched reassignment L0 / L1 / L2", "Share of reassignment on untouched", "Levels localised (CI > 1)"], rows)


# ---------------------------------------------------------------- labels, retrieval

def t_faithfulness(r):
    fa = r.m["faithfulness"]
    lv = fa["protocol"]["levels"]
    rows = [[f"All cutoffs, L{lv[0]}–L{lv[-1]}", fa["over_claim"]["n"], ci(fa["over_claim"]["value"], *fa["over_claim"]["ci95"]), f(fa["claim_unsupported"])]]
    rows += [[k, v["over_claim"]["n"], ci(v["over_claim"]["value"], *v["over_claim"]["ci95"]), f(v["claim_unsupported"])]
             for k, v in fa["by_level"].items()]
    rows += [[f"≤{c}", v["over_claim"]["n"], ci(v["over_claim"]["value"], *v["over_claim"]["ci95"]), f(v["claim_unsupported"])]
             for c, v in fa["by_cutoff"].items()]
    d = fa["deterministic"]
    tail = (f"\nLabels {fa['labels']}, judged {fa['judged']} (no held-out evidence: {fa['no_held_out']}); decomposition "
            f"passes its content check for {fa['decomposition_ok']:.0%}; cited-line rejections {fa['quote_rejected']}; "
            f"deterministic flags: year after cutoff {d['year_after_cutoff']}, named non-member {d['named_non_member']}, "
            f"future entity {d['future_entity']}.\n")
    return md(["Group", "Labels judged", "Over-claim rate [95% CI]", "Claim-level unsupported"], rows) + tail


RETRIEVAL_NAMES = {"methods": "hit-rate, methods", "method_claims": "hit-rate, method claims", "claims": "hit-rate, claims",
                   "citations": "hit-rate, citations", "error_rate": "error rate", "reached": "reach",
                   "steps_first": "steps to first item (median)", "steps_half": "steps to 50% of items (median)"}
LOWER_BETTER = frozenset({"error_rate", "steps_first", "steps_half"})


def _favoured(k, d):
    """Which system a paired difference (drill-down - flat) favours; a point estimate (no CIs)."""
    if d is None:
        return None
    return "tie" if abs(d) < 1e-12 else ("drill-down" if (d < 0) == (k in LOWER_BETTER) else "flat")


def _ok(b):
    return b is not None and None not in b


def t_retrieval(r):
    names = RETRIEVAL_NAMES
    rows = []
    for t, s in r.m["retrieval"]["summary"].items():
        unknown = {k for k, v in s.items() if isinstance(v, dict) and "stat" in v} - names.keys()
        assert not unknown, f"retrieval metrics without a label: {unknown}"
        for k, label in names.items():
            if k not in s:
                continue
            v = s[k]
            nd = 1 if k.startswith("steps") else 3
            d = v["hier_minus_flat"]
            rows.append([t, label, v["n"], f(v["hier"], nd), f(v["flat"], nd), "—" if d is None else f"{d:+.{nd}f}",
                         _favoured(k, d) or "—"])
    dg = r.m["retrieval"]["diagnostics"]
    tail = ("\nDrill-down diagnostics: kept/frontier " + ", ".join(f"{lv} {x['mean']:.2f}" for lv, x in dg["kept_over_frontier"].items())
            + f"; super-nodes scored per question {dg['supernodes_scored']['min']}–{dg['supernodes_scored']['max']}; never reached: "
            + (", ".join(f"{q} (lost at L{lv})" for q, lv in dg["never_reached"].items()) or "none") + ".\n")
    return md(["Type", "Metric", "n", "Drill-down", "Flat", "Paired difference (mean; steps: median)", "Favoured (point estimate)"], rows) + tail


def t_findings(r):
    """Headline verdicts, computed with the same rules as Tables 5-10."""
    c = r.m["coherence"]["snapshots"]
    def cells(pred, m="exact"):
        return [f"≤{t} L{k}" for t in r.cutoffs for k, lv in enumerate(c[t]["levels"]) if pred(lv[m], c[t]["coverage"][m]["period_strata"])]
    rob = cells(lambda x, s: s >= 2 and _passes(x) == len(SCHEMES))
    rob_f = cells(lambda x, s: s >= 2 and _passes(x) == len(SCHEMES), "fuzzy")
    below = cells(lambda x, s: s >= 2 and x["interval"]["lift"] is not None and _below(x))
    below_f = cells(lambda x, s: s >= 2 and x["interval"]["lift"] is not None and _below(x), "fuzzy")
    cs = r.m["stability"]["cross_snapshot"]
    idx = [v for x in cs.values() for v in [*x["ari"], x["hari"]]]
    above = sum(v["new_paper_null"]["p"] is not None and v["new_paper_null"]["p"] <= ALPHA for v in idx)
    pt = r.m["stability"]["perturbation"]
    loc = [x for lvs in r.m["stability"]["localisation"].values() for x in lvs]
    nloc = sum(_ok(x["ratio_ci95"]) and x["ratio_ci95"][0] > 1 for x in loc)
    fa = r.m["faithfulness"]
    oc = fa["over_claim"]
    lv, lv_names = list(fa["by_level"].values()), list(fa["by_level"])
    if not _ok(oc["ci95"]):
        oc_q = "not evaluable"
    else:
        oc_q = "majority of labels" if oc["ci95"][0] > 0.5 else ("minority of labels" if oc["ci95"][1] < 0.5 else "not distinguishable from one half")
    if len(lv) < 2:
        lv_row = ["P6 over-claim by level", "one level only", "", "Table 9"]
    else:
        a, b = lv[0]["over_claim"]["ci95"], lv[-1]["over_claim"]["ci95"]
        sep = "not evaluable" if not (_ok(a) and _ok(b)) else ("CIs do not overlap" if a[1] < b[0] or b[1] < a[0] else "CIs overlap")
        lv_row = [f"P6 {lv_names[0]} vs {lv_names[-1]} over-claim",
                  f"{f(lv[0]['over_claim']['value'])} vs {f(lv[-1]['over_claim']['value'])}", sep, "Table 9"]
    fav = {"drill-down": 0, "flat": 0, "tie": 0}
    for s in r.m["retrieval"]["summary"].values():
        for k in RETRIEVAL_NAMES:
            if k in s and (fv := _favoured(k, s[k]["hier_minus_flat"])):
                fav[fv] += 1
    steps = [(t, s["steps_first"]) for t, s in r.m["retrieval"]["summary"].items() if "steps_first" in s]
    rows = [["P3 coherence beyond both nulls (robust: all schemes, exact filter)", ", ".join(rob) or "none",
             f"fuzzy filter: {', '.join(rob_f) or 'none'}", "Table 5"],
            ["P3 cells below both nulls in every scheme (exact filter)", ", ".join(below) or "none",
             f"fuzzy filter: {', '.join(below_f) or 'none'}", "Table 5"],
            ["P5 cross-snapshot indices above the new-paper null", f"{above} of {len(idx)}", f"p ≤ {ALPHA}, uncorrected", "Table 7"],
            ["P5 perturbation HARI, first → last snapshot", f"{f(pt[r.cutoffs[0]]['hari']['mean'])} → {f(pt[r.last]['hari']['mean'])}", "", "Table 6"],
            ["P5 localised level × transition cells (ratio CI > 1)", f"{nloc} of {len(loc)}",
             "untouched share of reassignment " + _range_pct([_untouched_share(x) for x in loc]), "Table 8"],
            ["P6 over-claim rate", ci(oc["value"], *oc["ci95"]), oc_q, "Table 9"],
            lv_row,
            ["T6 retrieval measures favouring drill-down / flat / tie", f"{fav['drill-down']} / {fav['flat']} / {fav['tie']}",
             "point estimates, no CIs", "Table 10"],
            ["T6 median steps to first item, drill-down vs flat", "; ".join(f"type {t}: {f(x['hier'], 1)} vs {f(x['flat'], 1)}" for t, x in steps) or "—", "", "Table 10"]]
    return md(["Finding", "Result", "Qualifier", "Source"], rows)


TABLES = {"findings": t_findings, "data": t_data, "params": t_params, "properties": t_properties, "literature": t_literature,
          "collapse": t_collapse, "coherence_coverage": t_coherence_coverage, "coherence": t_coherence,
          "perturbation": t_perturbation, "cross_snapshot": t_cross, "localisation": t_localisation,
          "faithfulness": t_faithfulness, "retrieval": t_retrieval}


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--run", default="out")
    ap.add_argument("--report", default="docs/report.md")
    ap.add_argument("--check", action="store_true", help="exit 1 if the report's tables are not up to date")
    a = ap.parse_args(argv)
    r, path = Run(a.run), Path(a.report)
    text = path.read_text()
    found = [m.group(2) for m in BLOCK.finditer(text)]
    stray = [l for l in BLOCK.sub("", text).splitlines() if l.lstrip().startswith("|")]
    if stray or len(found) != len(set(found)):
        sys.exit(f"{path}: tables outside generated blocks {stray[:3]} or duplicate blocks {sorted(found)}")
    unknown, missing = set(found) - set(TABLES), set(TABLES) - set(found)
    if unknown or missing:
        sys.exit(f"{path}: unknown table blocks {sorted(unknown)}, missing {sorted(missing)}")
    new = BLOCK.sub(lambda m: m.group(1) + TABLES[m.group(2)](r) + m.group(4), text)
    if a.check:
        if new != text:
            sys.exit(f"{path}: tables are out of date; run python make_tables.py")
        print(f"{path}: {len(found)} tables up to date")
        return
    path.write_text(new)
    print(f"{path}: {len(found)} tables regenerated from {a.run}/")


if __name__ == "__main__":
    main()
