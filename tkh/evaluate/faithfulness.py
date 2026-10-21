"""Label faithfulness: rates each label/gloss against its super-node's members and reports the over-claim rate with intervals.

E3. A judge model from a different open family (config [labels] judge_model) rates every
level-0/1 label and gloss as accurate / vague / wrong:
- primary pass ("held_out"): evidence the labeller did not see, namely the held-out half
  of the members (tkh/label.split_members), plus claim sentences and titles of the
  snapshot papers those members come from. This removes the circularity of judging a
  label against the very list it was written from;
- second pass ("full", primary snapshot only): all members and their papers; the gap to
  the held-out pass is reported;
- negative control ("swapped"): each label judged against the held-out evidence of
  another super-node of the same level (a derangement). A judge that cannot tell labels
  apart rates these accurate too, so its 'wrong' share bounds what the primary rate means.
Over-claim rate = share rated 'wrong' (always reported with the 'vague' share), with
Wilson 95% intervals.

Deterministic checks, independent of any model (`deterministic_checks`):
- a year after the cutoff in the label or gloss;
- a named non-member: a method/dataset name of the graph (whole-word, >= 4 characters)
  that is not a member of the super-node;
- a named entity whose entry year is after the cutoff (future leakage).
"""

import random
import re

from tkh.evaluate.stats import wilson
from tkh.label import Evidence, _mode, split_members

RATINGS = ("accurate", "vague", "wrong")
NAMED_TYPES = ("method", "dataset")


def derangement(n, seed=0):
    """A permutation of range(n) with no fixed point (n >= 2), deterministic per seed."""
    rng = random.Random(seed)
    while True:
        p = list(range(n))
        rng.shuffle(p)
        if all(i != j for i, j in enumerate(p)):
            return p


class Judge:
    def __init__(self, tkh, cfg, llm=None):
        from tkh.llm import CachedLLM
        self.cfg, self.ev, self.tkh = cfg, Evidence(tkh, cfg), tkh
        lab = cfg.labels
        self.llm = llm or CachedLLM(lab["judge_model"], lab["cache"], lab.get("endpoint", "http://localhost:11434"), _mode(cfg))

    def pack(self, cutoff, members, kind):
        concept = self.ev.concept(members)
        seen, held = split_members(concept, int(self.cfg.labels.get("seed", 0)))
        nodes = concept if kind == "full" else (held or seen)  # a 1-member super-node has no held-out half
        lines, _ = self.ev.member_lines(cutoff, nodes)
        claims, titles = self.ev.paper_texts(cutoff, nodes)
        return {"members": "\n".join(lines) or "(none)", "claims": "\n".join(f"- {c}" for c in claims) or "(none)",
                "titles": "\n".join(f"- {t}" for t in titles) or "(none)"}

    def rate(self, cutoff, label, gloss, pack):
        from tkh.llm import render
        prompt = render(self.cfg.labels["judge_prompt"], cutoff=cutoff, label=label, gloss=gloss, **pack)
        resp = self.llm.complete(prompt)
        r = str(resp.get("rating", "")).strip().lower() if isinstance(resp, dict) else ""
        return (r if r in RATINGS else "unparsed"), (resp.get("reason") if isinstance(resp, dict) else None)


class NameChecker:
    def __init__(self, tkh):
        n = tkh.nodes
        self.entry = n["entry_year"].to_dict()
        self.pats = []
        for v, sf, al, t in zip(n.index, n["surface_form"], n["aliases"] if "aliases" in n else [None] * len(n), n["type"]):
            if t not in NAMED_TYPES:
                continue
            for s in [sf, *(al if isinstance(al, list) else [])]:
                s = str(s).strip()
                if len(s) >= 4:
                    self.pats.append((v, re.compile(r"(?<![\w-])" + re.escape(s) + r"(?![\w-])")))

    def named(self, text):
        return {v for v, p in self.pats if p.search(text)}


def deterministic_checks(text, members, cutoff, checker):
    years = [int(y) for y in re.findall(r"(?<!\d)(19\d\d|20\d\d)(?!\d)", text)]
    named = checker.named(text)
    mem = set(members)
    return {"year_after_cutoff": any(y > cutoff for y in years),
            "named_non_member": sorted(named - mem),
            "future_entity": sorted(v for v in named if checker.entry.get(v, 0) > cutoff)}


def summarise(ratings):
    """Shares of accurate / vague / wrong (and unparsed) with Wilson intervals."""
    n = len(ratings)
    out = {"n": n}
    for r in (*RATINGS, "unparsed"):
        k = sum(x == r for x in ratings)
        lo, hi = wilson(k, n)
        out[r] = {"k": k, "share": k / n if n else None, "lo": lo, "hi": hi}
    return out


def evaluate_labels(tkh, cfg, hierarchies, judge, passes=("held_out",), swapped=False, seed=0):
    """Rows per labelled super-node and pass. hierarchies: {cutoff: hierarchy dict}."""
    checker = NameChecker(tkh)
    rows = []
    for c, h in sorted(hierarchies.items()):
        sns = [s for s in h["supernodes"] if s["level"] in (0, 1) and s.get("label")]
        for s in sns:
            text = f"{s['label']}. {s['gloss'] or ''}"
            det = deterministic_checks(text, s["member_ids"], c, checker)
            for kind in passes:
                r, why = judge.rate(c, s["label"], s["gloss"] or "", judge.pack(c, s["member_ids"], kind))
                rows.append({"snapshot": c, "level": s["level"], "id": s["id"], "pass": kind, "rating": r, "reason": why,
                             "label": s["label"], **{f"det_{k}": (bool(v) if isinstance(v, list) else v) for k, v in det.items()},
                             "det_named_non_member_ids": det["named_non_member"]})
        if swapped:
            for k in (0, 1):
                lv = [s for s in sns if s["level"] == k]
                if len(lv) < 2:
                    continue
                perm = derangement(len(lv), seed + 1000 * k + c)
                for s, j in zip(lv, perm):
                    other = lv[j]
                    r, why = judge.rate(c, s["label"], s["gloss"] or "", judge.pack(c, other["member_ids"], "held_out"))
                    rows.append({"snapshot": c, "level": k, "id": s["id"], "pass": "swapped", "rating": r, "reason": why,
                                 "label": s["label"], "evidence_of": other["id"]})
    return rows
