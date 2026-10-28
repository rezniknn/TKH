"""T6 extrinsic utility: the drill-down retrieval agent (tkh/retrieve.py) against the flat baseline, on the questions of
data/questions.csv scored with data/ground_truth.json. Only the evaluator reads ground truth.

Gold resolution (`resolve_gold`), per question, on the question's snapshot:
  methods (A)     a GT name matches leaf nodes of the answer kinds, by the first tier that matches:
                  exact     name_key of the surface form or an alias ("DeepH-E3")
                  acronym   name_key of a parenthetical ("GAP" -> "Gaussian approximation potential (GAP) for silicon")
                  prefix    name_key of the first '-'/space segment, >= 3 characters ("Orb" -> "Orb-v2")
                  conceptual names no node carries ("physics-informed") are unattainable.
  citations (A)   "Surname [& Surname | et al.] YYYY [(hint)]" -> articles whose author set contains every surname
                  (diacritics folded), year within +-1 (the exact year preferred), the hint, if given, in the title or a
                  presented method's name when that leaves any candidate. Author order is not in the export.
  citations (B)   source keys -> articles by title (name_key equality or word Jaccard >= 0.8).
  claims (B)      a required claim is attainable if one of its sources resolves to an article with claims in the
                  snapshot; it is hit when the answer returns a claim of such an article (paraphrased GT claims are
                  matched by source, not by wording).
Metrics, per question and system (hier, flat):
  hit_rate        hits / attainable GT items among the answer's top-k, separately for methods or claims and citations
  steps           steps to the first target, one step = one node the agent inspects: hier = super-nodes scored on the
                  way down + the target's rank in the pool; flat = its rank among all leaves of the answer kinds; a
                  target not in the hier pool is censored at N + 1 (N = the flat candidate count).
                  Targets: the resolved method nodes (A) or the claims of resolved source articles (B).
  lost_at_level   (hier, diagnostic) the first level at which no kept super-node holds a target (None: reached).
Summaries: means over questions per type, and the paired hier - flat difference with a bootstrap 95% CI over questions.
Objective H (`objective`, the selection criterion of eval/retrieval_experiments.py): the mean over questions with
targets of the mean of their item (methods / claims) and citation hit-rates.
"""

from collections import defaultdict
from dataclasses import asdict
import csv
import json
import re

import numpy as np

from tkh import semantic as sm
from tkh.retrieve import KINDS, Agent, Settings, fold, surname

YEAR = re.compile(r"\b((?:19|20)\d\d)\b")


def read_questions(path):
    with open(path, newline="", encoding="utf-8") as f:
        return [{"id": r["question_id"], "question": r["question"], "type": r["type"].strip()}
                for r in csv.DictReader(f, delimiter=";")]


def _segment(name):
    return sm.name_key(re.split(r"[\s\-]", sm.clean(name), maxsplit=1)[0])


def resolve_method(name, ix, kinds):
    """(tier, [node ids]) for one GT method name on a snapshot index."""
    want = sm.name_key(name)
    cand = [v for v in ix.leaves if ix.type[v] in kinds]
    tiers = [("exact", lambda v: want in ix.keys[v]),
             ("acronym", lambda v: want in {sm.name_key(p) for p in re.findall(r"\(([^)]*)\)", ix.name[v])}),
             ("prefix", lambda v: len(want) >= 3 and _segment(ix.name[v]) == want)]
    for tier, ok in tiers:
        hit = [v for v in cand if want and ok(v)]
        if hit:
            return tier, hit
    return "unattainable", []


def parse_citation(c):
    """'Li et al. 2022 (DeepH)' -> (['li'], 2022, 'DeepH')."""
    hint = re.search(r"\(([^)]*)\)\s*$", c)
    y = YEAR.search(c)
    who = c[:y.start()] if y else c
    who = re.sub(r"\bet al\.?", "", who)
    names = [fold(s.strip().split(" ")[-1]) for s in re.split(r"&|\band\b|,", who) if s.strip()]
    return names, int(y.group(1)) if y else None, hint.group(1) if hint else None


def resolve_citation(c, ix):
    names, year, hint = parse_citation(c)
    if not names or year is None:
        return "unattainable", []
    sur = {a: {surname(n) for n in ix.authors.get(a, [])} for a in ix.art_year}
    cand = [a for a in ix.art_year if abs(ix.art_year[a] - year) <= 1 and set(names) <= sur[a]]
    exact = [a for a in cand if ix.art_year[a] == year]
    cand = exact or cand
    if hint and len(cand) > 1:
        h = sm.name_key(hint)
        hinted = [a for a in cand if h in sm.name_key(ix.art_title.get(a, ""))
                  or any(h in sm.name_key(ix.name[v]) for v in ix.presents.get(a, ()))]
        cand = hinted or cand
    return ("unattainable" if not cand else "unique" if len(cand) == 1 else "ambiguous"), sorted(cand)


def _words(s):
    return set(re.findall(r"[a-z0-9]+", fold(s)))


def resolve_source(src, ix):
    t, tw = sm.name_key(src.get("title", "")), _words(src.get("title", ""))
    hit = [a for a, title in ix.art_title.items()
           if sm.name_key(title) == t or len(tw & _words(title)) / max(1, len(tw | _words(title))) >= 0.8]
    return ("unique" if len(hit) == 1 else "ambiguous" if hit else "unattainable"), sorted(hit)


def resolve_gold(gt, ix):
    """{kind: [{item, tier, nodes}]} and the target node set for steps-to-target."""
    if gt["type"] == "A":
        methods = [{"item": m, **dict(zip(("tier", "nodes"), resolve_method(m, ix, KINDS["A"])))}
                   for m in gt["expected_methods"]]
        cits = [{"item": c, **dict(zip(("tier", "nodes"), resolve_citation(c, ix)))} for c in gt["required_citations"]]
        return {"methods": methods, "citations": cits}, sorted({v for m in methods for v in m["nodes"]})
    src = {k: dict(zip(("tier", "articles"), resolve_source(s, ix))) for k, s in gt["sources"].items()}
    claims_of = defaultdict(list)
    for v in ix.leaves:
        if ix.type[v] == "claim":
            for a in ix.articles_of[v]:
                claims_of[a].append(v)
    claims = []
    for c in gt["required_claims"]:
        arts = sorted({a for k in c["sources"] for a in src.get(k, {}).get("articles", []) if claims_of[a]})
        claims.append({"item": c["id"], "tier": "source" if arts else "unattainable", "articles": arts,
                       "nodes": sorted({v for a in arts for v in claims_of[a]})})
    cits = [{"item": k, "tier": src[k]["tier"], "nodes": src[k]["articles"]} for k in gt["required_citations"]]
    return {"claims": claims, "citations": cits}, sorted({v for c in claims for v in c["nodes"]})


def score(ans, gold, targets, ix, n_flat):
    """Hit-rates and steps-to-target of one answer."""
    out = {}
    if "methods" in gold:
        got_ids, got_keys = set(ans["method_nodes"]), {sm.name_key(m) for m in ans["expected_methods"]}
        hits = [bool(set(g["nodes"]) & got_ids or {sm.name_key(ix.name[v]) for v in g["nodes"]} & got_keys)
                for g in gold["methods"] if g["nodes"]]
        out["methods"] = _rate(hits)
    else:
        arts = {a for v in ans["claim_nodes"] for a in ix.articles_of[v]}
        out["claims"] = _rate([bool(set(g["articles"]) & arts) for g in gold["claims"] if g["nodes"]])
    cited = set(ans["citation_articles"])
    out["citations"] = _rate([bool(set(g["nodes"]) & cited) for g in gold["citations"] if g["nodes"]])
    out["n_articles"] = len(cited)
    t = set(targets)
    rank = next((i + 1 for i, v in enumerate(ans["ranked"]) if v in t), None)
    out["steps"] = (None if not t else n_flat + 1 if rank is None else ans["n_supernodes_scored"] + rank)
    out["reached"] = rank is not None
    if ans["trace"] and t:   # diagnostic: the first level whose kept super-nodes hold no target
        out["lost_at_level"] = next((lv for lv in sorted({x["level"] for x in ans["trace"]})
                                     if not any(t & set(ix.sn[x["id"]]["member_ids"])
                                                for x in ans["trace"] if x["level"] == lv and x["kept"])), None)
    return out


def _rate(hits):
    return {"hits": sum(hits), "attainable": len(hits), "rate": sum(hits) / len(hits) if hits else None}


def _boot(x, B, seed):
    x = np.asarray(x, float)
    if not len(x):
        return None
    rng = np.random.default_rng(seed)
    b = x[rng.integers(0, len(x), (B, len(x)))].mean(axis=1)
    return {"mean": float(x.mean()), "ci95": [float(np.quantile(b, 0.025)), float(np.quantile(b, 0.975))], "n": int(len(x))}


def summarise(per_q, B=2000, seed=0):
    """Per type: mean hit-rates and steps per system, and paired hier - flat differences with bootstrap CIs."""
    out = {}
    for qtype, item in (("A", "methods"), ("B", "claims")):
        qs = [p for p in per_q.values() if p["type"] == qtype]
        res = {"n_questions": len(qs)}
        for metric in (item, "citations", "steps"):
            get = (lambda p, s: p[s]["steps"]) if metric == "steps" else (lambda p, s: p[s][metric]["rate"])
            both = [(get(p, "hier"), get(p, "flat")) for p in qs if get(p, "hier") is not None]
            res[metric] = {s: _boot([x[i] for x in both], B, seed) for i, s in enumerate(("hier", "flat"))}
            res[metric]["hier_minus_flat"] = _boot([h - f for h, f in both], B, seed)
            if metric == "steps":
                res[metric]["median"] = {s: float(np.median([x[i] for x in both])) if both else None
                                         for i, s in enumerate(("hier", "flat"))}
                res[metric]["reached"] = {s: sum(p[s]["reached"] for p in qs if p[s]["steps"] is not None)
                                          for s in ("hier", "flat")}
        out[qtype] = res
    return out


def evaluate(agent, questions, gt, golds=None):
    """Both systems on every question -> (per-question scores, answers). `golds` ({qid: (gold, targets)}) caches the
    gold resolution, which depends only on the snapshot, not on the retrieval settings."""
    per_q, answers = {}, {}
    for q in questions:
        hier, flt = (agent.answer(q["question"], q["type"], m) for m in ("hier", "flat"))
        ix = agent.index(hier["snapshot"])
        if golds is None or q["id"] not in golds:
            g = resolve_gold(gt[q["id"]], ix)
            if golds is not None:
                golds[q["id"]] = g
        gold, targets = golds[q["id"]] if golds is not None else g
        n_flat = len(flt["ranked"])
        per_q[q["id"]] = {"type": q["type"], "snapshot": hier["snapshot"], "snapshot_source": hier["snapshot_source"],
                          "n_targets": len(targets), "n_flat_candidates": n_flat, "pool": len(hier["ranked"]),
                          "n_supernodes_scored": hier["n_supernodes_scored"],
                          "ceiling": {kind: {"attainable": sum(bool(g["nodes"]) for g in gs), "total": len(gs)}
                                      for kind, gs in gold.items()},
                          "hier": score(hier, gold, targets, ix, n_flat), "flat": score(flt, gold, targets, ix, n_flat)}
        strip = lambda a: {x: y for x, y in a.items() if x != "ranked"}   # noqa: E731
        answers[q["id"]] = {"question": q["question"], "type": q["type"], "gold": gold,
                            "hier": strip(hier), "flat": strip(flt)}
    return per_q, answers


def objective(per_q, system="hier"):
    """H: mean over questions with targets of the mean of their item and citation hit-rates -> (H, {qid: h})."""
    h = {}
    for qid, p in per_q.items():
        if not p["n_targets"]:
            continue
        rates = [r["rate"] for kind, r in p[system].items() if kind in ("methods", "claims", "citations")
                 and isinstance(r, dict) and r["rate"] is not None]
        h[qid] = float(np.mean(rates))
    return (float(np.mean(list(h.values()))) if h else None), h


def retrieval_check(tkh, run_dir, cutoffs, questions_path, gt_path, settings=None, B=2000, seed=0):
    """(metrics section, per-question answers)."""
    settings = settings or Settings()
    gt = json.loads(open(gt_path, encoding="utf-8").read())
    per_q, answers = evaluate(Agent(tkh, run_dir, cutoffs, settings), read_questions(questions_path), gt)
    metrics = {"config": {**{k: (list(v) if isinstance(v, tuple) else v) for k, v in asdict(settings).items()},
                          "bootstrap": B, "seed": seed, "questions": str(questions_path), "ground_truth": str(gt_path)},
               "snapshots": {qid: p["snapshot"] for qid, p in per_q.items()},
               "objective_H": {s: objective(per_q, s)[0] for s in ("hier", "flat")},
               "summary": summarise(per_q, B, seed), "per_question": per_q}
    return metrics, answers
