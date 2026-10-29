"""Regenerate every table of docs/report.md from out/metrics.json (deliverable §6a.3).

    python make_tables.py [--run out] [--report docs/report.md] [--check]
    python make_tables.py --sweep [--run out] [--report docs/alpha_sweep.md] [--check]

Each table sits between `<!-- table:NAME -->` and `<!-- /table:NAME -->` in the report; the script rewrites the block
from the run's metrics.json and nothing else: the sections coherence, stability, faithfulness and retrieval, and the
alpha_sweep section written by `make sweep` (eval/sweep.py). Verdict columns are computed with the rules of
eval/verdicts.py from the p-values and intervals (ALPHA), never typed in; the recommendation and the trade-off verdicts
of the α sweep are computed here. With --sweep the script renders the α-sweep tables into docs/alpha_sweep.md.

Hand-written claims in the prose are tagged `<!-- claim:NAME -->` and checked against metrics.json by the predicates
of CLAIMS: a false claim, an unknown tag or an unused claim fails, on every run and with --check. --check exits 1 if
any block is out of date, unknown or missing. Nothing is recomputed: the script only reads metrics.json.
"""

from pathlib import Path
import argparse
import json
import re
import sys

from eval import verdicts as V
from eval.verdicts import ALPHA, LOWER_BETTER, RETRIEVAL_NAMES, SCHEMES

BLOCK = re.compile(r"(<!-- table:(\w+) -->\n)(.*?)(<!-- /table:\2 -->)", re.S)
CLAIM = re.compile(r"<!-- claim:(\w+) -->")


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
    """A run's metrics.json, the only input of every table."""

    def __init__(self, run):
        self.dir = Path(run)
        self.m = json.loads((self.dir / "metrics.json").read_text())
        self.cutoffs = V.cutoffs(self.m)
        self.last = self.cutoffs[-1]


# ---------------------------------------------------------------- run, parameters, design

def t_properties(r):
    rows = [["P1 laminarity, P2 budgets", "by construction (merge-only levels; budget lemma)", "`validate.py` on every run"],
            ["P4 hyper-edge fidelity", "by construction (score on the collapsed incidence; multi-way edges kept whole)", "§4"],
            ["No future information (structure, membership)", "by construction (snapshot-only edges, hubs, LSA, anchors)", "`validate.py` member cutoffs"],
            ["Structure–semantics trade-off (P3)", "empirical (α sweep; α chosen on these results)", "Tables 3–4, Fig. 1"],
            ["P3 semantic coherence", "empirical", "Tables 5–6, Fig. 2"],
            ["P5 temporal stability", "by construction (prior, persistent ids); size empirical", "Tables 7–9, Figs. 3–4"],
            ["P6 faithful labels", "empirical", "Table 10, Fig. 5"],
            ["T6 extrinsic utility", "empirical", "Table 11, Fig. 6"]]
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


# ---------------------------------------------------------------- verdict rules (eval/verdicts.py)

_ok, _passes, _untouched_share, _favoured = V.ok, V.passes, V.untouched_share, V.favoured


def _verdict(cell, strata):
    v = V.verdict(cell, strata)
    return "**robust**" if v == "robust" else v


def _robust(r, m="exact"):
    return V.robust(r.m, m)


def _below_cells(r, m="exact"):
    return V.below_cells(r.m, m)


def _above_null(r):
    return V.above_null(r.m)


def _localised(r):
    return V.localised(r.m)


def _favour_counts(r):
    return V.favour_counts(r.m)


# ---------------------------------------------------------------- coherence









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
    """Headline verdicts, computed with the same rules as Tables 6-11."""
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
        lv_row = ["P6 over-claim by level", "one level only", "", "Table 10"]
    else:
        a, b = lv[0]["over_claim"]["ci95"], lv[-1]["over_claim"]["ci95"]
        sep = "not evaluable" if not (_ok(a) and _ok(b)) else ("CIs do not overlap" if a[1] < b[0] or b[1] < a[0] else "CIs overlap")
        lv_row = [f"P6 {lv_names[0]} vs {lv_names[-1]} over-claim",
                  f"{f(lv[0]['over_claim']['value'])} vs {f(lv[-1]['over_claim']['value'])}", sep, "Table 10"]
    fav = _favour_counts(r)
    steps = [(t, s["steps_first"]) for t, s in r.m["retrieval"]["summary"].items() if "steps_first" in s]
    rows = [["P3 coherence beyond both nulls (robust: all schemes, exact filter)", ", ".join(rob) or "none",
             f"fuzzy filter: {', '.join(rob_f) or 'none'}", "Table 6"],
            ["P3 cells below both nulls in every scheme (exact filter)", ", ".join(below) or "none",
             f"fuzzy filter: {', '.join(below_f) or 'none'}", "Table 6"],
            ["P5 cross-snapshot indices above the new-paper null", f"{above} of {len(idx)}", f"p ≤ {ALPHA}, uncorrected", "Table 8"],
            ["P5 perturbation HARI, first → last snapshot", f"{f(pt[r.cutoffs[0]]['hari']['mean'])} → {f(pt[r.last]['hari']['mean'])}", "", "Table 7"],
            ["P5 localised level × transition cells (ratio CI > 1)", f"{nloc} of {len(loc)}",
             "untouched share of reassignment " + _range_pct([_untouched_share(x) for x in loc]), "Table 9"],
            ["P6 over-claim rate", ci(oc["value"], *oc["ci95"]), oc_q, "Table 10"],
            lv_row,
            ["T6 retrieval measures favouring drill-down / flat / tie", f"{fav['drill-down']} / {fav['flat']} / {fav['tie']}",
             "point estimates, no CIs", "Table 11"],
            ["T6 median steps to first item, drill-down vs flat", "; ".join(f"type {t}: {f(x['hier'], 1)} vs {f(x['flat'], 1)}" for t, x in steps) or "—", "", "Table 11"]]
    return md(["Finding", "Result", "Qualifier", "Source"], rows)


TABLES = {"findings": t_findings, "properties": t_properties, "literature": t_literature,
          "coherence_coverage": t_coherence_coverage, "coherence": t_coherence,
          "perturbation": t_perturbation, "cross_snapshot": t_cross, "localisation": t_localisation,
          "faithfulness": t_faithfulness, "retrieval": t_retrieval}


# ---------------------------------------------------------------- α sweep (metrics.json "alpha_sweep")

class Sweep:
    """The alpha_sweep section of the main run's metrics.json (eval/sweep.py), with the main run's α as the default."""

    def __init__(self, m):
        if "alpha_sweep" not in m:
            sys.exit("metrics.json has no alpha_sweep section: run `make sweep` (or `python -m eval sweep --summarise-only`)")
        self.s = m["alpha_sweep"]
        pr = self.s["protocol"]
        self.alphas, self.ref, self.fixed, self.budgets = pr["alphas"], pr["reference"], pr["fixed"], pr["budgets"]
        self.cutoffs = [str(c) for c in pr["cutoffs"]]
        self.last = self.cutoffs[-1]
        self.main = pr["main_run"]
        if self.main:   # the variant's metric sections against the main run's current ones (hashes in the section)
            self.main = {**self.main, "sections": len(self.main["section_sha256"]),
                         "sections_identical": [k for k, h in self.main["section_sha256"].items()
                                                if k in m and V.section_hash(m[k]) == h]}
        self.default = m["coherence"]["params"]["alpha"]   # the configured default: the α of the main run

    def v(self, a):
        return self.s["variants"][f"{a:g}"]

    def robust(self, a, flt="exact"):
        return self.v(a)["coherence"]["robust"][flt]

    def below(self, a, flt="exact"):
        return self.v(a)["coherence"]["below"][flt]

    def hari(self, a, c=None):
        h = self.v(a)["stability"]["perturbation_hari"][c or self.last]
        return h["mean"], h["lo"], h["hi"]

    def overclaim(self, a):
        oc = self.v(a)["faithfulness"]["over_claim"]
        return oc["value"], *oc["ci95"]

    def favour(self, a):
        return self.v(a)["retrieval"]["favour"]


def _a(a, w=None):
    """α with its role: the pre-sweep default (the reference of the paired comparisons) and the configured default."""
    tags = [] if w is None else ["pre-sweep default"] * (a == w.ref) + ["default"] * (a == w.default != w.ref)
    return f"{a:g}" + (f" ({', '.join(tags)})" if tags else "")


def _span_pct(r):
    return "—" if r is None else f"{r[0]:.0%}–{r[1]:.0%}"


def st_setup(w):
    fx = w.fixed
    per = lambda fn: ", ".join(sorted({fn(w.v(a)["protocol"]) for a in w.alphas}))
    rows = [["α (semantic weight; 0 = structure only, 1 = semantics only)", ", ".join(f"{a:g}" for a in w.alphas)],
            ["Fixed at the defaults: γ, ρ, edge weights, hub fraction h, LSA dimension",
             f"{fx['gamma']}, {fx['rho']}, {fx['edge_weight']}, {fx['hub_frac']}, {fx['lsa_dim']}"],
            ["Snapshots; budgets N_0, N_1, N_2", f"{', '.join(w.cutoffs)}; {', '.join(map(str, w.budgets))}"],
            ["Per α: coherence nulls (configuration rebuilds at that α, random labels)",
             per(lambda x: f"{x['coherence']['R']}, {x['coherence']['R_labels']}")],
            ["Per α: perturbation seeds × edge fraction; new-paper null R",
             per(lambda x: f"{len(x['stability']['seeds'])} × {x['stability']['frac']}; {x['stability']['R']}")],
            ["Per α: labeller / judge; retrieval beam, k",
             per(lambda x: f"{x['labels']['labeller_model']} / {x['labels']['judge_model']}; "
                           f"{'/'.join(map(str, x['retrieval']['beam']))}, {x['retrieval']['k']}")],
            ["Reference for paired comparisons", f"α = {w.ref:g} (the configured default before the sweep)"],
            ["Significance level of all null tests", f"{ALPHA}"]]
    if w.main:
        mr = w.main
        rows.append([f"Variant α = {mr['alpha']:g} (the configured default) against the main run",
                     f"hierarchy.json identical at {mr['hierarchy_identical']} of {mr['snapshots']} snapshots; metrics.json "
                     f"sections identical: {', '.join(mr['sections_identical']) or 'none'} of {mr['sections']}"])
    return md(["Setting", "Value"], rows)


def st_tree(w):
    rows = []
    for a in w.alphas:
        v = w.v(a)["tree"]
        lv = v["last"]
        rows.append([_a(a, w), " / ".join(f(x) for x in v["ari_vs_reference"][w.last]),
                     " / ".join(f"{x['linked'] / x['merges']:.0%}" if x["merges"] else "—" for x in lv),
                     f"{lv[0]['max_size']} ({lv[0]['cap']:.1f})", lv[-1]["singletons"]])
    return md(["α", f"ARI with the pre-sweep default tree at ≤{w.last}, L0 / L1 / L2", f"Merges sharing an edge at ≤{w.last}, L0 / L1 / L2",
               "Largest L0 super-node (cap)", "L2 singletons"], rows)


def st_coherence(w):
    rows = []
    for a in w.alphas:
        c = w.v(a)["coherence"]
        lifts = [ci(x["exact"]["lift"], *x["exact"]["ci95"]) if x["exact"]["lift"] is not None else "—" for x in c["cells"][w.last]]
        rows.append([_a(a, w), f"{len(w.robust(a))} / {len(w.robust(a, 'fuzzy'))} of {c['n_cells']}",
                     f"{len(w.below(a))} / {len(w.below(a, 'fuzzy'))}", *lifts])
    return md(["α", "Robust cells (exact / fuzzy)", "Cells below both nulls (exact / fuzzy)",
               f"Lift L0 ≤{w.last} [95% CI]", "Lift L1", "Lift L2"], rows)


VERDICT_SHORT = {"robust": "**robust**", "below both nulls": "below", "undefined": "—"}


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
        for k in range(len(w.v(w.ref)["coherence"]["cells"][c])):
            rows.append([f"≤{c}", f"L{k}", *(_short(w.v(a)["coherence"]["cells"][c][k]["exact"]["verdict"]) for a in w.alphas)])
    return md(["Snapshot", "Level", *(f"α = {_a(a, w)}" for a in w.alphas)], rows)


def st_stability(w):
    rows = []
    for a in w.alphas:
        v = w.v(a)
        d = v["paired"]["perturbation"][w.last]
        diff = "—" if a == w.ref else ci(d["mean"], d["lo"], d["hi"]) if d["lo"] is not None else f(d["mean"])
        cx = v["paired"]["cross_snapshot"][list(v["paired"]["cross_snapshot"])[-1]]
        st = v["stability"]
        rows.append([_a(a, w), f(w.hari(a, w.cutoffs[0])[0]), ci(*w.hari(a)), diff,
                     f"{st['above_null'][0]} of {st['above_null'][1]}", "—" if a == w.ref else ci(cx["mean"], *cx["ci95"]),
                     f"{st['localised'][0]} of {st['localised'][1]}", _span_pct(st["untouched_share"])])
    tr = list(w.v(w.ref)["paired"]["cross_snapshot"])[-1].replace("-", "→")
    return md(["α", f"Perturbation HARI ≤{w.cutoffs[0]}", f"Perturbation HARI ≤{w.last} [t-interval]",
               f"Paired difference to the pre-sweep default, ≤{w.last}", f"Cross-snapshot indices above the new-paper null (p ≤ {ALPHA})",
               f"Cross-snapshot HARI difference to the pre-sweep default, {tr}", "Localised cells (ratio CI > 1)",
               "Untouched share of reassignment"], rows)


def st_faithfulness(w):
    rows = []
    for a in w.alphas:
        fa = w.v(a)["faithfulness"]
        lv = [ci(x["value"], *x["ci95"]) for x in fa["by_level"].values()]
        rows.append([_a(a, w), fa["over_claim"]["n"], ci(*w.overclaim(a)), *lv, f(fa["claim_unsupported"]),
                     fa["named_non_member"]])
    names = list(w.v(w.ref)["faithfulness"]["by_level"])
    return md(["α", "Labels judged", "Over-claim [95% CI]", *(f"Over-claim {n}" for n in names), "Claim-level unsupported",
               "Named non-member flags"], rows)


def st_retrieval(w):
    rows, ref = [], w.v(w.ref)["retrieval"]["summary"]
    for t, s in ref.items():
        for k, label in RETRIEVAL_NAMES.items():
            if k not in s:
                continue
            nd = 1 if k.startswith("steps") else 3
            flats = {w.v(a)["retrieval"]["summary"][t][k]["flat"] for a in w.alphas}
            assert len(flats) == 1, f"flat search differs across alpha for {t} {k}: {flats}"
            cells = []
            for a in w.alphas:
                x = w.v(a)["retrieval"]["summary"][t][k]
                cells.append(f"{f(x['hier'], nd)}" + (" ✓" if _favoured(k, x["hier_minus_flat"]) == "drill-down" else ""))
            rows.append([t, label, f(s[k]["flat"], nd), *cells])
    rows.append(["", "measures favouring drill-down / flat / tie", "",
                 *(" / ".join(str(w.favour(a)[x]) for x in ("drill-down", "flat", "tie")) for a in w.alphas)])
    return md(["Type", "Metric", "Flat (every α)", *(f"Drill-down, α = {_a(a, w)}" for a in w.alphas)], rows)


def _recommend(w, guard="reference"):
    """Per α: headlines, eligibility and the recommendation (the rule of docs/alpha_sweep.md §8). guard "reference": the
    rule as applied, eligibility against the pre-sweep default; "best": the original rule, against the most robust and
    the most faithful variant (recorded in docs/alpha_sweep.md §9)."""
    h = {a: {"robust": len(w.robust(a)), "hari": w.hari(a), "oc": w.overclaim(a), "fav": w.favour(a)["drill-down"]}
         for a in w.alphas}
    ref_o = h[w.ref]["oc"]
    best_h = max(w.alphas, key=lambda a: h[a]["hari"][0])
    best_o = min(w.alphas, key=lambda a: h[a]["oc"][0])
    for a in w.alphas:
        why = []
        if guard == "reference":
            d = w.v(a)["paired"]["perturbation"][w.last]
            if a != w.ref and d["hi"] is not None and d["hi"] < 0:
                why.append("HARI below the pre-sweep default (paired)")
            if a != w.ref and None not in h[a]["oc"] and None not in ref_o and h[a]["oc"][1] > ref_o[2]:
                why.append("over-claim above the pre-sweep default")
        else:
            if h[a]["hari"][2] < h[best_h]["hari"][1]:
                why.append(f"HARI below α = {best_h:g}")
            if h[a]["oc"][1] > h[best_o]["oc"][2]:
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
        rows.append([_a(a, w), x["robust"], ci(*x["hari"]), ci(*x["oc"]), x["fav"],
                     "yes" if a in eligible else "no: " + "; ".join(x["why"]), "**recommended**" if a == rec else ""])
    n_meas = sum(w.favour(w.ref).values())
    tail = (f"\nRecommended: α = {rec:g}" + (" (the pre-sweep default)" if rec == w.ref else "") if rec is not None
            else "\nRecommended: none (no α is eligible)") + (
        f". Eligible: {', '.join(f'{a:g}' for a in eligible) or 'none'}; retrieval counts are out of {n_meas} measures"
        " (point estimates, no CIs).\n")
    return md(["α", "P3 robust cells (exact)", f"P5 perturbation HARI ≤{w.last} [t-interval]", "P6 over-claim [95% CI]",
               "T6 measures favouring drill-down", "Eligible (not distinguishably worse than the pre-sweep default on HARI or over-claim)",
               "Recommendation"], rows) + tail


def t_alpha_sweep(r):
    """Report table: the α variants across the four criteria, the recommended α in bold."""
    w = Sweep(r.m)
    h, eligible, rec = _recommend(w)
    rows = []
    for a in w.alphas:
        x, d, fav = h[a], w.v(a)["paired"]["perturbation"][w.last], w.favour(a)
        row = [_a(a, w), f"{x['robust']} / {len(w.below(a))}", ci(*x["hari"]),
               "—" if a == w.ref else ci(d["mean"], d["lo"], d["hi"]), ci(*x["oc"]),
               f"{fav['drill-down']} / {fav['flat']} / {fav['tie']}",
               "yes" if a in eligible else "no: " + "; ".join(x["why"]), "recommended" if a == rec else ""]
        rows.append([f"**{c}**" if a == rec and c != "" else c for c in row])
    n_cells, n_meas = w.v(w.ref)["coherence"]["n_cells"], sum(w.favour(w.ref).values())
    tail = (f"\nRecommended: α = {rec:g}" + (" (the pre-sweep default)" if rec == w.ref else "") if rec is not None
            else "\nRecommended: none (no α is eligible)") + (
        f". Coherence cells are out of {n_cells} (snapshot × level), retrieval measures out of {n_meas}.\n")
    return md(["α", "P3 robust / below-null cells (exact)", f"P5 perturbation HARI ≤{w.last} [t-interval]",
               "P5 paired difference to the pre-sweep default", "P6 over-claim [95% CI]",
               "T6 measures favouring drill-down / flat / tie", "Eligible", "Recommendation"], rows) + tail


TABLES["alpha_sweep"] = t_alpha_sweep


def _paired_excl(w, a):
    """Every paired HARI difference of α to the reference (perturbation per snapshot, cross-snapshot per transition)
    whose interval excludes 0: (below, above, number of intervals)."""
    v = w.v(a)["paired"]
    ds = [(f"≤{c} (perturbation)", d["lo"], d["hi"]) for c, d in v["perturbation"].items()]
    ds += [(f"{tr.replace('-', '→')} (cross-snapshot)", *d["ci95"]) for tr, d in v["cross_snapshot"].items()]
    ds = [x for x in ds if x[1] is not None and x[2] is not None]
    return [n for n, lo, hi in ds if hi < 0], [n for n, lo, hi in ds if lo > 0], len(ds)


def _paired_rows(w, rec):
    below, above, n = _paired_excl(w, rec)
    verdict = "; ".join(s for s in (f"worse at {', '.join(below)}" if below else "",
                                    f"better at {', '.join(above)}" if above else "") if s) or "no distinguishable difference"
    return ["P5 paired HARI differences, every snapshot and transition", f"{len(below)} below 0, {len(above)} above 0",
            "—", f"of {n} paired intervals", "—", verdict]


def _retrieval_delta(w, a):
    """Drill-down measures of α against those of the reference (point estimates): (better, same count, worse)."""
    s, b = w.v(a)["retrieval"]["summary"], w.v(w.ref)["retrieval"]["summary"]
    better, worse, same = [], [], 0
    for typ in s:
        for k, name in RETRIEVAL_NAMES.items():
            if k in s[typ] and k in b[typ] and None not in (s[typ][k]["hier"], b[typ][k]["hier"]):
                d = s[typ][k]["hier"] - b[typ][k]["hier"]
                d = -d if k in LOWER_BETTER else d
                if d == 0:
                    same += 1
                else:
                    (better if d > 0 else worse).append(f"{typ} {name}")
    return better, same, worse


def _retrieval_change(w, rec):
    better, same, worse = _retrieval_delta(w, rec)
    return ["T6 drill-down measures against the pre-sweep default (point estimates)",
            f"{len(better)} better / {same} same / {len(worse)} worse", "—", "—", "—",
            f"worse: {'; '.join(worse) or 'none'}. Better: {'; '.join(better) or 'none'}"]


def t_alpha_tradeoffs(r):
    """Report table: per headline, the recommended α against the pre-sweep default and the best variant on that headline."""
    w = Sweep(r.m)
    h, _, rec = _recommend(w)
    ref = w.ref

    def best(vals, low=False):
        b = (min if low else max)(vals.values())
        return ", ".join(f"α = {_a(a, w)}" for a, v in vals.items() if v == b) + f": {b if isinstance(b, int) else f(b)}"

    def count(name, fn, low=False):
        vals = {a: fn(a) for a in w.alphas}
        d = vals[rec] - vals[ref]
        better = (d < 0) if low else (d > 0)
        verdict = "same count" if d == 0 else ("better" if better else "worse") + " (count, no interval)"
        return [name, vals[rec], vals[ref], f"{d:+d}" if d else "0", best(vals, low), verdict]

    pd = w.v(rec)["paired"]["perturbation"][w.last]
    hv = "not computed" if rec == ref else (
        "no distinguishable difference (paired interval contains 0)" if pd["lo"] <= 0 <= pd["hi"]
        else "better (paired interval above 0)" if pd["lo"] > 0 else "worse (paired interval below 0)")
    oR, oD = h[rec]["oc"], h[ref]["oc"]
    ov = ("no distinguishable difference (intervals overlap)" if oR[1] <= oD[2] and oD[1] <= oR[2]
          else "better (interval below)" if oR[2] < oD[1] else "worse (interval above)")
    rows = [count("P3 robust coherence cells (exact)", lambda a: len(w.robust(a))),
            count("P3 cells below both nulls (exact)", lambda a: len(w.below(a)), low=True),
            [f"P5 perturbation HARI ≤{w.last}", ci(*h[rec]["hari"]), ci(*h[ref]["hari"]),
             "—" if rec == ref else ci(pd["mean"], pd["lo"], pd["hi"]) + " (paired by seed)",
             best({a: h[a]["hari"][0] for a in w.alphas}), hv],
            _paired_rows(w, rec),
            count("P5 cross-snapshot indices above the new-paper null", lambda a: w.v(a)["stability"]["above_null"][0]),
            count("P5 localised level × transition cells", lambda a: w.v(a)["stability"]["localised"][0]),
            ["P6 over-claim rate", ci(*oR), ci(*oD), f"{oR[0] - oD[0]:+.3f} (unpaired)",
             best({a: h[a]["oc"][0] for a in w.alphas}, low=True), ov],
            count("T6 retrieval measures favouring drill-down", lambda a: w.favour(a)["drill-down"]),
            _retrieval_change(w, rec)]
    return md(["Headline", f"Recommended, α = {_a(rec, w)}", f"Pre-sweep default, α = {ref:g}", "Difference",
               "Best variant on this headline", "Recommended against the pre-sweep default"], rows)


TABLES["alpha_tradeoffs"] = t_alpha_tradeoffs

SWEEP_TABLES = {"sweep_setup": st_setup, "sweep_tree": st_tree, "sweep_coherence": st_coherence,
                "sweep_coherence_grid": st_coherence_grid, "sweep_stability": st_stability,
                "sweep_faithfulness": st_faithfulness, "sweep_retrieval": st_retrieval, "sweep_summary": st_summary}


# ---------------------------------------------------------------- verified claims of the prose

def _claims():
    """NAME -> (the document it is tagged in, what the tagged sentence states, predicate over the main run's metrics.json)."""
    def sw(fn):
        return lambda m: fn(Sweep(m))

    def rec(w):
        return _recommend(w)[2]

    def others(w, a):
        return [b for b in w.alphas if b != a]

    def most_robust(w):
        r = rec(w)
        return all(len(w.robust(r)) > len(w.robust(b)) for b in others(w, r)) and not w.below(r)

    def last_indistinct(w):
        r, d = rec(w), w.v(rec(w))["paired"]["perturbation"][w.last]
        oR, oD = w.overclaim(r), w.overclaim(w.ref)
        return d["lo"] <= 0 <= d["hi"] and oR[1] <= oD[2] and oD[1] <= oR[2]

    def stability_loss(w):
        below, above, _ = _paired_excl(w, rec(w))
        return ([x for x in below if "perturbation" in x] == [f"≤{w.cutoffs[0]} (perturbation)"]
                and sum("cross-snapshot" in x for x in below) == 1 and len(above) == 1 and "cross-snapshot" in above[0])

    def names_most_robust(w):
        h = {a: w.hari(a) for a in w.alphas}
        top = max(w.alphas, key=lambda a: h[a][0])
        return top == 1.0 and not w.robust(1.0) and all(h[1.0][1] > h[b][2] for b in others(w, 1.0))

    def faith_tradeoff(w):
        r = rec(w)
        low = min(w.alphas, key=lambda a: w.overclaim(a)[0])
        return low != r and w.overclaim(r)[0] >= w.overclaim(w.ref)[0]

    def retrieval_mixed(w):
        r = rec(w)
        better, _, worse = _retrieval_delta(w, r)
        slow = all(x["steps_first"]["hier"] > x["steps_first"]["flat"] for x in w.v(r)["retrieval"]["summary"].values()
                   if "steps_first" in x)
        return (w.favour(r)["drill-down"] == w.favour(w.ref)["drill-down"] and better and worse
                and "A reach" in worse and slow)

    def paired_ref(w):
        st = [w.v(a)["protocol"]["stability"] for a in w.alphas]
        n = len(st[0]["seeds"])
        return (w.ref == 0.5 and all(x == st[0] for x in st)
                and all(d["n"] == n for a in w.alphas for d in w.v(a)["paired"]["perturbation"].values()))

    def main_identical(w):
        mr = w.main
        return (mr is not None and mr["alpha"] == w.default and mr["hierarchy_identical"] == mr["snapshots"]
                and len(mr["sections_identical"]) == mr["sections"])

    def original_rule(w):
        o = _recommend(w, guard="best")[2]
        best_h = max(w.alphas, key=lambda a: w.hari(a)[0])
        h = {a: w.hari(a) for a in w.alphas}
        return (o == 1.0 == best_h and not w.robust(1.0) and _recommend(w, guard="best")[1] == [1.0]
                and all(h[1.0][1] > h[b][2] for b in others(w, 1.0)))

    return {
        "sweep_grid": ("report", "the five α values 0, 0.25, 0.5, 0.75 and 1", sw(lambda w: w.alphas == [0.0, 0.25, 0.5, 0.75, 1.0])),
        "reference": ("report", "the reference is α = 0.5, and the stability comparisons with it are paired by seed "
                      "(same seeds, edge fraction and subsamples for every variant)", sw(paired_ref)),
        "recommended": ("report", "the rule recommends α = 0.75, which is the configured default of the main run",
                        sw(lambda w: rec(w) == 0.75 == w.default)),
        "most_robust": ("report", "the recommended α has more robust cells than every other variant and no below-null cell", sw(most_robust)),
        "last_indistinct": ("report", "at the last snapshot its paired HARI interval contains 0 and its over-claim CI overlaps the reference's",
                            sw(last_indistinct)),
        "stability_loss": ("report", "its paired HARI differences lie below 0 exactly at the first snapshot (perturbation) and one "
                           "transition (cross-snapshot), and above 0 at one transition", sw(stability_loss)),
        "names_most_robust": ("report", "α = 1 has the highest perturbation HARI, an interval above every other variant's, and no "
                              "robust cell", sw(names_most_robust)),
        "faith_tradeoff": ("report", "another variant has the lowest over-claim, and the recommended α's over-claim is not below the "
                           "reference's", sw(faith_tradeoff)),
        "retrieval_mixed": ("report", "same drill-down favour count as the reference; measures better and worse, type-A reach worse; "
                            "drill-down slower to the first item than flat for every type", sw(retrieval_mixed)),
        "main_run_identical": ("report", "the main run is identical to the sweep variant at the configured default (hierarchies "
                               "and all four metric sections)", sw(main_identical)),
        "sweep_grid_doc": ("sweep", "the five α values 0, 0.25, 0.5, 0.75 and 1",
                           sw(lambda w: w.alphas == [0.0, 0.25, 0.5, 0.75, 1.0])),
        "reference_doc": ("sweep", "the pre-sweep default and reference is α = 0.5, paired as in the report",
                          sw(paired_ref)),
        "original_rule": ("sweep", "the original best-variant guard would have recommended α = 1 alone, the most robust variant, "
                          "which has no robust cell", sw(original_rule)),
    }


CLAIMS = _claims()


def check_claims(text, m, path, doc):
    """Every claim tagged in the document holds on metrics.json, and every claim registered for it is tagged."""
    found = set(CLAIM.findall(text))
    unknown = sorted(n for n in found if n not in CLAIMS or CLAIMS[n][0] != doc)
    unused = sorted(n for n, (d, _, _) in CLAIMS.items() if d == doc and n not in found)
    false = sorted(n for n in found if n in CLAIMS and not CLAIMS[n][2](m))
    if unknown or unused or false:
        sys.exit(f"{path}: unknown claim tags or tags of the other document {unknown}; registered but untagged {unused}; claims that do not hold on "
                 "metrics.json: " + ("; ".join(f"{n} ({CLAIMS[n][1]})" for n in false) or "none"))
    return found


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--run", default="out")
    ap.add_argument("--sweep", action="store_true", help="render the α-sweep tables (docs/alpha_sweep.md) instead")
    ap.add_argument("--report", help="default: docs/report.md, or docs/alpha_sweep.md with --sweep")
    ap.add_argument("--check", action="store_true", help="exit 1 if the report's tables are not up to date")
    a = ap.parse_args(argv)
    tables = SWEEP_TABLES if a.sweep else TABLES
    run = Run(a.run)
    r = Sweep(run.m) if a.sweep else run
    path = Path(a.report or ("docs/alpha_sweep.md" if a.sweep else "docs/report.md"))
    text = path.read_text()
    found = [m.group(2) for m in BLOCK.finditer(text)]
    stray = [l for l in BLOCK.sub("", text).splitlines() if l.lstrip().startswith("|")]
    if stray or len(found) != len(set(found)):
        sys.exit(f"{path}: tables outside generated blocks {stray[:3]} or duplicate blocks {sorted(found)}")
    unknown, missing = set(found) - set(tables), set(tables) - set(found)
    if unknown or missing:
        sys.exit(f"{path}: unknown table blocks {sorted(unknown)}, missing {sorted(missing)}")
    claims = check_claims(text, run.m, path, "sweep" if a.sweep else "report")
    new = BLOCK.sub(lambda m: m.group(1) + tables[m.group(2)](r) + m.group(4), text)
    if a.check:
        if new != text:
            sys.exit(f"{path}: tables are out of date; run python make_tables.py")
        print(f"{path}: {len(found)} tables up to date; {len(claims)} claims hold")
        return
    path.write_text(new)
    print(f"{path}: {len(found)} tables regenerated from {a.run}/metrics.json; {len(claims)} claims hold")


if __name__ == "__main__":
    main()
