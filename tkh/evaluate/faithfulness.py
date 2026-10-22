"""Label faithfulness: rates each label/gloss against its super-node's members and reports the over-claim rate with intervals.

E3. Two judge protocols, both with a judge model from a different open family than the
labeller (config [labels] judge_model; robustness judges in configs/eval.toml [e3]).

Forced choice (`forced_choice`; post hoc: it replaced the pre-registered absolute rating
after that failed its control, and its tests are reported outside the Holm family). The judge sees the HELD-OUT
evidence of one super-node and four candidate labels+glosses of the same level and
snapshot: its own and three random others, in a seeded random order. A label is counted
as faithful if the judge picks it. Over-claim rate = 1 - identification rate; chance is
0.25, and chance-corrected identification is (rate - 1/4) / (3/4). Unlike an absolute
rating, this cannot be passed by agreeing with everything. The chosen positions are
reported as a position-bias check.

Absolute rating (the pre-registered instrument, kept as the E3 primary test, but it FAILED its negative control on this data: the 7-9B judges
rated the swapped glosses accurate as often as the true ones, so its over-claim rate is
reported only as a failed instrument). It rates every level-0/1 label and gloss as
accurate / vague / wrong:
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
- a named non-member: a proper-name-like method/dataset name of the graph (it contains a
  token with two or more capitals or a digit, e.g. CHGNet, QM9; dictionary words such as
  the dataset node "Materials" are excluded) that is not a member of the super-node;
- a named entity whose entry year is after the cutoff (future leakage).
"""

import random
import re

from tkh.evaluate.stats import wilson
from tkh.evalkit.evidence import Evidence
from tkh.evalkit.split import split_members
from tkh.llm import mode as _mode

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
        nodes = concept if kind == "full" else held
        lines, _ = self.ev.member_lines(cutoff, nodes) if nodes else ([], [])
        if not nodes:  # single-concept super-node: no held-out member; never show the labeller's own list
            lines = ["(no held-out member: this group has a single concept)"]
        claims, titles = self.ev.paper_texts(cutoff, nodes or seen)
        return {"members": "\n".join(lines), "claims": "\n".join(f"- {c}" for c in claims) or "(none)",
                "titles": "\n".join(f"- {t}" for t in titles) or "(none)"}

    def rate(self, cutoff, label, gloss, pack):
        from tkh.llm import render
        prompt = render(self.cfg.labels["judge_prompt"], cutoff=cutoff, label=label, gloss=gloss, **pack)
        resp = self.llm.complete(prompt)
        r = str(resp.get("rating", "")).strip().lower() if isinstance(resp, dict) else ""
        return (r if r in RATINGS else "unparsed"), (resp.get("reason") if isinstance(resp, dict) else None)


def _proper(name):
    """True if the name contains a token with >= 2 capitals or a digit (acronym / CamelCase / numbered)."""
    return any(sum(ch.isupper() for ch in t) >= 2 or (any(ch.isdigit() for ch in t) and any(ch.isalpha() for ch in t))
               for t in re.findall(r"[\w-]+", name))


class NameChecker:
    """Proper-name-like method/dataset names of the graph, matched whole-word in label text.

    Checks work per NAME, not per node: the graph has duplicate entities and shared aliases
    (e.g. 'CGCNN' enters in 2024 while 'crystal graph convolutional neural networks' enters
    in 2018), so a name is a non-member only if no node carrying it is a member, and a
    future entity only if every node carrying it enters after the cutoff."""

    def __init__(self, tkh):
        n = tkh.nodes
        self.entry = n["entry_year"].to_dict()
        self.nodes_of = {}
        for v, sf, al, t in zip(n.index, n["surface_form"], n["aliases"] if "aliases" in n else [None] * len(n), n["type"]):
            if t not in NAMED_TYPES:
                continue
            for s in [sf, *(al if isinstance(al, list) else [])]:
                s = str(s).strip()
                if len(s) >= 3 and _proper(s):
                    self.nodes_of.setdefault(s, set()).add(v)
        self.pats = [(s, re.compile(r"(?<![\w-])" + re.escape(s) + r"(?![\w-])")) for s in sorted(self.nodes_of)]

    def named(self, text):
        """{matched name: set of nodes carrying it}."""
        return {s: self.nodes_of[s] for s, p in self.pats if p.search(text)}


def deterministic_checks(text, members, cutoff, checker):
    years = [int(y) for y in re.findall(r"(?<!\d)(19\d\d|20\d\d)(?!\d)", text)]
    named = checker.named(text)
    mem = set(members)
    non_member = sorted(s for s, vs in named.items() if not vs & mem)
    future = sorted(s for s, vs in named.items() if all(checker.entry.get(v, 0) > cutoff for v in vs))
    return {"year_after_cutoff": any(y > cutoff for y in years), "named_non_member": non_member, "future_entity": future}


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


LETTERS = "ABCD"


def forced_choice(tkh, cfg, hierarchies, judge, levels=(0, 1), seed=0, tag="model"):
    """Rows per labelled super-node: did the judge pick its label among 4 (own + 3 same-level others)?"""
    from tkh.llm import render
    rows = []
    for c, h in sorted(hierarchies.items()):
        for k in levels:
            lv = sorted((s for s in h["supernodes"] if s["level"] == k and s.get("label")), key=lambda s: s["id"])
            if len(lv) < 4:
                continue
            for i, s in enumerate(lv):
                rng = random.Random(f"{seed}|{c}|{k}|{s['id']}")
                others = rng.sample([o for o in lv if o["id"] != s["id"]], 3)
                pos = rng.randrange(4)
                opts = others[:pos] + [s] + others[pos:]
                text = "\n".join(f"{LETTERS[j]}. {o['label']}: {o['gloss'] or ''}" for j, o in enumerate(opts))
                pk = judge.pack(c, s["member_ids"], "held_out")
                resp = judge.llm.complete(render(cfg.labels["judge_choice_prompt"], cutoff=c, options=text, **pk))
                ch = str(resp.get("choice", "")).strip().upper()[:1] if isinstance(resp, dict) else ""
                rows.append({"snapshot": c, "level": k, "id": s["id"], "variant": tag, "judge": judge.llm.model,
                             "true_pos": LETTERS[pos], "choice": ch if ch in LETTERS else None,
                             "hit": ch == LETTERS[pos], "reason": resp.get("reason") if isinstance(resp, dict) else None})
    return rows
