"""Snapshot-restricted evidence texts about a super-node (member lines, claim sentences, titles).

Owned by the evaluator: the judge builds its held-out evidence pack from it, and a labeller under evaluation may
use it to build its own (seen-half) input. Independent of any coarsening code.
"""

from collections import Counter

from tkh.evalkit.split import split_members
from tkh.io import snapshot
from tkh.structure import CONCEPT_TYPES, node_papers


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
