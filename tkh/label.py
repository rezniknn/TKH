"""T5: a label and one-sentence gloss per super-node at levels 0-1, written by an open-source LLM from half of its evidence.

Evidence of a super-node (`evidence`) is a list of text lines, all from its snapshot (P6 cutoff):
  concept   member concepts, "name [type]" (with aliases)
  fact      each incident clustering edge: "<method> <relation> <members in the super-node>"; evaluated_on edges
            add their result attributes (metric, value, task, split)
  claim     member claim nodes, "claim: <sentence>"
  future    member future-topic nodes, "future work: <topic>"
  paper     member article nodes, "paper: <title>"
Cited works and citations are left out (they are the P3 coherence ruler); authors carry no meaning.

The evidence is split 50/50 (`split_evidence`): seeded by the super-node's members, stratified by kind. The labeller
sees only the seen half; the held-out half is reserved for the faithfulness judge (eval/labels.py), which breaks the
circularity of judging a label on its own input. Each half is capped at max_items lines, ranked by how many snapshot
papers mention the node (or how many super-node members an edge holds). The exact input is recorded per super-node
(label_inputs.json, written by tkh/pipeline.py).

`placeholder_labeller` is a deterministic stand-in (labeller = "placeholder", the default when no [labels] is set).
"""

from collections import Counter
import hashlib
import math
import random

from tkh import semantic as sm
from tkh.coarsen import CLUSTER_RELATIONS, node_papers
from tkh.io import snapshot
from tkh.llm import CachedLLM, render
from tkh.config import REPO_ROOT
from tkh.semantic import CONCEPT_TYPES

LABELLED_LEVELS = (0, 1)
LABEL_DEFAULTS = {"labeller": "placeholder", "labeller_model": "qwen2.5:7b-instruct", "judge_model": "phi4",
                  "endpoint": "http://localhost:11434", "cache": str(REPO_ROOT / "data" / "llm_cache.json"),
                  "prompts": str(REPO_ROOT / "configs" / "prompts"), "mode": "offline", "seed": 0, "max_items": 40,
                  "workers": 4}
KINDS = ("concept", "fact", "claim", "future", "paper")
PHRASE = {"addresses": "addresses", "solves": "solves", "extends": "extends", "uses_component": "uses component",
          "uses_technique": "uses technique", "evaluated_on": "is evaluated on"}


def settings(cfg):
    return {**LABEL_DEFAULTS, **(getattr(cfg, "labels", None) or {})}


class Evidence:
    """Evidence lines of super-nodes, per snapshot (cached)."""

    def __init__(self, tkh):
        self.tkh = tkh
        n = tkh.nodes
        self.type = n["type"].to_dict()
        self.name = {v: sm.clean(s) for v, s in n["surface_form"].items()}
        al = n["aliases"] if "aliases" in n else None
        self.alias = {v: [sm.clean(a) for a in x] for v, x in (al.items() if al is not None else []) if isinstance(x, list) and x}
        self._snap = {}

    def _snapshot(self, cutoff):
        if cutoff not in self._snap:
            snap = snapshot(self.tkh, cutoff)
            papers = {v: len(p) for v, p in node_papers(self.tkh, snap).items()}
            e = snap.edges[snap.edges["relation_type"].isin(CLUSTER_RELATIONS)]
            incident = {}
            for eid, m in zip(e.index, e["members"]):
                for v in m:
                    incident.setdefault(v, []).append(eid)
            self._snap[cutoff] = (papers, e, incident)
        return self._snap[cutoff]

    def items(self, cutoff, members):
        """[(kind, text, weight)] for one super-node."""
        papers, e, incident = self._snapshot(cutoff)
        mem = set(members)
        out = []
        for v in sorted(mem):
            t = self.type[v]
            if t in CONCEPT_TYPES:
                al = self.alias.get(v)
                out.append(("concept", f"{self.name[v]} [{t}]" + (f" (also: {', '.join(al)})" if al else ""), papers.get(v, 0)))
            elif t == "claim":
                out.append(("claim", f"claim: {self.name[v]}", papers.get(v, 0)))
            elif t == "future_topic":
                out.append(("future", f"future work: {self.name[v]}", papers.get(v, 0)))
            elif t == "article":
                out.append(("paper", f"paper: {self.name[v]}", papers.get(v, 0)))
        for eid in sorted({x for v in mem for x in incident.get(v, ())}):
            m, r = e.at[eid, "members"], e.at[eid, "relation_type"]
            inside = [self.name[v] for v in m[1:] if v in mem]
            if not inside:   # only facts about this super-node's members
                continue
            text = f"{self.name[m[0]]} {PHRASE[r]} {', '.join(inside[:8])}"
            attrs = e.at[eid, "attributes"] if "attributes" in e else None
            if r == "evaluated_on" and isinstance(attrs, dict):
                res = ", ".join(f"{k} {attrs[k]}" for k in ("metric", "value", "task", "split") if attrs.get(k) not in (None, ""))
                text += f" ({res})" if res else ""
            out.append(("fact", text, len(inside)))
        return out


def split_evidence(items, members, seed=0, cap=40):
    """Seeded, kind-stratified 50/50 split: (seen, held_out) lists of text lines, each capped at `cap`."""
    h = hashlib.sha256(("|".join(sorted(members)) + f"#{seed}").encode()).hexdigest()
    rng = random.Random(int(h[:16], 16))
    seen, held = [], []
    for kind in KINDS:
        part = sorted((it for it in items if it[0] == kind), key=lambda it: it[1])
        rng.shuffle(part)
        k = math.ceil(len(part) / 2)
        seen += part[:k]
        held += part[k:]
    top = lambda xs: [t for _, t, _ in sorted(dict.fromkeys(xs), key=lambda it: (-it[2], it[1]))[:cap]]  # noqa: E731
    return top(seen), top(held)


class LLMLabeller:
    """label(cutoff, level, members) -> (label, gloss); `inputs` records the exact evidence each label was given."""

    def __init__(self, tkh, cfg, llm=None):
        self.s = settings(cfg)
        self.ev = Evidence(tkh)
        self.llm = llm or CachedLLM(self.s["labeller_model"], self.s["cache"], self.s["endpoint"], self.s["mode"])
        self.template = f"{self.s['prompts']}/labeller.txt"
        self.inputs = {}

    def view(self, cutoff, members):
        return split_evidence(self.ev.items(cutoff, members), members, self.s["seed"], self.s["max_items"])

    def prompt(self, cutoff, seen):
        return render(self.template, cutoff=cutoff, evidence="\n".join(f"- {t}" for t in seen))

    def prefetch(self, parts):
        """Label every level-0/1 super-node of {cutoff: [levels]} in one parallel batch (fills the cache)."""
        prompts = [self.prompt(c, self.view(c, mem)[0]) for c, levels in parts.items()
                   for k, lv in enumerate(levels) if k in LABELLED_LEVELS for mem in lv.values()]
        self.llm.complete_many(prompts, self.s["workers"])

    def __call__(self, cutoff, level, members):
        if level not in LABELLED_LEVELS:
            return None, None
        seen, held = self.view(cutoff, members)
        p = self.prompt(cutoff, seen)
        resp = self.llm.complete(p)
        self.inputs[(cutoff, level, frozenset(members))] = {"seen": seen, "held_out": held,
                                                           "prompt_sha256": hashlib.sha256(p.encode()).hexdigest()}
        return clean_output(resp)


def clean_output(resp):
    lab = resp.get("label") if isinstance(resp, dict) else None
    gloss = resp.get("gloss") if isinstance(resp, dict) else None
    return (" ".join(str(lab).split()) if lab else "[label generation failed]",
            " ".join(str(gloss).split()) if gloss else "[gloss generation failed]")


def make_labeller(tkh, cfg):
    return LLMLabeller(tkh, cfg) if settings(cfg)["labeller"] == "llm" else placeholder_labeller(tkh)


def placeholder_labeller(tkh):
    """Deterministic stand-in: the most common concept type and its members shared by the most snapshot papers."""
    ntype = tkh.nodes["type"].to_dict()
    name = tkh.nodes["surface_form"].to_dict()
    n_papers = {}

    def label(cutoff, level, members):
        if level not in LABELLED_LEVELS:
            return None, None
        if cutoff not in n_papers:
            n_papers[cutoff] = {v: len(p) for v, p in node_papers(tkh, snapshot(tkh, cutoff)).items()}
        concept = [v for v in members if ntype[v] in CONCEPT_TYPES] or list(members)
        types = Counter(ntype[v] for v in concept)
        top = sorted(concept, key=lambda v: (-n_papers[cutoff][v], name[v]))[:2]
        lab = f"[placeholder] {types.most_common(1)[0][0]}: " + "; ".join(name[v][:30] for v in top)
        mix = ", ".join(f"{c} {t}" for t, c in types.most_common(3))
        gloss = f"[placeholder] {len(concept)} concept nodes ({mix}); the label lists the most widely shared members."
        return lab, gloss
    return label
