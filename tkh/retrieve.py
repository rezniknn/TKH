"""T6 extrinsic utility: a retrieval agent that starts at the coarsest level of a snapshot's hierarchy and drills down
to the leaf nodes that answer a question, and the flat baseline that ranks every leaf directly.

Agent(tkh, run_dir, cutoffs).answer(question, qtype, mode="hier" | "flat") -> answer dict (ground-truth format)
  1. snapshot  `choose_snapshot`: the latest cutoff <= the year the question names ("by Feb 2026" -> 2026); a question
               with no date gets the latest cutoff. Only that snapshot's nodes, edges and hierarchy are used (P6).
  2. content   each leaf's text is its name and aliases, the names of its relation neighbours and its evaluated_on
               attributes (metric, task), all from edges <= cutoff, plus the title of the article that presents it
               (methods, once) or makes it (claims), and for a presented method its paper's claims (`Settings`
               leaf_info). Scored by keyword overlap: the share of the question's keywords present in the text
               (`Settings` scorer; tfidf and bm25 are the alternatives). Every vocabulary and statistic is fitted on the
               snapshot's own leaf texts.
  3. descent   L0 and L1 super-nodes score 0.5 s(q, label + gloss) + 0.5 s(q, member centroid); L2 (unlabelled)
               scores the centroid. Beam search keeps the best `beam[k]` super-nodes per level (10 / 20 / 40) among the
               children of the previous level's kept nodes. The leaves of the kept L2 nodes of the answer kinds form
               the pool, ranked by s(q, leaf). The trace records every super-node scored and which were kept.
  4. flat      the same scorer and answer kinds over every leaf of the snapshot.
  5. answer    type A (methods): the top-k distinct method names, and as citations the articles they come from;
               type B (claims): the top-k claims, their source articles and citation keys.
The question type is given by the question's metadata (data/questions.csv); the agent never sees ground truth.
"""

from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
import json
import re
import unicodedata

import numpy as np
import scipy.sparse as sp
from sklearn.feature_extraction.text import CountVectorizer
from sklearn.preprocessing import normalize

from tkh import semantic as sm
from tkh.coarsen import CLUSTER_RELATIONS
from tkh.io import snapshot

KINDS = {"A": ("method", "technique", "component", "dataset"),   # GT "expected_methods" also lists datasets (Q14)
         "B": ("claim",)}
MONTHS = "jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec"
DATE = re.compile(rf"\b(?:by|as of|before|until|up to)\s+(?:(?:{MONTHS})[a-z]*\.?\s+)?((?:19|20)\d\d)\b", re.I)
TEMPLATE = re.compile(r"\((?:by|as of)[^)]*\)|\b(?:which|what|are|is|the|methods?|best|suited|leading|most|"
                      r"important|commonly|used|give|evidences?|when|for|of|by|feb|\d{4})\b", re.I)


def choose_snapshot(question, cutoffs):
    """(cutoff, source): the latest cutoff <= the stated year; no date -> the latest cutoff."""
    cutoffs = sorted(cutoffs)
    m = DATE.search(question)
    if not m:
        return cutoffs[-1], "default_latest"
    year = int(m.group(1))
    ok = [c for c in cutoffs if c <= year]
    return (ok[-1], "stated") if ok else (cutoffs[0], "before_first_cutoff")


def fold(s):
    """Lower case without diacritics (Bartók -> bartok)."""
    return "".join(ch for ch in unicodedata.normalize("NFKD", str(s)) if not unicodedata.combining(ch)).lower()


def surname(full):
    return fold(sm.clean(full).split(" ")[-1])


LEAF_INFO = ("name", "rel", "full", "full+claims")
NODE_INFO = ("blend", "label", "centroid", "kind_centroid", "doc")
SCORERS = ("tfidf", "bm25", "overlap")
QUERY = ("stripped", "full", "task", "condition")


@dataclass(frozen=True)
class Settings:
    """Retrieval knobs (eval/retrieval_experiments.py sweeps them; the defaults are the applied configuration).
    beam       super-nodes kept per level, L0 first; with rel set, the beam is the cap per level instead
    rel        keep every scored child >= rel x the level's best score (at least min_keep)
    node_info  super-node content compared with the question: blend (0.5 label + gloss, 0.5 member centroid; L2
               centroid), label (label + gloss; L2 centroid), centroid (all members), kind_centroid (members of the
               answer kinds), doc (label + gloss + names of the answer-kind members as one document)
    leaf_info  leaf text: name (name + aliases), rel (+ relation neighbours, evaluated_on metric/task), full (+ title
               of the presenting / claiming article), full+claims (+ for a presented method, its paper's claims)
    scorer     tfidf (cosine of word TF-IDF), bm25 (keyword matching, k1 = 1.2, b = 0.75), overlap (share of the
               question's keywords present in the node text)
    query      stripped (template words removed), full, task (the phrase after 'for' / before 'when'), condition
               (the clause after 'when'); task and condition fall back to stripped
    """
    beam: tuple = (10, 20, 40)          # selected by eval/retrieval_experiments.py (docs/retrieval_report.md §8)
    rel: float = None
    min_keep: int = 1
    node_info: str = "blend"
    leaf_info: str = "full+claims"
    scorer: str = "overlap"
    query: str = "stripped"
    k: int = 10


def leaf_texts(tkh, snap, info="full"):
    """{node id: text} from the snapshot's own edges only (tkh.semantic.attached_text reads all edges)."""
    name = sm.names(tkh)
    title = tkh.articles["title"].to_dict()
    ntype = tkh.nodes["type"].to_dict()
    txt = {v: [name[v]] for v in snap.node_ids}
    if info == "name":
        return {v: " . ".join(x) for v, x in txt.items()}
    e = snap.edges
    attrs = e["attributes"] if "attributes" in e else [None] * len(e)
    presented, claims_of = {}, defaultdict(list)
    for m, r, a, at in zip(e["members"], e["relation_type"], e["article_id"], attrs):
        if r in CLUSTER_RELATIONS:
            head, tails = m[0], m[1:]
            txt[head] += [name[t] for t in tails]
            for t in tails:
                txt[t].append(name[head])
            if r == "evaluated_on" and isinstance(at, dict):
                extra = " ".join(str(at[k]) for k in ("metric", "task") if at.get(k))
                for v in m:
                    txt[v].append(extra)
        elif info == "rel":
            continue
        elif r == "presents" and isinstance(title.get(a), str):   # the presented method: its paper's title, once
            txt[m[1]].append(sm.clean(title[a]))
            presented[a] = m[1]
        elif r == "claims" and isinstance(title.get(a), str):     # claim nodes only (methods on claims edges excluded)
            for v in m[1:]:
                if ntype[v] == "claim":
                    txt[v].append(sm.clean(title[a]))
                    claims_of[a].append(name[v])
    if info == "full+claims":
        for a, v in presented.items():
            txt[v] += claims_of[a]
    return {v: " . ".join(x) for v, x in txt.items()}


class Space:
    """Documents and queries as vectors whose dot product is the score: tfidf (L2-normalised TF-IDF, cosine),
    bm25 (per-document BM25 term weights . binary query), overlap (binary document . query / its keyword count)."""

    def __init__(self, texts, scorer):
        self.scorer = scorer
        if scorer == "tfidf":
            self.X, self.vec = sm.vectorize(texts, kind="word")
            return
        self.vec = CountVectorizer(lowercase=True, stop_words="english", token_pattern=r"(?u)\b[\w][\w\-\+]*\b")
        C = self.vec.fit_transform(texts)
        n, df = C.shape[0], np.bincount(C.indices, minlength=C.shape[1])
        self.idf = np.log((n - df + 0.5) / (df + 0.5) + 1.0)
        self.avgdl = C.sum() / n
        self.X = self._weights(C)

    def _weights(self, C, k1=1.2, b=0.75):
        C = sp.csr_matrix(C, dtype=float)
        if self.scorer == "overlap":
            C.data[:] = 1.0
            return C
        dl = np.asarray(C.sum(axis=1)).ravel()
        rows = np.repeat(np.arange(C.shape[0]), np.diff(C.indptr))
        tf = C.data
        C.data = self.idf[C.indices] * tf * (k1 + 1) / (tf + k1 * (1 - b + b * dl[rows] / self.avgdl))
        return C

    def docs(self, texts):
        """Vectors of texts outside the fitted corpus (labels, super-node documents)."""
        texts = [sm.clean(t) for t in texts]
        if self.scorer == "tfidf":
            return normalize(self.vec.transform(texts))
        return self._weights(self.vec.transform(texts))

    def query(self, text):
        if self.scorer == "tfidf":
            return normalize(self.vec.transform([text])).toarray()[0]
        q = (self.vec.transform([text]).toarray()[0] > 0).astype(float)
        return q / max(1.0, q.sum()) if self.scorer == "overlap" else q


def query_text(question, mode):
    """The part of the question compared with node content."""
    if mode == "full":
        return sm.clean(question)
    q = re.sub(r"\((?:by|as of)[^)]*\)", " ", question)
    if mode == "task":
        m = re.search(r"\bfor (.+?)(?:\bwhen\b|\?|$)", q, re.I)
        q = m.group(1) if m else q
    elif mode == "condition":
        m = re.search(r"\bwhen (.+?)(?:\?|$)", q, re.I)
        q = m.group(1) if m else q
    return sm.clean(TEMPLATE.sub(" ", q))


class Index:
    """One snapshot under one leaf text and scorer: its hierarchy, leaf and super-node vectors, and article metadata."""

    def __init__(self, tkh, run_dir, cutoff, leaf_info="full", scorer="tfidf"):
        snap = snapshot(tkh, cutoff)
        h = json.loads((Path(run_dir) / str(cutoff) / "hierarchy.json").read_text())
        self.cutoff, self.sn = cutoff, {s["id"]: s for s in h["supernodes"]}
        self.children = defaultdict(list)
        for s in h["supernodes"]:
            if s["parent_id"] is not None:
                self.children[s["parent_id"]].append(s["id"])
        self.roots = [s["id"] for s in h["supernodes"] if s["level"] == 0]
        self.depth = h["levels"]
        self.leaves = sorted({v for s in h["supernodes"] if s["level"] == self.depth - 1 for v in s["member_ids"]})
        texts = leaf_texts(tkh, snap, leaf_info)
        self.space = Space([texts[v] for v in self.leaves], scorer)
        self.X, self.row = self.space.X, {v: i for i, v in enumerate(self.leaves)}
        self.type = tkh.nodes["type"].to_dict()
        self.name = {v: sm.clean(s) for v, s in tkh.nodes["surface_form"].items()}
        self.keys = sm.name_keys(tkh)
        self._rep = {}
        # citations: article -> year, title, author surnames; leaf -> its articles within the snapshot
        arts = tkh.articles
        self.art_year = {a: int(y) for a, y in arts["year"].items() if a in snap.articles}
        self.art_title = {a: sm.clean(t) for a, t in arts["title"].items() if a in snap.articles and isinstance(t, str)}
        self.authors = defaultdict(list)
        for m, r, a in zip(snap.edges["members"], snap.edges["relation_type"], snap.edges["article_id"]):
            if r == "authored_by":
                self.authors[a] += [self.name[v] for v in m[1:]]
        prov = tkh.nodes["prov_articles"].to_dict()
        self.articles_of = {v: [a for a in prov[v] if a in snap.articles] for v in self.leaves}
        self.presents = defaultdict(list)
        for m, r, a in zip(snap.edges["members"], snap.edges["relation_type"], snap.edges["article_id"]):
            if r == "presents":
                self.presents[a] += m[1:]

    def encode(self, question, mode="stripped"):
        return self.space.query(query_text(question, mode))

    def _centroid(self, members):
        rows = [self.row[v] for v in members]
        if not rows:
            return np.zeros(self.X.shape[1])
        c = np.asarray(self.X[rows].mean(axis=0))
        return normalize(c)[0] if self.space.scorer == "tfidf" else c[0]

    def reps(self, info, kinds):
        """{super-node id: [(weight, vector)]} for one node_info and answer kinds (cached)."""
        key = (info, kinds)
        if key not in self._rep:
            rep, labelled = {}, [sid for sid, s in self.sn.items() if s.get("label")]
            lab = dict(zip(labelled, self.space.docs([f"{self.sn[i]['label']} . {self.sn[i].get('gloss') or ''}"
                                                       for i in labelled]))) if labelled else {}
            vec = lambda m: m.toarray()[0] if sp.issparse(m) else np.asarray(m).ravel()   # noqa: E731
            if info == "doc":
                ids = list(self.sn)
                docs = self.space.docs([" . ".join([*(f"{self.sn[i]['label']} . {self.sn[i].get('gloss') or ''}"
                                                       for _ in [0] if self.sn[i].get("label")),
                                                     *(self.name[v] for v in self.sn[i]["member_ids"]
                                                       if self.type[v] in kinds)]) for i in ids])
                rep = {i: [(1.0, vec(docs[j]))] for j, i in enumerate(ids)}
            for sid, s in self.sn.items():
                if info == "doc":
                    continue
                members = [v for v in s["member_ids"] if info != "kind_centroid" or self.type[v] in kinds]
                c = self._centroid(members)
                if sid in lab and info == "blend":
                    rep[sid] = [(0.5, vec(lab[sid])), (0.5, c)]
                elif sid in lab and info == "label":
                    rep[sid] = [(1.0, vec(lab[sid]))]
                else:
                    rep[sid] = [(1.0, c)]
            self._rep[key] = rep
        return self._rep[key]

    def score(self, sid, q, info="blend", kinds=KINDS["A"]):
        return sum(w * float(v @ q) for w, v in self.reps(info, kinds)[sid])

    def rank(self, ids, q):
        """[(leaf, score)] best first, ties by id."""
        ids = sorted(ids)
        s = self.X[[self.row[v] for v in ids]] @ q if ids else np.zeros(0)
        return sorted(zip(ids, map(float, s)), key=lambda t: (-t[1], t[0]))

    def citation(self, a):
        """'Surname et al. YYYY' (author order is not recorded in the export: the first listed author is used)."""
        sur = [sm.clean(n).split(" ")[-1] for n in self.authors.get(a, [])]
        who = sur[0] if len(sur) == 1 else f"{sur[0]} & {sur[1]}" if len(sur) == 2 else f"{sur[0]} et al." if sur else "Anon."
        return f"{who} {self.art_year[a]}"


def _keep(scored, b, rel, min_keep):
    """Kept ids of one level's [(score, id)] (best first): the top b, or with rel every id >= rel x best (cap b)."""
    if rel is None:
        return [s for _, s in scored[:b]]
    best = scored[0][0] if scored else 0.0
    ok = [s for sc, s in scored if best > 0 and sc >= rel * best]
    return ok[:b] if len(ok) >= min_keep else [s for _, s in scored[:min(b, min_keep)]]


def descend(ix, q, kinds, beam, rel=None, min_keep=1, info="blend"):
    """Beam search from L0 to the finest level -> (ranked pool, trace)."""
    frontier, trace = ix.roots, []
    for level, b in enumerate(beam):
        scored = sorted(((ix.score(s, q, info, kinds), s) for s in frontier), key=lambda t: (-t[0], t[1]))
        keep = _keep(scored, b, rel, min_keep)
        trace += [{"level": level, "id": s, "label": ix.sn[s].get("label"), "score": round(sc, 4), "kept": s in keep}
                  for sc, s in scored]
        frontier = [c for s in keep for c in ix.children[s]]
    pool = {v for s in keep for v in ix.sn[s]["member_ids"] if ix.type[v] in kinds}
    return ix.rank(pool, q), trace


def flat(ix, q, kinds):
    return ix.rank([v for v in ix.leaves if ix.type[v] in kinds], q)


def extract(ix, qtype, ranked, k):
    """The answer in the ground-truth format, plus the node and article ids it was read from."""
    if qtype == "A":
        seen, picked = set(), []
        for v, _ in ranked:
            key = sm.name_key(ix.name[v])
            if key and key not in seen:
                seen.add(key)
                picked.append(v)
            if len(picked) == k:
                break
        arts = list(dict.fromkeys(a for v in picked for a in ix.articles_of[v]))
        return {"expected_methods": [ix.name[v] for v in picked], "required_citations": [ix.citation(a) for a in arts],
                "method_nodes": picked, "citation_articles": arts}
    picked = [v for v, _ in ranked[:k]]
    arts = list(dict.fromkeys(a for v in picked for a in ix.articles_of[v]))
    keys, used = {}, set()
    for a in arts:
        base = fold(ix.citation(a).split(" ")[0]) + str(ix.art_year[a])
        key = next(f"{base}{s}" for s in ["", *"bcdefgh"] if f"{base}{s}" not in used)
        used.add(key)
        keys[a] = key
    return {"required_claims": [{"id": f"R{i + 1}", "text": ix.name[v], "node_id": v,
                                 "sources": [keys[a] for a in ix.articles_of[v]]} for i, v in enumerate(picked)],
            "sources": {keys[a]: {"key": ix.citation(a), "title": ix.art_title.get(a), "date": str(ix.art_year[a]),
                                  "article_id": int(a)} for a in arts},
            "required_citations": [keys[a] for a in arts], "claim_nodes": picked, "citation_articles": arts}


class Agent:
    """answer(question, qtype, mode) for mode 'hier' (drill-down) or 'flat' (baseline), under one Settings.
    `cache` ({(cutoff, leaf_info, scorer): Index}) may be shared between agents of different settings."""

    def __init__(self, tkh, run_dir, cutoffs, settings=None, cache=None):
        self.tkh, self.run_dir, self.cutoffs = tkh, Path(run_dir), sorted(cutoffs)
        self.s = settings or Settings()
        self._ix = {} if cache is None else cache

    def index(self, cutoff):
        key = (cutoff, self.s.leaf_info, self.s.scorer)
        if key not in self._ix:
            self._ix[key] = Index(self.tkh, self.run_dir, cutoff, self.s.leaf_info, self.s.scorer)
        return self._ix[key]

    def answer(self, question, qtype, mode="hier"):
        cutoff, src = choose_snapshot(question, self.cutoffs)
        ix, s = self.index(cutoff), self.s
        q, kinds = ix.encode(question, s.query), KINDS[qtype]
        if mode == "hier":
            ranked, trace = descend(ix, q, kinds, tuple(s.beam)[:ix.depth], s.rel, s.min_keep, s.node_info)
        else:
            ranked, trace = flat(ix, q, kinds), []
        out = {"type": qtype, "snapshot": cutoff, "snapshot_source": src, **extract(ix, qtype, ranked, s.k)}
        if qtype == "B":
            out = {"as_of": str(cutoff), **out}
        out["ranked"] = [v for v, _ in ranked]           # full ranking, for steps-to-target
        out["top_leaves"] = [{"id": v, "name": ix.name[v], "score": round(sc, 4)} for v, sc in ranked[:s.k]]
        out["n_supernodes_scored"] = len(trace)
        out["closest"] = {lv: next((t["id"], t["label"], t["score"]) for t in trace if t["level"] == lv)
                          for lv in sorted({t["level"] for t in trace})}
        if ranked:
            out["closest"]["leaf"] = (ranked[0][0], ix.name[ranked[0][0]], round(ranked[0][1], 4))
        out["trace"] = trace
        return out
