"""T6 extrinsic utility: the drill-down retrieval agent (tkh/retrieve.py) against the flat baseline, on the questions of
data/questions.csv scored with data/ground_truth.json. Only the evaluator reads ground truth. Design and rationale:
notebooks/05_retrieval_design.ipynb.

Gold resolution (`resolve_gold`), per question, on the snapshot the evaluator itself derives from the question text:
  methods (A)        a GT name matches leaf nodes of the answer kinds by the first rule that matches:
                     exact    name_key of the surface form or an alias ("DeepH-E3")
                     acronym  name_key of a parenthetical ("GAP" -> "Gaussian approximation potential (GAP) ...")
                     names no node carries ("physics-informed", "Orb" for "Orb-v2") are unattainable.
  citations (A)      "Surname [& Surname | et al.] YYYY [(hint)]" -> articles whose author set contains every surname
                     (diacritics folded), year within +-1 (the exact year preferred); the hint narrows ambiguous
                     candidates by title or presented method. Author order is not in the export.
  method claims (A)  each ';'-separated part of a method's evidence sources is resolved as a citation; a GT method
                     claim is attainable if the graph holds a claim from one of those articles on a claims edge of a
                     resolved node of the method.
  sources (B)        DOI first, then title (name_key equality or word Jaccard >= 0.8).
  claims (B)         attainable if one of its sources resolves to an article with claims in the snapshot.
  errors (A)         fp_categories.wrong_domain / outdated_as_main names, resolved like methods.
Metrics, per question and system (hier, flat), on attainable items only:
  M1 hit-rate        methods (a resolved node or a node with the same name_key returned), method claims (method hit
                     and one of its returned graph claims from an evidence article; scored per method), claims (a claim
                     of a source article returned), citations (a resolved article cited). Claim credit is by source
                     article: a returned claim's text is never compared with the GT assertion, and one returned claim
                     can credit several assertions of the same sources.
  M2 error_rate      share of the k answers that resolve to a wrong_domain / outdated_as_main name (valid_but_unlisted
                     is neutral).
  M3 inspection      the reader's effort: hier = the L0-L1 labels shown (every labelled super-node scored) + the item's
                     rank in the pool; flat = its rank among all leaves of the answer kinds. One target per attainable
                     GT item (method or required claim); to the first item and to 50% of the items; an item not
                     reached is censored at N + 1 (N = the snapshot's nodes of the answer kinds). Medians, with reach.
  M4 scored          computation: candidates scored, hier = super-nodes scored (all levels) + pool leaves ranked;
                     flat = every leaf of the answer kinds. Not a wall-clock latency. Median.
  end_to_end         M1 with unattainable GT items counted as misses: hits / all GT items of the kind.
  lost_at_level      (hier, diagnostic) the first level at which no kept super-node holds a target (None: reached).
Summaries per question type: the mean (M3, M4: median) per system and of the paired hier - flat differences; point
estimates, no intervals.
"""

import csv
import json
from pathlib import Path
import re

import numpy as np

from tkh import semantic as sm
from tkh.config import REPO_ROOT
from tkh.retrieve import BEAM, K, KINDS, Agent, fold

YEAR = re.compile(r"\b((?:19|20)\d\d)\b")
ERROR_CATEGORIES = ("wrong_domain", "outdated_as_main")
METRICS = {"A": ["methods", "method_claims", "citations", "error_rate", "reached", "inspect_first", "inspect_half",
                 "scored"],
           "B": ["claims", "citations", "reached", "inspect_first", "inspect_half", "scored"]}
MEDIANS = ("inspect_first", "inspect_half", "scored")   # censored or count measures


def read_questions(path):
    with open(path, newline="", encoding="utf-8") as f:
        return [{"id": r["question_id"], "question": r["question"], "type": r["type"].strip()}
                for r in csv.DictReader(f, delimiter=";")]


def expected_snapshot(question, v, cutoffs):
    """The evaluator's own snapshot for a question, independent of the agent's parser: the GT `as_of` year (type B),
    else the first year written in the question; no year -> the latest cutoff; before the first cutoff -> None."""
    m = YEAR.search(v.get("as_of") or question)
    if not m:
        return max(cutoffs)
    ok = [c for c in cutoffs if c <= int(m.group(1))]
    return max(ok) if ok else None


def _rel(p):
    p = Path(p).resolve()
    return str(p.relative_to(REPO_ROOT)) if p.is_relative_to(REPO_ROOT) else p.name


def resolve_method(name, F, kinds=KINDS["A"]):
    """(rule, [node ids]) for one GT method name on a snapshot's facts."""
    want = sm.name_key(name)
    cand = [v for v in F.ids if F.type[v] in kinds]
    rules = [("exact", lambda v: want in F.keys[v]),
             ("acronym", lambda v: want in {sm.name_key(p) for p in re.findall(r"\(([^)]*)\)", F.name[v])})]
    for rule, ok in rules:
        hit = [v for v in cand if want and ok(v)]
        if hit:
            return rule, hit
    return "unattainable", []


def parse_citation(c):
    """'Li et al. 2022 (DeepH)' -> (['li'], 2022, 'DeepH')."""
    hint = re.search(r"\(([^)]*)\)\s*$", c)
    y = YEAR.search(c)
    who = re.sub(r"\bet al\.?", "", c[:y.start()] if y else c)
    names = [fold(x.strip().split(" ")[-1]) for x in re.split(r"&|\band\b|,", who) if x.strip()]
    return names, int(y.group(1)) if y else None, hint.group(1) if hint else None


def resolve_citation(c, F):
    """(unique | ambiguous | unattainable, [article ids])."""
    names, year, hint = parse_citation(c)
    if not names or year is None:
        return "unattainable", []
    sur = {a: {fold(sm.clean(n).split(" ")[-1]) for n in F.authors.get(a, [])} for a in F.year}
    cand = [a for a in F.year if abs(F.year[a] - year) <= 1 and set(names) <= sur[a]]
    cand = [a for a in cand if F.year[a] == year] or cand
    if hint and len(cand) > 1:
        h = sm.name_key(hint)
        cand = [a for a in cand if h in sm.name_key(F.title.get(a, "")) or
                any(h in sm.name_key(F.name[v]) for v in F.presents.get(a, ()))] or cand
    return ("unattainable" if not cand else "unique" if len(cand) == 1 else "ambiguous"), sorted(cand)


def _words(s):
    return set(re.findall(r"[a-z0-9]+", fold(s)))


def resolve_source(src, F):
    """(doi | title | unattainable, [article ids]) for a type-B source entry."""
    doi = str(src.get("doi") or "").lower()
    hit = [a for a, d in F.doi.items() if doi and d == doi]
    if hit:
        return "doi", hit
    t, tw = sm.name_key(src.get("title", "")), _words(src.get("title", ""))
    hit = [a for a, title in F.title.items()
           if sm.name_key(title) == t or len(tw & _words(title)) / max(1, len(tw | _words(title))) >= 0.8]
    return ("title" if hit else "unattainable"), sorted(hit)


def resolve_gold(v, F):
    """Every ground-truth item of one question -> graph nodes / articles, with its rule; step items and targets."""
    g = {"type": v["type"]}
    if v["type"] == "A":
        g["methods"] = {m: dict(zip(("rule", "nodes"), resolve_method(m, F))) for m in v["expected_methods"]}
        g["citations"] = {c: dict(zip(("rule", "articles"), resolve_citation(c, F))) for c in v["required_citations"]}
        fp = v.get("fp_categories", {})
        g["fp"] = {cat: {n: resolve_method(n, F)[1] for n in fp[cat]} for cat in ERROR_CATEGORIES if cat in fp}
        g["method_claims"] = []
        for m, claims in v["method_claims"].items():
            arts = sorted({a for e in v["method_evidence"][m] for part in e["source"].split(";")
                           for a in resolve_citation(part.strip(), F)[1]})
            ok = any(set(F.articles_of[x]) & set(arts) for n in g["methods"][m]["nodes"] for x in F.method_claims[n])
            g["method_claims"] += [{"method": m, "text": t, "articles": arts, "source_resolves": bool(arts),
                                    "attainable": ok} for t in claims]
        g["step_items"] = [r["nodes"] for r in g["methods"].values() if r["nodes"]]   # one per attainable GT method
    else:
        src = {k: dict(zip(("rule", "articles"), resolve_source(s, F))) for k, s in v["sources"].items()}
        g["sources"] = src
        g["citations"] = {k: src[k] for k in v["required_citations"]}
        g["claims"] = []
        for c in v["required_claims"]:
            arts = sorted({a for k in c["sources"] for a in src[k]["articles"] if F.claims_of[a]})
            g["claims"].append({"id": c["id"], "articles": arts, "attainable": bool(arts),
                                "nodes": sorted({x for a in arts for x in F.claims_of[a]})})
        g["step_items"] = [c["nodes"] for c in g["claims"] if c["attainable"]]   # one per attainable required claim
    g["targets"] = sorted({x for it in g["step_items"] for x in it})
    return g


def ceilings(g):
    """{item kind: {attainable, total}} for one question."""
    if g["type"] == "A":
        out = {"methods": [bool(r["nodes"]) for r in g["methods"].values()],
               "method_claims": [c["attainable"] for c in g["method_claims"]],
               "citations": [bool(r["articles"]) for r in g["citations"].values()]}
    else:
        out = {"claims": [c["attainable"] for c in g["claims"]],
               "citations": [bool(r["articles"]) for r in g["citations"].values()]}
    return {k: {"attainable": sum(x), "total": len(x)} for k, x in out.items()}


def _rate(hits):
    return sum(hits) / len(hits) if hits else None


def score(ans, g, F, sn=None):
    """M1-M3 of one answer against one question's resolved gold."""
    out = {}
    got_nodes, got_keys = set(ans["node_ids"]), {sm.name_key(F.name[v]) for v in ans["node_ids"]}
    cited = set(ans["article_ids"])
    if g["type"] == "A":
        hit_m = {m: bool(set(r["nodes"]) & got_nodes or {sm.name_key(F.name[v]) for v in r["nodes"]} & got_keys)
                 for m, r in g["methods"].items() if r["nodes"]}
        out["methods"] = _rate(list(hit_m.values()))
        e2e = {"methods": (sum(hit_m.values()), len(g["methods"]))}
        mc = []
        for c in g["method_claims"]:
            if c["attainable"] and hit_m.get(c["method"]):
                names = {F.name[v] for v in g["methods"][c["method"]]["nodes"]}
                ret = [x for v, xs in ans["method_claim_ids"].items() if F.name[v] in names for x in xs]
                mc.append(any(set(F.articles_of[x]) & set(c["articles"]) for x in ret))
            elif c["attainable"]:
                mc.append(False)
        out["method_claims"] = _rate(mc)
        e2e["method_claims"] = (sum(mc), len(g["method_claims"]))
        if g["fp"]:
            wrong = {v for ns in g["fp"].values() for vs in ns.values() for v in vs}
            wrong_keys = {sm.name_key(F.name[v]) for v in wrong}
            out["error_rate"] = sum(v in wrong or sm.name_key(F.name[v]) in wrong_keys
                                    for v in ans["node_ids"]) / max(1, len(ans["node_ids"]))
    else:
        returned = {a for v in ans["node_ids"] for a in F.articles_of[v]}
        hit_c = [bool(set(c["articles"]) & returned) for c in g["claims"] if c["attainable"]]
        out["claims"] = _rate(hit_c)
        e2e = {"claims": (sum(hit_c), len(g["claims"]))}
    hit_r = [bool(set(r["articles"]) & cited) for r in g["citations"].values() if r["articles"]]
    out["citations"] = _rate(hit_r)
    e2e["citations"] = (sum(hit_r), len(g["citations"]))
    out["end_to_end"] = {k: h / n for k, (h, n) in e2e.items() if n}
    out["n_articles_cited"] = len(cited)
    # inspection: labels shown, then the ranked pool; computation: candidates scored; one target per GT item
    items, n_flat = g["step_items"], sum(F.type[v] in KINDS[g["type"]] for v in F.ids)
    out["scored"] = ans["n_supernodes_scored"] + ans["n_leaves_scored"]
    pos = {v: i + 1 for i, v in enumerate(ans["ranked"])}
    found = sorted(min(pos[v] for v in it if v in pos) for it in items if any(v in pos for v in it))
    if items:
        out["reached"] = bool(found)
        out["inspect_first"] = ans["n_labels_shown"] + found[0] if found else n_flat + 1
        half = int(np.ceil(len(items) / 2))
        out["inspect_half"] = ans["n_labels_shown"] + found[half - 1] if len(found) >= half else n_flat + 1
        if ans["trace"] and sn is not None:   # diagnostic: the first level whose kept super-nodes hold no target
            t = set(g["targets"])
            out["lost_at_level"] = next((lv for lv in sorted({x["level"] for x in ans["trace"]})
                                         if not any(t & set(sn[x["id"]]["member_ids"])
                                                    for x in ans["trace"] if x["level"] == lv and x["kept"])), None)
    return out


def summarise(per_q):
    """Per type and metric: n, the mean (MEDIANS: median) per system, and of the paired hier - flat differences;
    hit-rates also end to end (all GT items)."""
    out = {}
    for t, ms in METRICS.items():
        qs = [p for p in per_q.values() if p["type"] == t and "hier" in p]
        res = {"n_questions": len(qs)}
        for m in ms:
            pairs = [(float(p["hier"][m]), float(p["flat"][m])) for p in qs
                     if p["hier"].get(m) is not None and p["flat"].get(m) is not None]
            stat = np.median if m in MEDIANS else np.mean               # censored inspection: medians, not means
            f = (lambda x: float(stat(x)) if len(x) else None)          # noqa: E731
            res[m] = {"n": len(pairs), "stat": stat.__name__, "hier": f([h for h, _ in pairs]),
                      "flat": f([x for _, x in pairs]), "hier_minus_flat": f([h - x for h, x in pairs])}
            e2e = [(p["hier"]["end_to_end"][m], p["flat"]["end_to_end"][m]) for p in qs
                   if m in p["hier"].get("end_to_end", {}) and m in p["flat"].get("end_to_end", {})]
            if e2e:
                res[m]["end_to_end"] = {"n": len(e2e), "hier": float(np.mean([h for h, _ in e2e])),
                                        "flat": float(np.mean([x for _, x in e2e]))}
        res["ceilings"] = {k: {s: sum(p["ceiling"][k][s] for p in qs) for s in ("attainable", "total")}
                           for k in qs[0]["ceiling"]} if qs else {}
        out[t] = res
    return out


def diagnostics(answers, per_q):
    """Routing and breadth diagnostics of the drill-down (not metrics)."""
    kept = {lv: [] for lv in sorted({x["level"] for a in answers.values() for x in a["hier"].get("trace", [])})}
    for a in answers.values():
        for lv in kept:
            sc = [x for x in a["hier"].get("trace", []) if x["level"] == lv]
            if sc:
                kept[lv].append(sum(x["kept"] for x in sc) / len(sc))
    scored = [a["hier"]["n_supernodes_scored"] for a in answers.values() if "n_supernodes_scored" in a["hier"]]
    shown = [a["hier"]["n_labels_shown"] for a in answers.values() if "n_labels_shown" in a["hier"]]
    pool = [a["hier"]["n_leaves_scored"] for a in answers.values() if "n_leaves_scored" in a["hier"]]
    with_items = [q for q, p in per_q.items() if "reached" in p.get("hier", {})]
    return {"kept_over_frontier": {f"L{lv}": {"mean": float(np.mean(v)), "min": float(min(v)), "max": float(max(v))}
                                   for lv, v in kept.items() if v},
            "supernodes_scored": {"min": int(min(scored)), "max": int(max(scored))} if scored else None,
            "labels_shown": {"min": int(min(shown)), "max": int(max(shown))} if shown else None,
            "pool": {"min": int(min(pool)), "max": int(max(pool))} if pool else None,
            "never_reached": {q: per_q[q]["hier"].get("lost_at_level") for q in with_items if not per_q[q]["hier"]["reached"]},
            "articles_cited": {t: {s: float(np.mean([per_q[q][s]["n_articles_cited"] for q in with_items
                                                     if per_q[q]["type"] == t])) for s in ("hier", "flat")}
                               for t in ("A", "B") if any(per_q[q]["type"] == t for q in with_items)}}


def retrieval_check(tkh, run_dir, cutoffs, questions_path, gt_path, beam=BEAM, k=K):
    """(metrics section, per-question answers with their resolved gold). Abstained questions are recorded, not scored."""
    questions = read_questions(questions_path)
    gt = json.loads(open(gt_path, encoding="utf-8").read())
    agent = Agent(tkh, run_dir, cutoffs, beam, k)
    per_q, answers = {}, {}
    for q in questions:
        hier, flt = (agent.answer(q["question"], q["type"], m) for m in ("hier", "flat"))
        expected = expected_snapshot(q["question"], gt[q["id"]], cutoffs)
        p = {"type": q["type"], "snapshot": hier["snapshot"], "snapshot_source": hier["snapshot_source"],
             "snapshot_ok": hier["snapshot"] == expected}
        if not hier.get("abstain"):
            ix = agent.index(hier["snapshot"])
            g = resolve_gold(gt[q["id"]], ix.F)
            p.update(n_step_items=len(g["step_items"]), n_targets=len(g["targets"]), pool=len(hier["ranked"]),
                     n_supernodes_scored=hier["n_supernodes_scored"], n_labels_shown=hier["n_labels_shown"],
                     ceiling=ceilings(g),
                     hier=score(hier, g, ix.F, ix.sn), flat=score(flt, g, ix.F, ix.sn))
        per_q[q["id"]] = p
        strip = lambda a: {x: y for x, y in a.items() if x != "ranked"}   # noqa: E731
        answers[q["id"]] = {"question": q["question"], "type": q["type"], "gold": g if not hier.get("abstain") else None,
                            "hier": strip(hier), "flat": strip(flt)}
    metrics = {"config": {"beam": list(beam), "k": k, "scorer": "keyword overlap on snapshot leaf texts",
                          "label_weight": 0.5, "method_rules": ["exact", "acronym"],
                          "questions": _rel(questions_path), "ground_truth": _rel(gt_path)},
               "summary": summarise(per_q), "diagnostics": diagnostics(answers, per_q), "per_question": per_q}
    return metrics, answers
