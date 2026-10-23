"""T6 label faithfulness: an independent NLI/entailment check of every label and gloss against HELD-OUT evidence.

The labeller (tkh/label.py, one model family) wrote each label from the seen half of the super-node's evidence; the
judge (a different family, [labels] judge_model) checks it only against the other half, which the labeller never saw.
  1. decompose  label + gloss -> atomic claims (claims_split.txt); a claim must reuse >= 80% of its content words
                from label and gloss, else fall back to [label, gloss]
  2. entail     each claim vs the held-out lines (claim_entail.txt): supported only if the judge's quote is
                actually one of those lines (a deterministic check against sycophancy)
  3. rates      over-claim rate = share of labels with >= 1 unsupported claim; claim-level unsupported share
  4. controls   known-false claims (the first claim of a sibling super-node, and of a random other one) and
                known-true claims ("The group includes <held-out member>") are judged the same way: sensitivity Se,
                specificity Sp, Youden J on sibling controls with a validity gate J >= 0.4, and the Rogan-Gladen
                corrected rate when the gate passes
  5. checks     deterministic, no LLM: years after the cutoff, named non-members, future entities
  6. nulls      the same labeller and judge on configuration-null rebuilds and random-label trees; model minus null
                with a bootstrap interval (a label written from half of an incoherent group's evidence should
                generalise worse to the other half)
Rigor levels (RIGOR) bound the number of LLM calls; every answer is cached, so a repeated run replays offline.
"""

import json
import math
import random
import re
from pathlib import Path

import numpy as np

from eval.experiments import _finite, real_hubs
from tkh.coarsen import concept_nodes
from tkh.hierarchy import Params, anchors, build_concept
from tkh.io import load, snapshot
from tkh.label import LABELLED_LEVELS, LLMLabeller, settings
from tkh.llm import CachedLLM, render
from tkh.null import label_permutation, null_tkh

RIGOR = {   # n_names: true and false member-name controls per label
    "quick": {"levels": [0], "model_cutoffs": "last", "null_cutoffs": "last", "R_config": 1, "R_labels": 1, "n_names": 3, "max_claims": 3},
    "standard": {"levels": [0, 1], "model_cutoffs": "all", "null_cutoffs": "last", "R_config": 3, "R_labels": 3, "n_names": 2, "max_claims": 3},
    "full": {"levels": [0, 1], "model_cutoffs": "all", "null_cutoffs": "all", "R_config": 5, "R_labels": 5, "n_names": 2, "max_claims": 3},
}
J_MIN = 0.4
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
        """[(label, gloss)] -> [(claims, ok)]."""
        resps = self.llm.complete_many([render(self.split_t, label=l, gloss=g) for l, g in pairs], self.s["workers"])
        out = []
        for (l, g), r in zip(pairs, resps):
            claims = [str(c).strip() for c in (r.get("claims") or [])] if isinstance(r, dict) else []
            kept = [c for c in claims if _content_ok(c, f"{l} {g}")]   # generic or invented claims are dropped
            ok = bool(kept) and len(kept) == len(claims)
            out.append((kept[:max_claims] if kept else [l, g], ok))
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


def _norm(s):
    return " ".join(str(s).lstrip("-• ").split()).lower()


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


# ---------------------------------------------------------------- trees to judge

def _parents(levels):
    """[{key: parent key or None}] for nested levels [{key: set(members)}]."""
    out = [{k: None for k in levels[0]}]
    for k in range(1, len(levels)):
        owner = {v: g for g, m in levels[k - 1].items() for v in m}
        out.append({g: owner[next(iter(m))] for g, m in levels[k].items()})
    return out


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


def _full_levels(tkh, snap, concept_levels):
    """Concept levels plus anchored nodes (anchors on the real graph)."""
    anc = anchors(tkh, snap, set().union(*concept_levels[-1].values()))
    out = []
    for lv in concept_levels:
        where = {v: g for g, m in lv.items() for v in m}
        groups = {g: set(m) for g, m in lv.items()}
        for v, a in anc.items():
            groups[where[a]].add(v)
        out.append(groups)
    return out


def _labelled(labeller, c, full, levels, tag):
    """Label the given levels of one tree (batched); rows as in _run_tree."""
    par = _parents(full)
    todo = [(k, g, sorted(m)) for k in levels for g, m in sorted(full[k].items(), key=lambda kv: str(kv[0]))]
    labeller.llm.complete_many([labeller.prompt(c, labeller.view(c, m)[0]) for _, _, m in todo], labeller.s["workers"])
    rows = []
    for k, g, m in todo:
        lab, gloss = labeller(c, k, m)
        seen, held = labeller.view(c, m)
        rows.append((c, k, f"{tag}:{c}:{g}", None if par[k][g] is None else f"{tag}:{c}:{par[k][g]}", m, lab, gloss, seen, held))
    return rows


def null_trees(cfg, params, run_dir, tkh, labeller, cutoffs, levels, R_config, R_labels):
    """{name: rows} for configuration-null rebuilds and random-label trees of the run, labelled by the labeller."""
    out = {}
    raw = json.loads(Path(cfg.graph).read_text())
    rh = real_hubs(tkh, cfg, params)
    for s in range(R_config):
        nt = null_tkh(raw, cfg.articles, cfg.cutoffs, s)[0]
        built = build_concept(nt, cfg.cutoffs, cfg.budgets, params, rh)
        rows = []
        for c in cutoffs:
            snap = snapshot(tkh, c)
            rows += _labelled(labeller, c, _full_levels(tkh, snap, built[c][0]), levels, f"cfg{s}")
        out[f"configuration_null_{s}"] = rows
    for s in range(R_labels):
        rows = []
        for c in cutoffs:
            snap = snapshot(tkh, c)
            concept = set(concept_nodes(tkh, snap))
            h = json.loads((Path(run_dir) / str(c) / "hierarchy.json").read_text())
            K = h["levels"]
            lv = [{x["id"]: set(x["member_ids"]) & concept for x in h["supernodes"] if x["level"] == k} for k in range(K)]
            perm = label_permutation(tkh, snap, cfg.cutoffs, 1000 + s)
            permuted = [{g: {perm.get(v, v) for v in m} for g, m in l.items()} for l in lv]
            rows += _labelled(labeller, c, _full_levels(tkh, snap, permuted), levels, f"rl{s}")
        out[f"random_labels_{s}"] = rows
    return out


# ---------------------------------------------------------------- scoring

MEMBER_CLAIM = 'The group has a member named "{}".'
CONCEPT_LINE = re.compile(r"^(.*?) \[(method|task|problem|technique|component|dataset|metric)\]")


def _names(lines):
    return [m.group(1) for m in map(CONCEPT_LINE.match, lines) if m]


def judge_trees(trees, judge, checker, rigor, seed=0):
    """Decompose, entail and control every tree's labels; returns per-tree summaries and the judgement records.

    Known-answer controls (judged like label claims, against the same held-out lines):
      true    MEMBER_CLAIM with a held-out member's name                       (should be supported)
      false   MEMBER_CLAIM with a concept of another super-node of the level that appears nowhere in this super-node's
              evidence                                                        (should be unsupported)
      cross   the label's own first claim against ANOTHER super-node's held-out lines (should be unsupported: a
              specific label does not fit other groups; guards against vague labels lowering the over-claim rate)
      sibling a sibling's first claim (diagnostic only: siblings share a field, so it is not a reliable false)
    Se = P(unsupported | false), Sp = P(supported | true), J = Se + Sp - 1 (gate J >= J_MIN)."""
    rng = random.Random(seed)
    r = RIGOR[rigor]
    allrows = [(t, row) for t, rows in trees.items() for row in rows]
    decs = judge.decompose_many([(row[5], row[6]) for _, row in allrows], r["max_claims"])
    claims_of = {(t, row[2]): d for (t, row), d in zip(allrows, decs)}
    jobs, meta = [], []
    for (t, row), (claims, ok) in zip(allrows, decs):
        c, k, key, parent, members, lab, gloss, seen, held = row
        if not held:
            continue
        for cl in claims:
            jobs.append((c, cl, held)); meta.append((t, key, "label", cl))
        same = [x for x in trees[t] if x[0] == c and x[1] == k and x[2] != key]
        text = " ".join(seen + held).lower()
        own = set(_names(seen + held))
        true = sorted(set(_names(held)))
        false = sorted({n for x in same for n in _names(x[7] + x[8]) if n not in own and n.lower() not in text})
        for n in rng.sample(true, min(r["n_names"], len(true))):
            jobs.append((c, MEMBER_CLAIM.format(n), held)); meta.append((t, key, "true", None))
        for n in rng.sample(false, min(r["n_names"], len(false))):
            jobs.append((c, MEMBER_CLAIM.format(n), held)); meta.append((t, key, "false", None))
        if same:
            other = rng.choice(same)
            if other[8]:
                jobs.append((c, claims[0], other[8])); meta.append((t, key, "cross", None))
            sib = [x for x in same if x[3] == parent and parent is not None] or same
            jobs.append((c, claims_of[(t, rng.choice(sib)[2])][0][0], held)); meta.append((t, key, "sibling", None))
    verdicts = judge.entail_many(jobs)
    recs = [{"tree": t, "supernode": key, "kind": kind, "claim": cl or jobs[i][1], **v}
            for i, ((t, key, kind, cl), v) in enumerate(zip(meta, verdicts))]
    summary = {}
    for t in trees:
        R = [x for x in recs if x["tree"] == t]
        per = {}
        for x in R:
            if x["kind"] == "label":
                per.setdefault(x["supernode"], []).append(not x["supported"])
        over = np.array([any(v) for v in per.values()], float)
        nclaims = np.array([len(v) for v in per.values()])
        u_obs = float(np.mean([u for v in per.values() for u in v])) if per else math.nan
        se = _rate([not x["supported"] for x in R if x["kind"] == "false"])
        sp = _rate([x["supported"] for x in R if x["kind"] == "true"])
        J = se + sp - 1 if np.isfinite(se) and np.isfinite(sp) else math.nan
        corrected = None
        if np.isfinite(J) and J >= J_MIN:
            u = min(1.0, max(0.0, (u_obs + sp - 1) / J))
            corrected = float(np.mean(1 - (1 - u) ** nclaims))
        det = [checker.checks(f"{row[5]} {row[6]}", row[4], row[0]) for row in trees[t]]
        summary[t] = {"labels": len(trees[t]), "judged": len(per), "over_claim": _ci(over), "claim_unsupported": u_obs,
                      "Se": se, "Sp": sp, "J": J, "valid": bool(np.isfinite(J) and J >= J_MIN), "corrected_over_claim": corrected,
                      "cross_support": _rate([x["supported"] for x in R if x["kind"] == "cross"]),
                      "sibling_support": _rate([x["supported"] for x in R if x["kind"] == "sibling"]),
                      "decomposition_ok": float(np.mean([claims_of[(t, row[2])][1] for row in trees[t]])),
                      "quote_rejected": int(sum(x["verdict"] == "supported" and not x["quote_ok"] for x in R)),
                      "no_held_out": sum(1 for row in trees[t] if not row[8]),
                      "deterministic": {k: int(sum(bool(d[k]) for d in det)) for k in ("year_after_cutoff", "named_non_member", "future_entity")},
                      "_over": {key: bool(any(v)) for key, v in per.items()}}
    return summary, recs


def paired(recs_a, recs_b, tree="model", B=2000, seed=0):
    """Paired bootstrap over super-nodes of b - a: over-claim rate, J (Se + Sp - 1) and cross-support rate."""
    def per_node(recs):
        out = {}
        for x in recs:
            if x["tree"] == tree:
                out.setdefault(x["supernode"], []).append(x)
        return out
    A, Bn = per_node(recs_a), per_node(recs_b)
    keys = sorted(set(A) & set(Bn))
    def stats(d, ks):
        R = [x for k in ks for x in d[k]]
        over = np.mean([any(not x["supported"] for x in d[k] if x["kind"] == "label") for k in ks])
        se = _rate([not x["supported"] for x in R if x["kind"] == "false"])
        sp = _rate([x["supported"] for x in R if x["kind"] == "true"])
        return np.array([over, se + sp - 1, _rate([x["supported"] for x in R if x["kind"] == "cross"])])
    rng = np.random.default_rng(seed)
    obs = stats(Bn, keys) - stats(A, keys)
    boot = np.array([stats(Bn, s) - stats(A, s) for s in ([keys[i] for i in rng.integers(0, len(keys), len(keys))] for _ in range(B))])
    names = ("over_claim", "J", "cross_support")
    return {"n": len(keys), **{n: {"a": float(stats(A, keys)[i]), "b": float(stats(Bn, keys)[i]), "delta": float(obs[i]),
                                    "ci95": [float(np.nanpercentile(boot[:, i], 2.5)), float(np.nanpercentile(boot[:, i], 97.5))]}
                               for i, n in enumerate(names)}}


def _rate(xs):
    return float(np.mean(xs)) if xs else math.nan


def _ci(x, B=2000, seed=0):
    if not len(x):
        return {"value": None, "ci95": [None, None], "n": 0}
    rng = np.random.default_rng(seed)
    b = [x[rng.integers(0, len(x), len(x))].mean() for _ in range(B)]
    return {"value": float(x.mean()), "ci95": [float(np.percentile(b, 2.5)), float(np.percentile(b, 97.5))], "n": len(x)}


def _diff(a, b, B=2000, seed=0):
    a, b = np.asarray(a, float), np.asarray(b, float)
    if not len(a) or not len(b):
        return None
    rng = np.random.default_rng(seed)
    d = [a[rng.integers(0, len(a), len(a))].mean() - b[rng.integers(0, len(b), len(b))].mean() for _ in range(B)]
    return {"value": float(a.mean() - b.mean()), "ci95": [float(np.percentile(d, 2.5)), float(np.percentile(d, 97.5))]}


def label_check(cfg, params, run_dir, rigor="standard", cutoffs=None, levels=None, nulls=True, relabel=False):
    """cutoffs / levels override the rigor's model (and null) selection; relabel: label the run's tree again with the
    current labeller prompt instead of reading the labels of hierarchy.json (for prompt iteration)."""
    r = RIGOR[rigor]
    tkh = load(cfg)
    cs = sorted(cfg.cutoffs)
    pick = lambda w: cutoffs or (cs if w == "all" else cs[-1:])  # noqa: E731
    levels = [k for k in (levels or r["levels"]) if k in LABELLED_LEVELS]
    labeller, judge = LLMLabeller(tkh, cfg), Judge(cfg)
    rows = _run_tree(run_dir, pick(r["model_cutoffs"]), levels)
    if relabel:
        labeller.llm.complete_many([labeller.prompt(x[0], labeller.view(x[0], x[4])[0]) for x in rows], labeller.s["workers"])
        rows = [(*x[:5], *labeller(x[0], x[1], x[4]), *labeller.view(x[0], x[4])) for x in rows]
    trees = {"model": rows}
    if nulls:
        trees.update(null_trees(cfg, params, run_dir, tkh, labeller, pick(r["null_cutoffs"]), levels, r["R_config"], r["R_labels"]))
    summary, recs = judge_trees(trees, judge, NameChecker(tkh), rigor)
    nc = set(pick(r["null_cutoffs"]))
    cut = {row[2]: row[0] for row in trees["model"]}
    m_over = [o for key, o in summary["model"]["_over"].items() if cut[key] in nc]   # model on the nulls' cutoffs
    pooled = {kind: [o for t, sm in summary.items() if t.startswith(kind) for o in sm["_over"].values()]
              for kind in ("configuration_null", "random_labels")}
    out = {"rigor": rigor, "protocol": r, "labeller_model": labeller.s["labeller_model"], "judge_model": judge.s["judge_model"],
           "j_min": J_MIN, "trees": {t: {k: v for k, v in sm.items() if k != "_over"} for t, sm in summary.items()},
           "model_on_null_cutoffs": _ci(np.array(m_over, float)),
           "nulls": {kind: {"over_claim": _ci(np.array(v, float)), "model_minus_null": _diff(m_over, v)} for kind, v in pooled.items() if v}}
    return _finite(out), recs
