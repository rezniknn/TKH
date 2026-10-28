"""Regenerate every table of docs/report.md from the run outputs (deliverable §6a.3).

    python make_tables.py [--run out] [--report docs/report.md] [--check]
    python make_tables.py --sweep out/sweep [--report docs/alpha_sweep.md] [--check]

Each table sits between `<!-- table:NAME -->` and `<!-- /table:NAME -->` in the report; the script rewrites the block
from out/metrics.json (coherence, stability, faithfulness, retrieval), out/run_info.json, out/run_config.toml and
out/<t>/coarse_hyperedges.json. Verdict columns are computed from the p-values and intervals (ALPHA), never typed in.
With --sweep DIR the script renders the α-sweep tables (DIR/<α>/ runs and DIR/sweep.json), including the
recommendation, into docs/alpha_sweep.md. --check exits 1 if any block is out of date, unknown or missing. Nothing is
recomputed: the script only reads the run outputs.
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


def _cells(r, pred, m="exact"):
    c = r.m["coherence"]["snapshots"]
    return [f"≤{t} L{k}" for t in r.cutoffs for k, lv in enumerate(c[t]["levels"]) if pred(lv[m], c[t]["coverage"][m]["period_strata"])]


def _robust(r, m="exact"):
    return _cells(r, lambda x, s: s >= 2 and _passes(x) == len(SCHEMES), m)


def _below_cells(r, m="exact"):
    return _cells(r, lambda x, s: s >= 2 and x["interval"]["lift"] is not None and _below(x), m)


def _above_null(r):
    """(cross-snapshot indices above the new-paper null at ALPHA, all indices)."""
    idx = [v for x in r.m["stability"]["cross_snapshot"].values() for v in [*x["ari"], x["hari"]]]
    return sum(v["new_paper_null"]["p"] is not None and v["new_paper_null"]["p"] <= ALPHA for v in idx), idx


def _localised(r):
    """(level x transition cells whose ratio CI lies above 1, all cells)."""
    loc = [x for lvs in r.m["stability"]["localisation"].values() for x in lvs]
    return sum(_ok(x["ratio_ci95"]) and x["ratio_ci95"][0] > 1 for x in loc), loc


def _favour_counts(r):
    fav = {"drill-down": 0, "flat": 0, "tie": 0}
    for s in r.m["retrieval"]["summary"].values():
        for k in RETRIEVAL_NAMES:
            if k in s and (fv := _favoured(k, s[k]["hier_minus_flat"])):
                fav[fv] += 1
    return fav


def t_findings(r):
    """Headline verdicts, computed with the same rules as Tables 5-10."""
    rob, rob_f = _robust(r), _robust(r, "fuzzy")
    below, below_f = _below_cells(r), _below_cells(r, "fuzzy")
    above, idx = _above_null(r)
    pt = r.m["stability"]["perturbation"]
    nloc, loc = _localised(r)
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
    fav = _favour_counts(r)
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


# ---------------------------------------------------------------- α sweep (docs/alpha_sweep.md)

class Sweep:
    """The runs of an α sweep (DIR/<α>/, each read like out/) and DIR/sweep.json (paired comparisons with the reference)."""

    def __init__(self, d):
        self.dir = Path(d)
        self.s = json.loads((self.dir / "sweep.json").read_text())
        self.alphas = self.s["alphas"]
        self.ref = self.s["reference"]
        self.runs = {a: Run(self.dir / self.s["variants"][f"{a:g}"]["run"]) for a in self.alphas}
        fixed = {a: {k: v for k, v in r.info["params"].items() if k != "alpha"} for a, r in self.runs.items()}
        assert all(x == fixed[self.ref] for x in fixed.values()), f"sweep runs differ in more than alpha: {fixed}"
        assert all(r.info["params"]["alpha"] == a for a, r in self.runs.items())
        self.fixed = fixed[self.ref]
        self.cutoffs, self.last = self.runs[self.ref].cutoffs, self.runs[self.ref].last

    def v(self, a):
        return self.s["variants"][f"{a:g}"]


def _a(a, ref=None):
    return f"{a:g}" + (" (default)" if a == ref else "")


def _hari_last(r):
    h = r.m["stability"]["perturbation"][r.last]["hari"]
    return h["mean"], h["lo"], h["hi"]


def _overclaim(r):
    oc = r.m["faithfulness"]["over_claim"]
    return oc["value"], *oc["ci95"]


def st_setup(w):
    r = w.runs[w.ref]
    fx = w.fixed
    rows = [["α (semantic weight; 0 = structure only, 1 = semantics only)", ", ".join(f"{a:g}" for a in w.alphas)],
            ["Fixed at the defaults: γ, ρ, edge weights, hub fraction h, LSA dimension",
             f"{fx['gamma']}, {fx['rho']}, {fx['edge_weight']}, {fx['hub_frac']}, {fx['lsa_dim']}"],
            ["Snapshots; budgets N_0, N_1, N_2", f"{', '.join(r.cutoffs)}; {', '.join(map(str, r.info['budgets']))}"],
            ["Per α: coherence nulls (configuration rebuilds at that α, random labels)",
             ", ".join(sorted({f"{x.m['coherence']['R']}, {x.m['coherence']['R_labels']}" for x in w.runs.values()}))],
            ["Per α: perturbation seeds × edge fraction; new-paper null R",
             ", ".join(sorted({f"{len(x.m['stability']['protocol']['seeds'])} × {x.m['stability']['protocol']['frac']}; "
                               f"{x.m['stability']['protocol']['R']}" for x in w.runs.values()}))],
            ["Per α: labeller / judge; retrieval beam, k",
             ", ".join(sorted({f"{x.cfg['labels']['labeller_model']} / {x.cfg['labels']['judge_model']}; "
                               f"{'/'.join(map(str, x.m['retrieval']['config']['beam']))}, {x.m['retrieval']['config']['k']}"
                               for x in w.runs.values()}))],
            ["Reference for paired comparisons", f"α = {w.ref:g} (the configured default)"],
            ["Significance level of all null tests", f"{ALPHA}"]]
    return md(["Setting", "Value"], rows)


def st_tree(w):
    rows = []
    for a in w.alphas:
        r, v = w.runs[a], w.v(a)
        lv = r.info["snapshots"][w.last]["levels"]
        rows.append([_a(a, w.ref), " / ".join(f(x) for x in v["tree_ari"][w.last]),
                     " / ".join(f"{x['linked'] / x['merges']:.0%}" if x["merges"] else "—" for x in lv),
                     f"{lv[0]['max_size']} ({lv[0]['cap']:.1f})", lv[-1]["singletons"]])
    return md(["α", f"ARI with the default tree at ≤{w.last}, L0 / L1 / L2", f"Merges sharing an edge at ≤{w.last}, L0 / L1 / L2",
               "Largest L0 super-node (cap)", "L2 singletons"], rows)


def st_coherence(w):
    rows = []
    for a in w.alphas:
        r = w.runs[a]
        lvs = r.m["coherence"]["snapshots"][w.last]["levels"]
        lifts = []
        for lv in lvs:
            iv = lv["exact"]["interval"]
            lifts.append(ci(iv["lift"], *iv["ci95"]) if iv["lift"] is not None else "—")
        n = sum(len(r.m["coherence"]["snapshots"][c]["levels"]) for c in r.cutoffs)
        rows.append([_a(a, w.ref), f"{len(_robust(r))} / {len(_robust(r, 'fuzzy'))} of {n}",
                     f"{len(_below_cells(r))} / {len(_below_cells(r, 'fuzzy'))}", *lifts])
    return md(["α", "Robust cells (exact / fuzzy)", "Cells below both nulls (exact / fuzzy)",
               f"Lift L0 ≤{w.last} [95% CI]", "Lift L1", "Lift L2"], rows)


VERDICT_SHORT = {"**robust**": "**robust**", "below both nulls": "below", "undefined": "—"}


def _short(v):
    if v in VERDICT_SHORT:
        return VERDICT_SHORT[v]
    if v.startswith("not evaluable"):
        return "n.e."
    if v.startswith("significant"):
        return "sig. " + v.split(", ")[1].split(" ")[0]
    return "n.s."


def st_coherence_grid(w):
    rows = []
    for c in w.cutoffs:
        for k in range(len(w.runs[w.ref].m["coherence"]["snapshots"][c]["levels"])):
            cells = []
            for a in w.alphas:
                snap = w.runs[a].m["coherence"]["snapshots"][c]
                cells.append(_short(_verdict(snap["levels"][k]["exact"], snap["coverage"]["exact"]["period_strata"])))
            rows.append([f"≤{c}", f"L{k}", *cells])
    return md(["Snapshot", "Level", *(f"α = {_a(a, w.ref)}" for a in w.alphas)], rows)


def st_stability(w):
    rows = []
    for a in w.alphas:
        r, v = w.runs[a], w.v(a)
        pt = r.m["stability"]["perturbation"]
        d = v["perturbation"][w.last]
        diff = "—" if a == w.ref else ci(d["mean"], d["lo"], d["hi"]) if d["lo"] is not None else f(d["mean"])
        above, idx = _above_null(r)
        nloc, loc = _localised(r)
        last_tr = list(v["cross_snapshot"])[-1]
        cx = v["cross_snapshot"][last_tr]
        rows.append([_a(a, w.ref), f(pt[w.cutoffs[0]]["hari"]["mean"]), ci(*_hari_last(r)), diff,
                     f"{above} of {len(idx)}", "—" if a == w.ref else ci(cx["mean"], *cx["ci95"]),
                     f"{nloc} of {len(loc)}", _range_pct([_untouched_share(x) for x in loc])])
    tr = list(w.v(w.ref)["cross_snapshot"])[-1].replace("-", "→")
    return md(["α", f"Perturbation HARI ≤{w.cutoffs[0]}", f"Perturbation HARI ≤{w.last} [t-interval]",
               f"Paired difference to default, ≤{w.last}", f"Cross-snapshot indices above the new-paper null (p ≤ {ALPHA})",
               f"Cross-snapshot HARI difference to default, {tr}", "Localised cells (ratio CI > 1)",
               "Untouched share of reassignment"], rows)


def st_faithfulness(w):
    rows = []
    for a in w.alphas:
        fa = w.runs[a].m["faithfulness"]
        lv = [ci(x["over_claim"]["value"], *x["over_claim"]["ci95"]) for x in fa["by_level"].values()]
        rows.append([_a(a, w.ref), fa["over_claim"]["n"], ci(*_overclaim(w.runs[a])), *lv, f(fa["claim_unsupported"]),
                     fa["deterministic"]["named_non_member"]])
    names = list(w.runs[w.ref].m["faithfulness"]["by_level"])
    return md(["α", "Labels judged", "Over-claim [95% CI]", *(f"Over-claim {n}" for n in names), "Claim-level unsupported",
               "Named non-member flags"], rows)


def st_retrieval(w):
    rows, ref = [], w.runs[w.ref].m["retrieval"]["summary"]
    for t, s in ref.items():
        for k, label in RETRIEVAL_NAMES.items():
            if k not in s:
                continue
            nd = 1 if k.startswith("steps") else 3
            flats = {w.runs[a].m["retrieval"]["summary"][t][k]["flat"] for a in w.alphas}
            assert len(flats) == 1, f"flat search differs across alpha for {t} {k}: {flats}"
            cells = []
            for a in w.alphas:
                x = w.runs[a].m["retrieval"]["summary"][t][k]
                fv = _favoured(k, x["hier_minus_flat"])
                cells.append(f"{f(x['hier'], nd)}" + (" ✓" if fv == "drill-down" else ""))
            rows.append([t, label, f(s[k]["flat"], nd), *cells])
    rows.append(["", "measures favouring drill-down / flat / tie", "",
                 *(" / ".join(str(_favour_counts(w.runs[a])[x]) for x in ("drill-down", "flat", "tie")) for a in w.alphas)])
    return md(["Type", "Metric", "Flat (every α)", *(f"Drill-down, α = {_a(a, w.ref)}" for a in w.alphas)], rows)


def _recommend(w):
    """Per α: headlines, eligibility and the recommendation (the rule of docs/alpha_sweep.md §6)."""
    h = {a: {"robust": len(_robust(r)), "hari": _hari_last(r), "oc": _overclaim(r),
             "fav": _favour_counts(r)["drill-down"]} for a, r in w.runs.items()}
    best_h = max(w.alphas, key=lambda a: h[a]["hari"][0])
    best_o = min(w.alphas, key=lambda a: h[a]["oc"][0])
    for a in w.alphas:
        why = []
        if None not in h[a]["hari"] and None not in h[best_h]["hari"] and h[a]["hari"][2] < h[best_h]["hari"][1]:
            why.append(f"HARI below α = {best_h:g}")
        if None not in h[a]["oc"] and None not in h[best_o]["oc"] and h[a]["oc"][1] > h[best_o]["oc"][2]:
            why.append(f"over-claim above α = {best_o:g}")
        h[a]["why"] = why
    eligible = [a for a in w.alphas if not h[a]["why"]]
    rec = max(eligible, key=lambda a: (h[a]["robust"], h[a]["hari"][0], -abs(a - w.ref))) if eligible else None
    return h, eligible, rec


def st_summary(w):
    h, eligible, rec = _recommend(w)
    rows = []
    for a in w.alphas:
        x = h[a]
        rows.append([_a(a, w.ref), x["robust"], ci(*x["hari"]), ci(*x["oc"]), x["fav"],
                     "yes" if a in eligible else "no: " + "; ".join(x["why"]), "**recommended**" if a == rec else ""])
    n_meas = sum(1 for s in w.runs[w.ref].m["retrieval"]["summary"].values() for k in RETRIEVAL_NAMES if k in s)
    tail = (f"\nRecommended: α = {rec:g}" + (" (the default)" if rec == w.ref else "") if rec is not None
            else "\nRecommended: none (no α is eligible)") + (
        f". Eligible: {', '.join(f'{a:g}' for a in eligible) or 'none'}; retrieval counts are out of {n_meas} measures"
        " (point estimates, no CIs).\n")
    return md(["α", "P3 robust cells (exact)", f"P5 perturbation HARI ≤{w.last} [t-interval]", "P6 over-claim [95% CI]",
               "T6 measures favouring drill-down", "Eligible (not distinguishably worse on HARI or over-claim)",
               "Recommendation"], rows) + tail


SWEEP_TABLES = {"sweep_setup": st_setup, "sweep_tree": st_tree, "sweep_coherence": st_coherence,
                "sweep_coherence_grid": st_coherence_grid, "sweep_stability": st_stability,
                "sweep_faithfulness": st_faithfulness, "sweep_retrieval": st_retrieval, "sweep_summary": st_summary}


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--run", default="out")
    ap.add_argument("--sweep", help="an alpha sweep directory (eval/sweep.py): render the sweep tables instead")
    ap.add_argument("--report", help="default: docs/report.md, or docs/alpha_sweep.md with --sweep")
    ap.add_argument("--check", action="store_true", help="exit 1 if the report's tables are not up to date")
    a = ap.parse_args(argv)
    tables = SWEEP_TABLES if a.sweep else TABLES
    r = Sweep(a.sweep) if a.sweep else Run(a.run)
    path = Path(a.report or ("docs/alpha_sweep.md" if a.sweep else "docs/report.md"))
    text = path.read_text()
    found = [m.group(2) for m in BLOCK.finditer(text)]
    stray = [l for l in BLOCK.sub("", text).splitlines() if l.lstrip().startswith("|")]
    if stray or len(found) != len(set(found)):
        sys.exit(f"{path}: tables outside generated blocks {stray[:3]} or duplicate blocks {sorted(found)}")
    unknown, missing = set(found) - set(tables), set(tables) - set(found)
    if unknown or missing:
        sys.exit(f"{path}: unknown table blocks {sorted(unknown)}, missing {sorted(missing)}")
    new = BLOCK.sub(lambda m: m.group(1) + tables[m.group(2)](r) + m.group(4), text)
    if a.check:
        if new != text:
            sys.exit(f"{path}: tables are out of date; run python make_tables.py")
        print(f"{path}: {len(found)} tables up to date")
        return
    path.write_text(new)
    print(f"{path}: {len(found)} tables regenerated from {a.sweep or a.run}/")


if __name__ == "__main__":
    main()
