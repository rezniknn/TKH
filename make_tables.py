"""Regenerate every table of the report and its appendices from out/metrics.json (deliverable §6a.3).

    python make_tables.py [--doc report|appendix|sweep] [--run out] [--report PATH] [--check]

    report    docs/report.md        the main report (TABLES)
    appendix  docs/appendix.md      Appendix A: full per-metric tables of the shipped run (APPENDIX_TABLES)
    sweep     docs/alpha_sweep.md   Appendix B: the α sweep (SWEEP_TABLES); --sweep is an alias of --doc sweep

Each table sits between `<!-- table:NAME -->` and `<!-- /table:NAME -->` in its document; the script rewrites the
block from the run's metrics.json and nothing else: the sections coherence, stability, faithfulness and retrieval, the
alpha_sweep section written by `make sweep` (eval/sweep.py) and the abstract_coherence section written by
`make abstract-coherence` (eval/extra/abstract_coherence.py). Verdict columns are computed with the rules of
eval/verdicts.py from the p-values and intervals (ALPHA), never typed in; the recommendation and the trade-off verdicts
of the α sweep are computed here.

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
from eval.verdicts import ALPHA, LOWER_BETTER, RETRIEVAL_COST, RETRIEVAL_NAMES

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
    rows = [["P1 laminarity, P2 budgets", "construction (merge-only; a feasible merge for ρ ≥ 2)", "`validate.py`"],
            ["P4 hyper-edge fidelity", "construction (collapsed incidence, multi-way edges whole)", "§4"],
            ["No future information", "construction (snapshot-only edges, hubs, LSA, anchors); aliases assumed", "`validate.py`"],
            ["P5 identity and lineage", "construction (overlap matching; one fate per super-node)", "`validate.py`"],
            ["P5 temporal stability", "empirical (soft prior; no bound on reassignment)", "Tables 3, A3–A5"],
            ["P3 coherence, trade-off", "empirical (α chosen on these results)", "Tables 2–3, A1–A2"],
            ["P6 labels, T6 utility", "empirical", "Tables 3, A6–A7"]]
    return md(["Property", "Status", "Evidence"], rows)


def t_literature(r):
    rows = [["h-Louvain [1]", "hyper-edge-aware affinity; multilevel aggregation",
             "no modularity optimum setting the counts; exact nested budgets; a semantic term"],
            ["Featured Graph Coarsening [2]", "joint topology–feature coarsening",
             "on the hyper-edge incidence; greedy merges; no similarity guarantee claimed"],
            ["DynHAC [3]", "average linkage; change confined to affected regions",
             "a soft prior, not recomputation (frozen regions would hold budget slots); H is not reducible"],
            ["HyperEF 2.0 [4]", "hyper-edge contraction with explicit coarse edges",
             "fixed counts, no spectral target; multi-way edges scored by the connectivity cut"]]
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
        rows.append([tr.replace("-", "→"), x["common_nodes"],
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
    dc, sens = fa["decomposition"], fa["sensitivity"]
    tail = (f"\nLabels {fa['labels']}, judged {fa['judged']} (no held-out evidence: {fa['no_held_out']}); decomposition "
            f"passes its content check for {fa['decomposition_ok']:.0%} (every claim kept {dc['all_kept']}, some claims "
            f"failing {dc['partial']}, none returned or kept {dc['none_kept']}; a failed decomposition is judged as label "
            f"and gloss); sensitivity, failing claims dropped and the survivors judged: over-claim "
            f"{ci(sens['over_claim']['value'], *sens['over_claim']['ci95'])}; cited-line rejections {fa['quote_rejected']}; "
            f"deterministic flags: year after cutoff {d['year_after_cutoff']}, named non-member {d['named_non_member']}, "
            f"future entity {d['future_entity']}.\n")
    return md(["Group", "Labels judged", "Over-claim rate [95% CI]", "Claim-level unsupported"], rows) + tail


def _nd(k):
    return 1 if k in LOWER_BETTER - {"error_rate"} else 3


def t_retrieval(r):
    names = {**RETRIEVAL_NAMES, **RETRIEVAL_COST}
    rows = []
    for t, s in r.m["retrieval"]["summary"].items():
        unknown = {k for k, v in s.items() if isinstance(v, dict) and "stat" in v} - names.keys()
        assert not unknown, f"retrieval metrics without a label: {unknown}"
        for k, label in names.items():
            if k not in s:
                continue
            v, nd = s[k], _nd(k)
            d = v["hier_minus_flat"]
            c, e = s["ceilings"].get(k), v.get("end_to_end")
            rows.append([t, label, v["n"], f"{c['attainable']}/{c['total']}" if c else "—", f(v["hier"], nd), f(v["flat"], nd),
                         "—" if d is None else f"{d:+.{nd}f}", f"{f(e['hier'], 3)} / {f(e['flat'], 3)} (n = {e['n']})" if e else "—",
                         "not counted" if k in RETRIEVAL_COST else _favoured(k, d) or "—"])
    dg = r.m["retrieval"]["diagnostics"]
    tail = ("\nDrill-down diagnostics: kept/frontier " + ", ".join(f"{lv} {x['mean']:.2f}" for lv, x in dg["kept_over_frontier"].items())
            + f"; per question, super-nodes scored {dg['supernodes_scored']['min']}–{dg['supernodes_scored']['max']}, of them labelled "
            + f"(shown to the reader) {dg['labels_shown']['min']}–{dg['labels_shown']['max']}; pool leaves {dg['pool']['min']}–{dg['pool']['max']}; "
            + "never reached: " + (", ".join(f"{q} (lost at L{lv})" for q, lv in dg["never_reached"].items()) or "none") + ".\n")
    return md(["Type", "Metric", "n", "Attainable / total items", "Drill-down", "Flat",
               "Paired difference (mean; medians: inspection, computation)", "End to end, drill-down / flat",
               "Favoured (point estimate)"], rows) + tail


def _hari(x):
    return ci(x["hari"]["mean"], x["hari"]["lo"], x["hari"]["hi"])


def _cells(cs):
    """['≤2024 L0', '≤2024 L1', ...] -> '≤2024 L0–L2; ≤2026 L1' (levels grouped per snapshot)."""
    by = {}
    for c in cs:
        t, lv = c.split(" ")
        by.setdefault(t, []).append(int(lv[1:]))
    out = []
    for t, lvs in by.items():
        run = sorted(lvs)
        out.append(f"{t} L{run[0]}–L{run[-1]}" if len(run) > 1 and run == list(range(run[0], run[-1] + 1)) else
                   t + " " + ", ".join(f"L{x}" for x in run))
    return "; ".join(out) or "none"


def t_results(r):
    """Headline results of the shipped run with their uncertainty, computed with the rules of Tables A2-A7."""
    rob, rob_f = _robust(r), _robust(r, "fuzzy")
    below, below_f = _below_cells(r), _below_cells(r, "fuzzy")
    above, idx = _above_null(r)
    pt = r.m["stability"]["perturbation"]
    nloc, loc = _localised(r)
    fa = r.m["faithfulness"]
    oc, lv = fa["over_claim"], list(fa["by_level"].items())
    n_cells = sum(len(r.m["coherence"]["snapshots"][c]["levels"]) for c in r.cutoffs)
    fav, ret = _favour_counts(r), r.m["retrieval"]["summary"]
    ra = ret["A"]
    lifts = [(c, k, lv["exact"]["interval"]) for c in [r.last] for k, lv in enumerate(r.m["coherence"]["snapshots"][c]["levels"])]
    seeds = len(r.m["stability"]["protocol"]["seeds"])
    rows = [["P3 robust cells (exact; fuzzy)", f"{len(rob)} of {n_cells}: {_cells(rob)}",
             f"fuzzy {len(rob_f)}; below both nulls: {len(below)} (fuzzy {len(below_f)})", "A2"],
            [f"P3 lift ≤{r.last}, " + ", ".join(f"L{k}" for _, k, _ in lifts), "; ".join(ci(x["lift"], *x["ci95"]) for _, _, x in lifts),
             "paper-bootstrap CI; 1 = chance", "A2"],
            ["P5 perturbation HARI, first → last", f"{_hari(pt[r.cutoffs[0]])} → {_hari(pt[r.last])}", f"t-interval, {seeds} seeds", "A3"],
            ["P5 cross-snapshot; localisation", f"{above} of {len(idx)} above the null; {nloc} of {len(loc)} localised",
             "untouched share " + _range_pct([_untouched_share(x) for x in loc]), "A4–A5"],
            ["P6 over-claim (all; " + " vs ".join(n for n, _ in lv) + ")",
             f"{ci(oc['value'], *oc['ci95'])}; " + " vs ".join(f(x["over_claim"]["value"]) for _, x in lv), "bootstrap CI", "A6"],
            ["T6 type-A methods; reach (drill-down vs flat)",
             f"{f(ra['methods']['hier'], 3)} vs {f(ra['methods']['flat'], 3)}; {f(ra['reached']['hier'], 3)} vs {f(ra['reached']['flat'], 3)}",
             "point estimates; favour count " + f"{fav['drill-down']}/{fav['flat']}/{fav['tie']}", "A7"],
            ["T6 items inspected to first; candidates scored",
             "; ".join(f"{t}: {f(x['inspect_first']['hier'], 1)} vs {f(x['inspect_first']['flat'], 1)}, {f(x['scored']['hier'], 0)} vs {f(x['scored']['flat'], 0)}"
                       for t, x in ret.items()), "medians; computation, not latency", "A7"]]
    return md(["Criterion", f"α = {r.m['coherence']['params']['alpha']:g}", "Qualifier", "Table"], rows)


def t_abstract_coherence(r):
    """§5.5 (extra, outside the assignment): LLM-rated closeness of paper abstracts within vs across L0 super-nodes (metrics.json "abstract_coherence")."""
    if "abstract_coherence" not in r.m:
        sys.exit("metrics.json has no abstract_coherence section: run `make abstract-coherence`")
    x = r.m["abstract_coherence"]
    cov, sm, pm, lo = x["coverage"], x["summary"], x["summary"]["permutation"], x["leave_one_out"]
    rows = [["Papers with an abstract; L0 super-nodes holding them",
             f"{cov['with_abstract']} of {cov['papers']}; {cov['super_nodes_with_papers']} of {cov['super_nodes_l0']}"],
            ["Pairs rated, same / different L0 super-node", f"{sm['pairs_within']} / {sm['pairs_across']}"],
            ["Mean closeness (0–10), same / different", f"{f(sm['mean_within'])} / {f(sm['mean_across'])}"],
            ["Difference [95% paper-bootstrap CI]", ci(sm["difference"], *sm["difference_ci95"])],
            [f"Permutation null (R = {pm['R']}): mean; 97.5% q.; p", f"{f(pm['null_mean'])}; {f(pm['null_q97.5'])}; {p(pm['p'])}"],
            [f"Difference, one of {lo['n']} super-nodes with ≥ 2 papers left out: min; max",
             f"{f(lo['min']['difference'])} (without {lo['min']['dropped']}); {f(lo['max']['difference'])} (without {lo['max']['dropped']})"]]
    pr = x["protocol"]
    return md(["Item", f"Value ({pr['model']}, ≤{pr['cutoff']}, L{pr['level']}, α = {pr['alpha']:g})"], rows)


TABLES = {"results": t_results, "properties": t_properties, "abstract_coherence": t_abstract_coherence}
APPENDIX_TABLES = {"literature": t_literature, "coherence_coverage": t_coherence_coverage, "coherence": t_coherence,
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
        so = fa["over_claim_survivors_only"]
        rows.append([_a(a, w), fa["over_claim"]["n"], ci(*w.overclaim(a)), *lv, f(fa["claim_unsupported"]),
                     ci(so["value"], *so["ci95"]), fa["named_non_member"]])
    names = list(w.v(w.ref)["faithfulness"]["by_level"])
    return md(["α", "Labels judged", "Over-claim [95% CI]", *(f"Over-claim {n}" for n in names), "Claim-level unsupported",
               "Over-claim, survivor rule (sensitivity)", "Named non-member flags"], rows)


def st_retrieval(w):
    rows, ref = [], w.v(w.ref)["retrieval"]["summary"]
    for t, s in ref.items():
        for k, label in {**RETRIEVAL_NAMES, **RETRIEVAL_COST}.items():
            if k not in s:
                continue
            nd = _nd(k)
            flats = {w.v(a)["retrieval"]["summary"][t][k]["flat"] for a in w.alphas}
            assert len(flats) == 1, f"flat search differs across alpha for {t} {k}: {flats}"
            cells = []
            for a in w.alphas:
                x = w.v(a)["retrieval"]["summary"][t][k]
                cells.append(f"{f(x['hier'], nd)}" + (" ✓" if k in RETRIEVAL_NAMES and _favoured(k, x["hier_minus_flat"]) == "drill-down" else ""))
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
               f"{fav['drill-down']} / {fav['flat']} / {fav['tie']}"]
        rows.append([f"**{c}**" if a == rec and c != "" else c for c in row])
    n_cells, n_meas = w.v(w.ref)["coherence"]["n_cells"], sum(w.favour(w.ref).values())
    tail = f"\nCoherence cells are out of {n_cells} (snapshot × level), retrieval measures out of {n_meas}.\n"
    return md(["α", "P3 robust / below-null cells (exact)", f"P5 perturbation HARI ≤{w.last} [t-interval]",
               f"P5 paired difference ≤{w.last} to the pre-sweep default", "P6 over-claim [95% CI]",
               "T6 measures favouring drill-down / flat / tie"], rows) + tail


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


def st_tradeoffs(w):
    """Per headline, the recommended α against the pre-sweep default and the best variant on that headline."""
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
            count("T6 retrieval measures favouring drill-down (descriptive count, not votes)", lambda a: w.favour(a)["drill-down"]),
            _retrieval_change(w, rec)]
    return md(["Headline", f"Recommended, α = {_a(rec, w)}", f"Pre-sweep default, α = {ref:g}", "Difference",
               "Best variant on this headline", "Recommended against the pre-sweep default"], rows)


SWEEP_TABLES = {"sweep_setup": st_setup, "sweep_tree": st_tree, "sweep_coherence": st_coherence,
                "sweep_coherence_grid": st_coherence_grid, "sweep_stability": st_stability,
                "sweep_faithfulness": st_faithfulness, "sweep_retrieval": st_retrieval, "sweep_summary": st_summary,
                "sweep_tradeoffs": st_tradeoffs}
DOCS = {"report": ("docs/report.md", TABLES, False), "appendix": ("docs/appendix.md", APPENDIX_TABLES, False),
        "sweep": ("docs/alpha_sweep.md", SWEEP_TABLES, True)}   # path, tables, whether tables take the Sweep view


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
        oR, oD = w.overclaim(r), w.overclaim(w.ref)
        return all(oR[0] >= w.overclaim(a)[0] for a in w.alphas) and oR[1] <= oD[2] and oD[1] <= oR[2]

    def retrieval_mixed(w):
        r = rec(w)
        better, _, worse = _retrieval_delta(w, r)
        s = w.v(r)["retrieval"]["summary"].values()
        cheaper = all(x["scored"]["hier"] < x["scored"]["flat"] for x in s)
        more_reading = all(x["inspect_first"]["hier"] > x["inspect_first"]["flat"] for x in s)
        return (w.favour(r)["drill-down"] == w.favour(w.ref)["drill-down"] and better and worse
                and "A reach" in worse and cheaper and more_reading)

    def navigation_not_established(w):
        s = w.v(w.default)["retrieval"]["summary"]
        a = s["A"]
        return (a["methods"]["hier"] <= a["methods"]["flat"] and a["reached"]["hier"] < a["reached"]["flat"]
                and all(x["scored"]["hier"] < x["scored"]["flat"] and x["inspect_first"]["hier"] > x["inspect_first"]["flat"]
                        for x in s.values()))

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

    def lift_ci_chance(m):
        cells = [lv["exact"]["interval"] for c in V.cutoffs(m) for lv in m["coherence"]["snapshots"][c]["levels"]]
        return all(x["ci95"][0] < 1 < x["ci95"][1] for x in cells if x["ci95"] and None not in x["ci95"])

    def protocol_counts(m):
        s, st = m["retrieval"]["summary"], m["stability"]["protocol"]
        return (len(m["retrieval"]["per_question"]) == 18 and s["A"]["n_questions"] == 14 and s["B"]["n_questions"] == 4
                and st["frac"] == 0.1 and len(st["seeds"]) == 5)

    def coherence_late(m):
        late = {f"≤{c} L{k}" for c in V.cutoffs(m)[-2:] for k in range(len(m["coherence"]["snapshots"][c]["levels"]))}
        return late <= set(V.robust(m, "exact")) and not V.below_cells(m, "exact")

    def coverage_grows(m):
        cov = [m["coherence"]["snapshots"][c]["coverage"]["exact"] for c in V.cutoffs(m)]
        return (all(x["no_overlap_pairs"] < y["no_overlap_pairs"] for x, y in zip(cov, cov[1:]))
                and cov[0]["period_strata"] == 1)

    def stability_profile(m):
        pt, cs = m["stability"]["perturbation"], V.cutoffs(m)
        above, idx = V.above_null(m)
        n_loc, loc = V.localised(m)
        share = [x for x in map(V.untouched_share, loc) if x is not None]
        return (pt[cs[0]]["hari"]["lo"] > pt[cs[-1]]["hari"]["hi"] and n_loc == len(loc) > 0 and above < len(idx) / 2
                and bool(share) and min(share) > 0.5)

    def faith_profile(m):
        fa = m["faithfulness"]
        lv = list(fa["by_level"].values())
        return fa["over_claim"]["ci95"][0] > 0.5 and lv[0]["over_claim"]["ci95"][1] < lv[-1]["over_claim"]["ci95"][0]

    def abstract_within_closer(m):
        x = m.get("abstract_coherence")
        if not x:
            return False
        sm = x["summary"]
        return (sm["difference_ci95"][0] > 0 and sm["difference"] > sm["permutation"]["null_q97.5"]
                and x["leave_one_out"]["min"]["difference"] > 0)

    def navigation_lost_l1(m):
        nr = m["retrieval"]["diagnostics"]["never_reached"]
        return sw(navigation_not_established)(m) and bool(nr) and all(lv == 1 for lv in nr.values())

    return {
        "lift_ci_chance": ("report", "every lift's paper-bootstrap CI (exact filter, interval scheme) contains 1", lift_ci_chance),
        "protocol_counts": ("report", "18 questions (14 type A, 4 type B); perturbation removes 10% of hyper-edges with 5 seeds",
                            protocol_counts),
        "coherence_late": ("report", "every level of the two latest snapshots is robust (exact filter) and no cell is below both nulls",
                           coherence_late),
        "coverage_grows": ("report", "no-overlap pairs grow with the snapshot and the first snapshot has one period stratum",
                           coverage_grows),
        "stability_profile": ("report", "perturbation HARI intervals of the first and last snapshot do not overlap (first higher); every "
                              "level x transition cell is localised, with untouched nodes carrying most reassignment in each; fewer "
                              "than half the cross-snapshot indices beat the null",
                              stability_profile),
        "faith_profile": ("report", "over-claim CI above one half; L0 CI below L1 CI", faith_profile),
        "abstract_within_closer": ("report", "abstract closeness difference: bootstrap CI above 0, above the permutation 97.5% quantile, "
                                   "positive with any one super-node holding two or more papers left out", abstract_within_closer),
        "sweep_grid": ("report", "the five α values 0, 0.25, 0.5, 0.75 and 1", sw(lambda w: w.alphas == [0.0, 0.25, 0.5, 0.75, 1.0])),
        "reference": ("report", "the reference is α = 0.5, and the stability comparisons with it are paired by seed "
                      "(same seeds, edge fraction and subsamples for every variant)", sw(paired_ref)),
        "recommended": ("report", "the rule recommends α = 0.75, which is the configured default of the main run",
                        sw(lambda w: rec(w) == 0.75 == w.default)),
        "most_robust": ("report", "the recommended α has more robust cells than every other variant and no below-null cell", sw(most_robust)),
        "last_indistinct": ("report", "at the last snapshot its paired HARI interval contains 0, and its over-claim CI (all snapshots) "
                            "overlaps the reference's",
                            sw(last_indistinct)),
        "stability_loss": ("report", "its paired HARI differences lie below 0 exactly at the first snapshot (perturbation) and one "
                           "transition (cross-snapshot), and above 0 at one transition", sw(stability_loss)),
        "names_most_robust": ("report", "α = 1 has the highest perturbation HARI, an interval above every other variant's, and no "
                              "robust cell", sw(names_most_robust)),
        "faith_tradeoff": ("report", "the recommended α has the highest over-claim point estimate of all variants, and its CI overlaps "
                           "the reference's", sw(faith_tradeoff)),
        "retrieval_mixed": ("report", "same drill-down favour count as the reference; measures better and worse, type-A reach worse; "
                            "for every type drill-down scores fewer candidates than flat but needs more items inspected to "
                            "the first item", sw(retrieval_mixed)),
        "navigation_not_established": ("report", "at the shipped α, drill-down's type-A method hit-rate is not above flat's and its "
                                       "type-A reach is below flat's; for every type it scores fewer candidates but needs more items inspected to "
                                       "the first item; every unreached question is lost at L1", navigation_lost_l1),
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
        sys.exit(f"{path}: unknown claim tags or tags registered for another document {unknown}; registered but untagged {unused}; claims that do not hold on "
                 "metrics.json: " + ("; ".join(f"{n} ({CLAIMS[n][1]})" for n in false) or "none"))
    return found


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--run", default="out")
    ap.add_argument("--doc", choices=sorted(DOCS), default="report", help="which document to render (default: report)")
    ap.add_argument("--sweep", action="store_true", help="alias of --doc sweep")
    ap.add_argument("--report", help="the document's path (default: that of --doc)")
    ap.add_argument("--check", action="store_true", help="exit 1 if the document's tables are not up to date")
    a = ap.parse_args(argv)
    doc = "sweep" if a.sweep else a.doc
    default, tables, sweep_view = DOCS[doc]
    run = Run(a.run)
    r = Sweep(run.m) if sweep_view else run
    path = Path(a.report or default)
    text = path.read_text()
    found = [m.group(2) for m in BLOCK.finditer(text)]
    stray = [l for l in BLOCK.sub("", text).splitlines() if l.lstrip().startswith("|")]
    if stray or len(found) != len(set(found)):
        sys.exit(f"{path}: tables outside generated blocks {stray[:3]} or duplicate blocks {sorted(found)}")
    unknown, missing = set(found) - set(tables), set(tables) - set(found)
    if unknown or missing:
        sys.exit(f"{path}: unknown table blocks {sorted(unknown)}, missing {sorted(missing)}")
    claims = check_claims(text, run.m, path, doc)
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
