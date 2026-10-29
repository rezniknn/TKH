"""T6 label faithfulness: an independent NLI/entailment check of every label and gloss against HELD-OUT evidence.

The labeller (tkh/label.py, one model family) wrote each label from the seen half of the super-node's evidence; the
judge (a different family, [labels] judge_model) checks it only against the other half, which the labeller never saw.
  1. decompose  label + gloss -> at most MAX_CLAIMS atomic claims (claims_split.txt). Every claim must pass the content
                check: reuse >= 80% of its content words from label and gloss and keep a non-generic word. If any
                claim fails (or none is returned), the decomposition fails and label and gloss are judged as two
                claims instead. Sensitivity: the previous rule, which dropped failing claims and judged the
                survivors (falling back only when none survived), is also scored (summary "sensitivity")
  2. entail     each claim vs the held-out lines (claim_entail.txt): supported only if the judge cites a numbered
                line that exists (a deterministic check against sycophancy)
  3. rates      over-claim rate = share of judged labels with >= 1 unsupported claim (bootstrap CI over labels);
                claim-level unsupported share; overall and by cutoff, level and cutoff x level
  4. checks     deterministic, no LLM: years after the cutoff, named non-members, future entities
Every LLM answer is cached (data/llm_cache.json), so a repeated run replays offline.
"""

import json
import math
import re
from pathlib import Path

import numpy as np

from eval.experiments import _finite
from tkh.io import load
from tkh.label import LABELLED_LEVELS, Evidence, LLMLabeller, settings
from tkh.llm import CachedLLM, render

MAX_CLAIMS = 3
STOP = set("a an and are as at be by for from group groups has have in into is it its of on or that the their these "
           "this those to using via with which whose they them such than then also more most contains contain includes include "
           "about members member used use share shares shared property properties focus focused related".split())   # claim frame words
NAMED_TYPES = ("method", "dataset")


# ---------------------------------------------------------------- judge

class Judge:
    def __init__(self, cfg, llm=None):
        s = settings(cfg)
        self.s = s
        self.llm = llm or CachedLLM(s["judge_model"], s["cache"], s["endpoint"], s["mode"])
        self.split_t, self.entail_t = f"{s['prompts']}/claims_split.txt", f"{s['prompts']}/claim_entail.txt"

    def decompose_many(self, pairs, max_claims):
        """[(label, gloss)] -> [(claims, ok, survivors)]. claims: the decomposition if every claim passes the content check
        (ok), else [label, gloss]; survivors: the claims judged under the previous rule (failing claims dropped, the
        fallback only when none survive), for the sensitivity check."""
        resps = self.llm.complete_many([render(self.split_t, label=l, gloss=g) for l, g in pairs], self.s["workers"])
        out = []
        for (l, g), r in zip(pairs, resps):
            claims = [str(c).strip() for c in (r.get("claims") or [])] if isinstance(r, dict) else []
            kept = [c for c in claims if _content_ok(c, f"{l} {g}")]
            ok = bool(claims) and len(kept) == len(claims)
            out.append((claims[:max_claims] if ok else [l, g], ok, kept[:max_claims] if kept else [l, g]))
        return out

    def entail_many(self, jobs):
        """[(cutoff, claim, held-out lines)] -> [{"verdict", "line", "quote_ok", "supported"}]. The judge cites a numbered
        line; a claim counts as supported only if the cited line exists (a deterministic check against sycophancy)."""
        prompts = [render(self.entail_t, cutoff=c, claim=cl, evidence="\n".join(f"{i}. {x}" for i, x in enumerate(held, 1)))
                   for c, cl, held in jobs]
        out = []
        for (c, cl, held), r in zip(jobs, self.llm.complete_many(prompts, self.s["workers"])):
            verdict = str(r.get("verdict", "")).lower() if isinstance(r, dict) else "unparsed"
            try:
                line = int(r.get("line", 0)) if isinstance(r, dict) else 0
            except (TypeError, ValueError):
                line = 0
            quote_ok = 1 <= line <= len(held)
            out.append({"verdict": verdict, "line": held[line - 1] if quote_ok else None, "quote_ok": quote_ok,
                        "supported": verdict == "supported" and quote_ok})
        return out


def _words(s):
    return {w for w in re.findall(r"[a-z0-9][a-z0-9\-]+", s.lower()) if w not in STOP and len(w) > 2}


GENERIC = set("model models method methods technique techniques task tasks problem problems component components dataset "
              "datasets metric metrics material materials science chemistry chemical molecular molecules machine learning "
              "deep neural data prediction predicting predict properties property computational computation simulation "
              "simulations approaches approach framework frameworks tools systems".split())


def _content_ok(claim, source):
    """The claim reuses the label and gloss (>= 80% of its content words) and keeps at least one specific word."""
    w = _words(claim)
    return bool(w - GENERIC) and len(w & _words(source)) >= 0.8 * len(w)


# ---------------------------------------------------------------- deterministic checks

def _proper(name):
    return any(sum(ch.isupper() for ch in t) >= 2 or (any(ch.isdigit() for ch in t) and any(ch.isalpha() for ch in t))
               for t in re.findall(r"[\w-]+", name))


class NameChecker:
    """Proper-name-like method/dataset names, matched whole-word; per NAME (duplicate entities share names)."""

    def __init__(self, tkh):
        n = tkh.nodes
        self.entry = n["entry_year"].to_dict()
        self.nodes_of = {}
        al = n["aliases"] if "aliases" in n else [None] * len(n)
        for v, sf, a, t in zip(n.index, n["surface_form"], al, n["type"]):
            if t in NAMED_TYPES:
                for s in [sf, *(a if isinstance(a, list) else [])]:
                    s = str(s).strip()
                    if len(s) >= 3 and _proper(s):
                        self.nodes_of.setdefault(s, set()).add(v)
        self.pats = [(s, re.compile(r"(?<![\w-])" + re.escape(s) + r"(?![\w-])")) for s in sorted(self.nodes_of)]

    def checks(self, text, members, cutoff):
        named = {s: self.nodes_of[s] for s, p in self.pats if p.search(text)}
        years = [int(y) for y in re.findall(r"(?<!\d)(19\d\d|20\d\d)(?!\d)", text)]
        return {"year_after_cutoff": any(y > cutoff for y in years),
                "named_non_member": sorted(s for s, vs in named.items() if not vs & set(members)),
                "future_entity": sorted(s for s, vs in named.items() if all(self.entry.get(v, 0) > cutoff for v in vs))}


# ---------------------------------------------------------------- labels to judge

def _run_tree(run_dir, cutoffs, levels):
    """Labels of the evaluated run: [(cutoff, level, key, parent, members, label, gloss, seen, held)]."""
    rows = []
    for c in cutoffs:
        h = json.loads((Path(run_dir) / str(c) / "hierarchy.json").read_text())
        inp = json.loads((Path(run_dir) / str(c) / "label_inputs.json").read_text())
        for s in h["supernodes"]:
            if s["level"] in levels:
                i = inp[s["id"]]
                rows.append((c, s["level"], f"{c}:{s['id']}", s["parent_id"] and f"{c}:{s['parent_id']}", s["member_ids"],
                             s["label"], s["gloss"], i["seen"], i["held_out"]))   # ids persist across snapshots: key by cutoff
    return rows


# ---------------------------------------------------------------- scoring

def judge_labels(rows, judge, checker, max_claims=MAX_CLAIMS):
    """Decompose and entail every label; returns the summary and the judgement records."""
    decs = judge.decompose_many([(row[5], row[6]) for row in rows], max_claims)
    jobs, meta = [], []
    for row, (claims, ok, surv) in zip(rows, decs):
        if row[8]:
            for cl in claims:
                jobs.append((row[0], cl, row[8])); meta.append((row, cl, "protocol"))
            if surv != claims:   # partial decomposition: the previous rule judged these survivors
                for cl in surv:
                    jobs.append((row[0], cl, row[8])); meta.append((row, cl, "survivors_only"))
    verdicts = judge.entail_many(jobs)
    recs = [{"supernode": row[2], "cutoff": row[0], "level": row[1], "claim": cl, "rule": rule, **v}
            for (row, cl, rule), v in zip(meta, verdicts)]
    partial = {row[2] for row, (claims, _, surv) in zip(rows, decs) if surv != claims}
    per, per_s = {}, {}   # per label: unsupported flags under the protocol / under the previous (survivors) rule
    for x in recs:
        k = x["supernode"]
        if x["rule"] == "protocol":
            per.setdefault(k, []).append(not x["supported"])
        if (x["rule"] == "survivors_only") == (k in partial):
            per_s.setdefault(k, []).append(not x["supported"])
    info = {row[2]: (row[0], row[1]) for row in rows}

    def rates(keys, table=None):
        table = per if table is None else table
        keys = [k for k in keys if k in table]
        return {"over_claim": _ci(np.array([any(table[k]) for k in keys], float)),
                "claim_unsupported": _rate([u for k in keys for u in table[k]])}

    cutoffs, levels = sorted({c for c, _ in info.values()}), sorted({k for _, k in info.values()})
    det = [checker.checks(f"{row[5]} {row[6]}", row[4], row[0]) for row in rows]
    summary = {"labels": len(rows), "judged": len(per), **rates(list(per)),
               "decomposition_ok": float(np.mean([ok for _, ok, _ in decs])) if decs else math.nan,
               "decomposition": {"all_kept": sum(ok for _, ok, _ in decs),
                                 "partial": sum(not ok and s != [r[5], r[6]] for r, (_, ok, s) in zip(rows, decs)),
                                 "none_kept": sum(not ok and s == [r[5], r[6]] for r, (_, ok, s) in zip(rows, decs))},
               "sensitivity": {"rule": "survivors_only: claims failing the content check dropped, the survivors judged",
                               **rates(list(per_s), per_s),
                               "by_level": {f"L{lv}": rates([k for k, (_, ll) in info.items() if ll == lv], per_s)
                                            for lv in levels}},
               "quote_rejected": int(sum(x["verdict"] == "supported" and not x["quote_ok"] for x in recs if x["rule"] == "protocol")),
               "no_held_out": sum(1 for row in rows if not row[8]),
               "deterministic": {k: int(sum(bool(d[k]) for d in det)) for k in ("year_after_cutoff", "named_non_member", "future_entity")},
               "by_cutoff": {str(c): rates([k for k, (cc, _) in info.items() if cc == c]) for c in cutoffs},
               "by_level": {f"L{lv}": rates([k for k, (_, ll) in info.items() if ll == lv]) for lv in levels},
               "by_cutoff_level": {f"{c}:L{lv}": rates([k for k, ck in info.items() if ck == (c, lv)])
                                   for c in cutoffs for lv in levels}}
    return summary, recs


def _rate(xs):
    return float(np.mean(xs)) if xs else math.nan


def _ci(x, B=2000, seed=0):
    if not len(x):
        return {"value": None, "ci95": [None, None], "n": 0}
    rng = np.random.default_rng(seed)
    b = [x[rng.integers(0, len(x), len(x))].mean() for _ in range(B)]
    return {"value": float(x.mean()), "ci95": [float(np.percentile(b, 2.5)), float(np.percentile(b, 97.5))], "n": len(x)}


def faithfulness_check(cfg, run_dir, cutoffs=None, levels=None, relabel=False):
    """All cutoffs and the labelled levels unless overridden; relabel: label the run's tree again with the current
    labeller prompt instead of reading the labels of hierarchy.json (for prompt iteration)."""
    tkh = load(cfg)
    cutoffs = sorted(cutoffs or cfg.cutoffs)
    levels = [k for k in (levels or LABELLED_LEVELS) if k in LABELLED_LEVELS]
    labeller, judge = LLMLabeller(tkh, cfg), Judge(cfg)
    rows = _run_tree(run_dir, cutoffs, levels)
    if relabel:
        for c, k in {(x[0], x[1]) for x in rows}:
            labeller.set_context(c, [x[4] for x in rows if (x[0], x[1]) == (c, k)])
        labeller.llm.complete_many([labeller.prompt(x[0], labeller.view(x[0], x[4])[0], x[4]) for x in rows], labeller.s["workers"])
        rows = [(*x[:5], *labeller(x[0], x[1], x[4]), *labeller.view(x[0], x[4])) for x in rows]
    ev = Evidence(tkh)   # the judge's view: facts with a head method outside the group flag it (Evidence.judge_view)
    rows = [(*x[:8], ev.judge_view(x[0], x[4], x[8])) for x in rows]
    summary, recs = judge_labels(rows, judge, NameChecker(tkh))
    out = {"protocol": {"cutoffs": cutoffs, "levels": levels, "max_claims": MAX_CLAIMS},
           "labeller_model": labeller.s["labeller_model"], "judge_model": judge.s["judge_model"], **summary}
    return _finite(out), recs
