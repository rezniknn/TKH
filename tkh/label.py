"""T5: generates a label and one-sentence gloss per super-node at levels 0-1. Records the exact labeller input and keeps evidence within the snapshot cutoff (P6).

`LLMLabeller` (the shipped labeller) asks an open model through a local Ollama server
(tkh/llm.py; model, endpoint and prompt template from the config's [labels] section; the
committed response cache makes the run reproducible offline).

Evidence (P6 and the circularity control of E3):
- a super-node's concept members are split in two halves by a seeded hash of the
  super-node's member set (`split_members`); the labeller sees only the SEEN half, the
  judge's primary evidence is the HELD-OUT half (tkh/evaluate/faithfulness.py);
- at most `max_members` members are shown, highest snapshot paper count first, as
  "name [type]"; names are snapshot nodes, so nothing after the cutoff is shown;
- the prompt states the cutoff year and forbids dates and unlisted entities.
`evidence(cutoff, level, members)` returns exactly what the labeller saw; build.py writes
it to out/<cutoff>/label_inputs.json.

`placeholder_labeller` is a deterministic stand-in for tests: it only restates the
super-node's composition, so it cannot over-claim. Levels >= 2 carry no label.
"""

from collections import Counter
import hashlib
import os
import random

from tkh.coarsen import node_papers
from tkh.io import snapshot
from tkh.semantic import CONCEPT_TYPES

LABELLED_LEVELS = (0, 1)


def placeholder_labeller(tkh):
    ntype = tkh.nodes["type"].to_dict()
    name = tkh.nodes["surface_form"].to_dict()
    n_papers = tkh.nodes["prov_articles"].map(len).to_dict()

    def label(cutoff, level, members):
        if level not in LABELLED_LEVELS:
            return None, None
        concept = [v for v in members if ntype[v] in CONCEPT_TYPES] or list(members)
        types = Counter(ntype[v] for v in concept)
        top = sorted(concept, key=lambda v: (-n_papers[v], name[v]))[:2]
        lab = f"[placeholder] {types.most_common(1)[0][0]}: " + "; ".join(name[v][:30] for v in top)
        mix = ", ".join(f"{c} {t}" for t, c in types.most_common(3))
        gloss = f"[placeholder] {len(concept)} concept nodes ({mix}); the label lists the most widely shared members."
        return lab, gloss
    return label


def split_members(members, seed=0):
    """(seen, held_out): a deterministic half split of the sorted members, seeded by the member set."""
    ms = sorted(members)
    h = hashlib.sha256(("|".join(ms) + f"#{seed}").encode()).hexdigest()
    rng = random.Random(int(h[:16], 16))
    rng.shuffle(ms)
    k = (len(ms) + 1) // 2
    return sorted(ms[:k]), sorted(ms[k:])


class Evidence:
    """Snapshot-restricted texts for labeller and judge prompts."""

    def __init__(self, tkh, cfg):
        self.tkh = tkh
        self.lab = cfg.labels
        self.ntype = tkh.nodes["type"].to_dict()
        self.name = tkh.nodes["surface_form"].to_dict()
        self._papers = {}

    def papers(self, cutoff):
        if cutoff not in self._papers:
            self._papers[cutoff] = node_papers(self.tkh, snapshot(self.tkh, cutoff))
        return self._papers[cutoff]

    def concept(self, members):
        return [v for v in members if self.ntype[v] in CONCEPT_TYPES]

    def member_lines(self, cutoff, nodes, cap=None):
        cap = cap or int(self.lab.get("max_members", 40))
        pp = self.papers(cutoff)
        top = sorted(nodes, key=lambda v: (-len(pp.get(v, ())), self.name[v], v))[:cap]
        return [f"- {self.name[v]} [{self.ntype[v]}]" for v in top], top

    def labeller_view(self, cutoff, level, members):
        seen, held = split_members(self.concept(members), int(self.lab.get("seed", 0)))
        lines, shown = self.member_lines(cutoff, seen)
        return {"cutoff": cutoff, "level": level, "seen": seen, "held_out": held, "shown": shown, "lines": lines}

    def paper_texts(self, cutoff, nodes, max_claims=None):
        """Claim sentences and titles of the snapshot papers the nodes come from (most members first)."""
        max_claims = max_claims or int(self.lab.get("max_claims", 12))
        pp = self.papers(cutoff)
        cnt = Counter(a for v in nodes for a in pp.get(v, ()))
        arts = self.tkh.articles
        papers = [a for a, _ in sorted(cnt.items(), key=lambda kv: (-kv[1], str(kv[0]))) if arts.at[a, "year"] <= cutoff]
        e = self.tkh.edges
        cl = e[(e["relation_type"] == "claims") & (e["article_year"] <= cutoff)]
        by_paper = {}
        for m, a in zip(cl["members"], cl["article_id"]):
            by_paper.setdefault(a, []).extend(v for v in m if self.ntype[v] == "claim")
        claims = []
        for a in papers:  # round-robin over papers so one paper does not fill the budget
            claims.append(sorted(by_paper.get(a, [])))
        flat = []
        while len(flat) < max_claims and any(claims):
            for lst in claims:
                if lst and len(flat) < max_claims:
                    flat.append(self.name[lst.pop(0)])
        titles = [str(arts.at[a, "title"]) for a in papers[:10] if "title" in arts and isinstance(arts.at[a, "title"], str)]
        return flat, titles


def _mode(cfg):
    return os.environ.get("TKH_LLM_MODE") or cfg.labels.get("mode", "offline")


class LLMLabeller:
    """labeller(cutoff, level, members) -> (label, gloss) for levels 0-1, (None, None) otherwise."""

    def __init__(self, tkh, cfg, llm=None):
        from tkh.llm import CachedLLM
        self.cfg, self.ev = cfg, Evidence(tkh, cfg)
        lab = cfg.labels
        self.llm = llm or CachedLLM(lab["labeller_model"], lab["cache"], lab.get("endpoint", "http://localhost:11434"), _mode(cfg))
        self.inputs = {}

    def prompt(self, view):
        from tkh.llm import render
        return render(self.cfg.labels["labeller_prompt"], cutoff=view["cutoff"], members="\n".join(view["lines"]))

    def __call__(self, cutoff, level, members):
        if level not in LABELLED_LEVELS:
            return None, None
        view = self.ev.labeller_view(cutoff, level, members)
        resp = self.llm.complete(self.prompt(view))
        label, gloss = clean_output(resp)
        self.inputs[(cutoff, level, tuple(sorted(members)))] = {"shown": view["shown"], "held_out": view["held_out"],
                                                               "prompt_key": self.llm.key(self.prompt(view))}
        return label, gloss


def clean_output(resp):
    """(label, gloss) from a model's JSON answer; unparseable answers become explicit failures."""
    label = resp.get("label") if isinstance(resp, dict) else None
    gloss = resp.get("gloss") if isinstance(resp, dict) else None
    label = " ".join(str(label).split()) if label else "[label generation failed]"
    gloss = " ".join(str(gloss).split()) if gloss else "[gloss generation failed]"
    return label, gloss
