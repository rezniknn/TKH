"""T6 extrinsic utility: a retrieval agent that starts at the coarsest level of a snapshot's hierarchy and drills down
to the leaf nodes that answer a question, and the flat baseline that ranks every leaf directly.

Agent(tkh, run_dir, cutoffs).answer(question, qtype, mode="hier" | "flat") -> answer dict (ground-truth format)
  1. snapshot  `choose_snapshot`: the latest cutoff <= the year the question names ("by Feb 2026" -> 2026); a question
               with no date gets the latest cutoff. Only that snapshot's nodes, edges and hierarchy are used (P6).
  2. content   each leaf's text is its name and aliases, the names of its relation neighbours and its evaluated_on
               attributes (metric, task), all from edges <= cutoff, plus the title of the article that presents it
               (methods, once) or makes it (claims), and for a presented method its paper's claims.
  3. score     keyword overlap: the share of the question's keywords (template words removed) present in a text; the
               vocabulary is fitted on the snapshot's own leaf texts.
  4. descent   L0 and L1 super-nodes score 0.5 s(q, label + gloss) + 0.5 s(q, member mean); L2 (unlabelled) scores the
               member mean. Beam search keeps the best BEAM[k] super-nodes per level (10 / 20 / 40) among the children
               of the previous level's kept nodes. The leaves of the kept L2 nodes of the answer kinds form the pool,
               ranked by s(q, leaf). The trace records every super-node scored and which were kept.
  5. flat      the same scorer and answer kinds over every leaf of the snapshot.
  6. answer    type A (methods): the top-K distinct method names, and as citations the articles they come from;
               type B (claims): the top-K claims, their source articles and citation keys.
The configuration was selected by a series of retrieval experiments (docs/retrieval_report.md section 8).
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


BEAM = (10, 20, 40)   # super-nodes kept per level, L0 first
K = 10                # answer length (methods or claims)


def leaf_texts(tkh, snap):
    """{node id: text} from the snapshot's own edges only (tkh.semantic.attached_text reads all edges)."""
    name = sm.names(tkh)
    title = tkh.articles["title"].to_dict()
    ntype = tkh.nodes["type"].to_dict()
    txt = {v: [name[v]] for v in snap.node_ids}
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
        elif r == "presents" and isinstance(title.get(a), str):   # the presented method: its paper's title, once
            txt[m[1]].append(sm.clean(title[a]))
            presented[a] = m[1]
        elif r == "claims" and isinstance(title.get(a), str):     # claim nodes only (methods on claims edges excluded)
            for v in m[1:]:
                if ntype[v] == "claim":
                    txt[v].append(sm.clean(title[a]))
                    claims_of[a].append(name[v])
    for a, v in presented.items():                                # a presented method: its paper's claims
        txt[v] += claims_of[a]
    return {v: " . ".join(x) for v, x in txt.items()}


class Overlap:
    """Keyword overlap as a dot product: binary document vectors . binary query / its keyword count."""

    def __init__(self, texts):
        self.vec = CountVectorizer(lowercase=True, stop_words="english", token_pattern=r"(?u)\b[\w][\w\-\+]*\b")
        self.X = self._binary(self.vec.fit_transform(texts))

    @staticmethod
    def _binary(C):
        C = sp.csr_matrix(C, dtype=float)
        C.data[:] = 1.0
        return C

    def docs(self, texts):
        """Vectors of texts outside the fitted corpus (labels and glosses)."""
        return self._binary(self.vec.transform([sm.clean(t) for t in texts]))

    def query(self, text):
        q = (self.vec.transform([text]).toarray()[0] > 0).astype(float)
        return q / max(1.0, q.sum())


class Index:
    """One snapshot: its hierarchy, leaf and super-node vectors, and article metadata for citations."""

    def __init__(self, tkh, run_dir, cutoff):
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
        texts = leaf_texts(tkh, snap)
        self.space = Overlap([texts[v] for v in self.leaves])
        self.X, self.row = self.space.X, {v: i for i, v in enumerate(self.leaves)}
        self.type = tkh.nodes["type"].to_dict()
        self.name = {v: sm.clean(s) for v, s in tkh.nodes["surface_form"].items()}
        self.keys = sm.name_keys(tkh)
        # super-nodes: label + gloss vector (L0-L1) and member mean
        labelled = [sid for sid, s in self.sn.items() if s.get("label")]
        lab = self.space.docs([f"{self.sn[i]['label']} . {self.sn[i].get('gloss') or ''}" for i in labelled])
        self.labelvec = {sid: lab[j].toarray()[0] for j, sid in enumerate(labelled)}
        self.centroid = {sid: np.asarray(self.X[[self.row[v] for v in s["member_ids"]]].mean(axis=0))[0]
                         for sid, s in self.sn.items()}
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

    def encode(self, question):
        """The question with its date clause and template words removed."""
        q = re.sub(r"\((?:by|as of)[^)]*\)", " ", question)
        return self.space.query(sm.clean(TEMPLATE.sub(" ", q)))

    def score(self, sid, q):
        c = float(self.centroid[sid] @ q)
        return 0.5 * float(self.labelvec[sid] @ q) + 0.5 * c if sid in self.labelvec else c

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


def descend(ix, q, kinds, beam=BEAM):
    """Beam search from L0 to the finest level -> (ranked pool, trace)."""
    frontier, trace = ix.roots, []
    for level, b in enumerate(beam):
        scored = sorted(((ix.score(s, q), s) for s in frontier), key=lambda t: (-t[0], t[1]))
        keep = [s for _, s in scored[:b]]
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
    """answer(question, qtype, mode) for mode 'hier' (drill-down) or 'flat' (baseline)."""

    def __init__(self, tkh, run_dir, cutoffs):
        self.tkh, self.run_dir, self.cutoffs = tkh, Path(run_dir), sorted(cutoffs)
        self._ix = {}

    def index(self, cutoff):
        if cutoff not in self._ix:
            self._ix[cutoff] = Index(self.tkh, self.run_dir, cutoff)
        return self._ix[cutoff]

    def answer(self, question, qtype, mode="hier"):
        cutoff, src = choose_snapshot(question, self.cutoffs)
        ix = self.index(cutoff)
        q, kinds = ix.encode(question), KINDS[qtype]
        if mode == "hier":
            ranked, trace = descend(ix, q, kinds, BEAM[:ix.depth])
        else:
            ranked, trace = flat(ix, q, kinds), []
        out = {"type": qtype, "snapshot": cutoff, "snapshot_source": src, **extract(ix, qtype, ranked, K)}
        if qtype == "B":
            out = {"as_of": str(cutoff), **out}
        out["ranked"] = [v for v, _ in ranked]           # full ranking, for steps-to-target
        out["top_leaves"] = [{"id": v, "name": ix.name[v], "score": round(sc, 4)} for v, sc in ranked[:K]]
        out["n_supernodes_scored"] = len(trace)
        out["closest"] = {lv: next((t["id"], t["label"], t["score"]) for t in trace if t["level"] == lv)
                          for lv in sorted({t["level"] for t in trace})}
        if ranked:
            out["closest"]["leaf"] = (ranked[0][0], ix.name[ranked[0][0]], round(ranked[0][1], 4))
        out["trace"] = trace
        return out
