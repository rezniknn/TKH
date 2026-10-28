"""T6 extrinsic utility: a retrieval agent that starts at the coarsest level of a snapshot's hierarchy and drills down
to the leaf nodes that answer a question, and the flat baseline that ranks every leaf directly.

Agent(tkh, run_dir, cutoffs).answer(question, qtype, mode="hier" | "flat") -> answer dict (ground-truth format)
  1. snapshot  `choose_snapshot`: the latest cutoff <= the year the question names ("by Feb 2026" -> 2026); no date ->
               the latest cutoff; a date before the first cutoff -> no admissible snapshot, the agent abstains. Only
               that snapshot's nodes, edges and hierarchy are used (P6).
  2. content   each leaf's text is its name and aliases, the names of its relation neighbours over the clustering
               relations and its evaluated_on attributes (metric, task), all from edges <= cutoff, plus the title of the
               article that presents it (methods, once) or makes it (claims), and for a presented method its paper's
               claims. Super-nodes: label + gloss (L0-L1) and the member centroid.
  3. score     keyword overlap: the share of the question's keywords (template words and English stop words removed,
               in the snapshot's leaf vocabulary) that a text contains; texts are binary keyword vectors.
  4. descent   L0-L1 super-nodes score 0.5 s(q, label + gloss) + 0.5 s(q, centroid); L2 (unlabelled) the centroid.
               Beam search keeps the best BEAM[k] super-nodes per level (10 / 20 / 40) among the children of the
               previous level's kept nodes; the leaves of the kept L2 nodes of the answer kinds form the pool, ranked
               by s(q, leaf). The trace records every super-node scored and which were kept.
  5. flat      the same scorer and answer kinds over every leaf of the snapshot.
  6. answer    the ground-truth format with K items, plus the node and article ids it was read from:
               A: expected_methods (distinct names), method_claims / method_evidence per method (up to 3 graph claims
               on its claims edges), required_citations; B: as_of, required_claims, sources, required_citations.
The question type is given by the question's metadata (data/questions.csv); the agent never sees ground truth.
"""

from collections import defaultdict
from pathlib import Path
import json
import re
import unicodedata

import numpy as np
import scipy.sparse as sp
from sklearn.feature_extraction.text import CountVectorizer

from tkh import semantic as sm
from tkh.coarsen import CLUSTER_RELATIONS
from tkh.io import snapshot

KINDS = {"A": ("method", "technique", "component", "dataset"),   # GT expected_methods also lists datasets (Q14)
         "B": ("claim",)}
MONTHS = "jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec"
DATE = re.compile(rf"\b(?:by|as of|before|until|up to)\s+(?:(?:{MONTHS})[a-z]*\.?\s+)?((?:19|20)\d\d)\b", re.I)
TEMPLATE = re.compile(r"\((?:by|as of)[^)]*\)|\b(?:which|what|are|is|the|methods?|best|suited|leading|most|"
                      r"important|commonly|used|give|evidences?|when|for|of|by|feb|\d{4})\b", re.I)
BEAM = (10, 20, 40)   # super-nodes kept per level, L0 first
K = 10                # answer length (methods or claims)
CLAIMS_PER_METHOD = 3


def choose_snapshot(question, cutoffs):
    """(cutoff or None, stated year or None, source): the latest cutoff <= the stated year; no date -> the latest."""
    m = DATE.search(question)
    if not m:
        return max(cutoffs), None, "default_latest"
    year = int(m.group(1))
    ok = [c for c in sorted(cutoffs) if c <= year]
    return (ok[-1], year, "stated") if ok else (None, year, "before_first_cutoff")


def fold(s):
    """Lower case without diacritics (Schütt -> schutt)."""
    return "".join(ch for ch in unicodedata.normalize("NFKD", str(s)) if not unicodedata.combining(ch)).lower()


class Facts:
    """One snapshot's graph facts (no hierarchy, no text model), shared by the agent and the evaluator."""

    def __init__(self, tkh, cutoff):
        s = snapshot(tkh, cutoff)
        self.cutoff, self.snap = cutoff, s
        self.ids = sorted(s.node_ids)
        self.type = tkh.nodes["type"].to_dict()
        self.name = {v: sm.clean(x) for v, x in tkh.nodes["surface_form"].items()}
        self.keys = sm.name_keys(tkh)
        prov = tkh.nodes["prov_articles"].to_dict()
        self.articles_of = {v: [a for a in prov[v] if a in s.articles] for v in self.ids}
        arts = tkh.articles
        self.year = {a: int(y) for a, y in arts["year"].items() if a in s.articles}
        self.title = {a: sm.clean(t) for a, t in arts["title"].items() if a in s.articles and isinstance(t, str)}
        node_of = arts["node_id"].to_dict()
        self.doi = {a: str((tkh.nodes.at[node_of[a], "provenance"] or {}).get("doi") or "").lower()
                    for a in s.articles if isinstance(node_of.get(a), str)}
        self.authors, self.presents, self.claims_of = defaultdict(list), defaultdict(list), defaultdict(list)
        self.method_claims = defaultdict(set)          # node -> claim nodes on the same claims edge
        for m, r, a in zip(s.edges["members"], s.edges["relation_type"], s.edges["article_id"]):
            if r == "authored_by":
                self.authors[a] += [self.name[v] for v in m[1:]]
            elif r == "presents":
                self.presents[a] += m[1:]
            elif r == "claims":
                cl = [v for v in m[1:] if self.type[v] == "claim"]
                self.claims_of[a] += cl
                for v in m[1:]:
                    if self.type[v] != "claim":
                        self.method_claims[v].update(cl)

    def citation(self, a):
        """'Surname et al. YYYY' (author order is not recorded in the export: the first listed author is used)."""
        sur = [sm.clean(n).split(" ")[-1] for n in self.authors.get(a, [])]
        who = sur[0] if len(sur) == 1 else f"{sur[0]} & {sur[1]}" if len(sur) == 2 else f"{sur[0]} et al." if sur else "Anon."
        return f"{who} {self.year[a]}"


def leaf_texts(tkh, F):
    """{node id: text} from the snapshot's own edges only (tkh.semantic.attached_text reads all edges)."""
    name, title = sm.names(tkh), tkh.articles["title"].to_dict()
    e = F.snap.edges
    txt = {v: [name[v]] for v in F.ids}
    attrs = e["attributes"] if "attributes" in e else [None] * len(e)
    presented = {}
    for m, r, a, at in zip(e["members"], e["relation_type"], e["article_id"], attrs):
        if r in CLUSTER_RELATIONS:
            txt[m[0]] += [name[t] for t in m[1:]]
            for t in m[1:]:
                txt[t].append(name[m[0]])
            if r == "evaluated_on" and isinstance(at, dict):
                for v in m:
                    txt[v].append(" ".join(str(at[k]) for k in ("metric", "task") if at.get(k)))
        elif r == "presents" and isinstance(title.get(a), str):
            txt[m[1]].append(sm.clean(title[a]))             # once per presented method
            presented[a] = m[1]
        elif r == "claims" and isinstance(title.get(a), str):
            for v in m[1:]:
                if F.type[v] == "claim":
                    txt[v].append(sm.clean(title[a]))
    for a, v in presented.items():                           # a presented method: its paper's claims
        txt[v] += [F.name[c] for c in F.claims_of[a]]
    return {v: " . ".join(x) for v, x in txt.items()}


def binary(C):
    C = sp.csr_matrix(C, dtype=float)
    C.data[:] = 1.0
    return C


def tree(run_dir, cutoff):
    """({super-node id: super-node}, {id: [child ids]}) of out/<cutoff>/hierarchy.json."""
    h = json.loads((Path(run_dir) / str(cutoff) / "hierarchy.json").read_text())
    sn = {s["id"]: s for s in h["supernodes"]}
    children = defaultdict(list)
    for s in h["supernodes"]:
        if s["parent_id"] is not None:
            children[s["parent_id"]].append(s["id"])
    return sn, children


class Index:
    """One snapshot's search index: binary leaf keyword vectors, super-node label and centroid vectors, the tree."""

    def __init__(self, tkh, run_dir, cutoff):
        self.F = Facts(tkh, cutoff)
        self.sn, self.children = tree(run_dir, cutoff)
        self.roots = [i for i, s in self.sn.items() if s["level"] == 0]
        finest = max(s["level"] for s in self.sn.values())
        self.depth = finest + 1
        self.leaves = sorted({v for s in self.sn.values() if s["level"] == finest for v in s["member_ids"]})
        texts = leaf_texts(tkh, self.F)
        self.vec = CountVectorizer(lowercase=True, stop_words="english", token_pattern=r"(?u)\b[\w][\w\-\+]*\b")
        self.X = binary(self.vec.fit_transform([texts[v] for v in self.leaves]))
        self.row = {v: i for i, v in enumerate(self.leaves)}
        self.centroid = {i: np.asarray(self.X[[self.row[v] for v in s["member_ids"]]].mean(axis=0))[0]
                         for i, s in self.sn.items()}     # share of members containing each keyword
        lab = [i for i, s in self.sn.items() if s.get("label")]
        L = binary(self.vec.transform([sm.clean(f"{self.sn[i]['label']} . {self.sn[i].get('gloss') or ''}") for i in lab]))
        self.labelvec = {i: L[j].toarray()[0] for j, i in enumerate(lab)}

    def encode(self, question):
        """Binary question keywords / their count: a text's score is the share of question keywords it contains."""
        q = (self.vec.transform([sm.clean(TEMPLATE.sub(" ", question))]).toarray()[0] > 0).astype(float)
        return q / max(1.0, q.sum())

    def score(self, i, q):
        c = float(self.centroid[i] @ q)
        return 0.5 * float(self.labelvec[i] @ q) + 0.5 * c if i in self.labelvec else c

    def rank(self, ids, q):
        """[(leaf, score)] best first, ties by id."""
        ids = sorted(ids)
        s = self.X[[self.row[v] for v in ids]] @ q if ids else np.zeros(0)
        return sorted(zip(ids, map(float, s)), key=lambda t: (-t[1], t[0]))


def descend(ix, q, kinds, beam=BEAM):
    """Beam search from L0 to the finest level -> (ranked pool, trace)."""
    frontier, trace = ix.roots, []
    for level, b in enumerate(beam):
        scored = sorted(((ix.score(i, q), i) for i in frontier), key=lambda t: (-t[0], t[1]))
        keep = [i for _, i in scored[:b]]
        trace += [{"level": level, "id": i, "label": ix.sn[i].get("label"), "score": round(s, 4), "kept": i in keep}
                  for s, i in scored]
        frontier = [c for i in keep for c in ix.children[i]]
    pool = {v for i in keep for v in ix.sn[i]["member_ids"] if ix.F.type[v] in kinds}
    return ix.rank(pool, q), trace


def flat(ix, q, kinds):
    return ix.rank([v for v in ix.leaves if ix.F.type[v] in kinds], q), []


def extract(F, qtype, ranked, as_of, k=K):
    """The answer in the ground-truth format, plus the node and article ids it was read from."""
    if qtype == "A":
        seen, picked = set(), []
        for v, _ in ranked:
            key = sm.name_key(F.name[v])
            if key and key not in seen:
                seen.add(key)
                picked.append(v)
            if len(picked) == k:
                break
        claims = {v: sorted(F.method_claims[v])[:CLAIMS_PER_METHOD] for v in picked}
        arts = list(dict.fromkeys(a for v in picked for a in F.articles_of[v]))
        return {"expected_methods": [F.name[v] for v in picked],
                "method_claims": {F.name[v]: [F.name[c] for c in cs] for v, cs in claims.items()},
                "method_evidence": {F.name[v]: [{"source": F.citation(a), "location": c, "evidence": F.name[c]}
                                                for c in cs for a in F.articles_of[c][:1]] for v, cs in claims.items()},
                "required_citations": [F.citation(a) for a in arts],
                "node_ids": picked, "method_claim_ids": {v: cs for v, cs in claims.items()}, "article_ids": arts}
    picked = [v for v, _ in ranked[:k]]
    arts = list(dict.fromkeys(a for v in picked for a in F.articles_of[v]))
    key = {a: f"{fold(F.citation(a).split(' ')[0])}{F.year[a]}_{a}" for a in arts}
    return {"as_of": as_of,
            "required_claims": [{"id": f"R{i + 1}", "text": F.name[v], "sources": [key[a] for a in F.articles_of[v]]}
                                for i, v in enumerate(picked)],
            "sources": {key[a]: {"key": F.citation(a), "title": F.title.get(a), "date": str(F.year[a])} for a in arts},
            "required_citations": [key[a] for a in arts], "node_ids": picked, "article_ids": arts}


class Agent:
    """answer(question, qtype, mode) for mode 'hier' (drill-down) or 'flat' (baseline); sees only the question and type."""

    def __init__(self, tkh, run_dir, cutoffs, beam=BEAM, k=K):
        self.tkh, self.run_dir, self.cutoffs, self.beam, self.k = tkh, Path(run_dir), sorted(cutoffs), tuple(beam), k
        self._ix = {}

    def index(self, cutoff):
        if cutoff not in self._ix:
            self._ix[cutoff] = Index(self.tkh, self.run_dir, cutoff)
        return self._ix[cutoff]

    def answer(self, question, qtype, mode="hier"):
        c, year, source = choose_snapshot(question, self.cutoffs)
        if c is None:                                    # date before the first cutoff: no admissible snapshot
            return {"abstain": True, "snapshot": None, "snapshot_source": source}
        ix = self.index(c)
        if mode == "hier" and len(self.beam) != ix.depth:
            raise ValueError(f"beam {self.beam} has {len(self.beam)} widths; the hierarchy has {ix.depth} levels")
        q = ix.encode(question)
        ranked, trace = descend(ix, q, KINDS[qtype], self.beam) if mode == "hier" else flat(ix, q, KINDS[qtype])
        out = extract(ix.F, qtype, ranked, f"{year or c}", self.k)
        out.update(snapshot=c, snapshot_source=source, ranked=[v for v, _ in ranked], trace=trace,
                   n_supernodes_scored=len(trace),
                   closest={lv: next((t["id"], t["label"], t["score"]) for t in trace if t["level"] == lv)
                            for lv in sorted({t["level"] for t in trace})})
        if ranked:
            out["closest"]["leaf"] = (ranked[0][0], ix.F.name[ranked[0][0]], round(ranked[0][1], 4))
        return out
