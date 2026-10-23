"""Held-out coherence check: are papers whose concept nodes a hierarchy groups together related by an independent signal?

The signal is bibliographic coupling, which no clustering input contains (citations and cited works never
enter the method). Everything below is fixed by the evaluator and computed once on the REAL export, the same
for every configuration, budget list and null replicate; only the evaluated partition changes.

  evaluator hubs  concept nodes in >= floor(EVAL_HUB_FRAC * #papers) + 1 papers (fixed, not the method's hub_frac)
  concepts(p)     non-hub concept nodes of paper p (provenance or incident edges)
  names           normalised surface forms AND aliases (tkh.semantic.name_keys): the names the method's text sees
  coupling c_pq   IDF-weighted Salton cosine of the cited-work sets of p and q, after a residual filter that drops
                  p's cited works named like one of p's own concept nodes (exact: a shared normalised name; fuzzy:
                  also containment of names of >= 4 characters), so that "extends X / cites X" is not counted
  no-overlap      paper pairs that share no non-hub concept node and no concept name: here the hierarchy can only
                  relate them by grouping DIFFERENT nodes, and shared structure explains nothing
  a_pq(level)     sum_S n_S(p) n_S(q) / (n_p n_q): how much the level co-assigns the two papers' concepts
  lift            sum a c / (sum a * mean c) over no-overlap pairs among citing papers; 1 = chance
  period-adjusted sum a c / sum a e (indirect standardisation), with e_pq the mean coupling of the no-overlap
                  pairs in the same stratum of publication periods of the two papers: a control for the
                  confounder "papers of the same period cite the same work", which both nulls preserve.
                  Period schemes (PERIODS): "interval" (primary; the snapshot cutoff intervals, the same strata
                  the random-label null permutes within), "year1", "year2", "year3" (bins of 1-3 years) and
                  "gap" (the absolute difference of the publication years)

Uncertainty: paper-cluster bootstrap (resampling papers, pairs within the resample). Nulls: tkh/null.py.
"""

from collections import Counter, defaultdict
import bisect
import math
import random

import numpy as np
from scipy.sparse import csr_matrix

from tkh.coarsen import concept_nodes, hubs, node_papers
from tkh.semantic import name_keys

EVAL_HUB_FRAC = 0.4
PERIODS = ("interval", "year1", "year2", "year3", "gap")


class Ruler:
    def __init__(self, tkh, snap, works=None, fuzzy=False, cutoffs=None, period="interval"):
        papers = node_papers(tkh, snap)
        concept = concept_nodes(tkh, snap)
        hubset = hubs(tkh, snap, EVAL_HUB_FRAC)
        nk = name_keys(tkh)
        self.concepts, keys = defaultdict(set), defaultdict(set)
        for v in concept:
            if v not in hubset:
                for a in papers[v]:
                    self.concepts[a].add(v)
                    keys[a] |= nk[v]
        cites, removed = defaultdict(set), 0
        e = snap.edges
        for m, r, a in zip(e["members"], e["relation_type"], e["article_id"]):
            if r == "cites":
                for w in m[1:]:
                    if any(_named_like(k, keys[a], fuzzy) for k in nk[w]):
                        removed += 1
                    else:
                        cites[a].add(w)
        citing = [a for a in cites if cites[a]]
        df = Counter(w for a in citing for w in cites[a])               # IDF from all citations
        self.papers = sorted((a for a in citing if works is None or cites[a] & works), key=str)
        idx = {w: i for i, w in enumerate(sorted(df))}
        X = np.zeros((len(self.papers), len(idx)))
        for i, a in enumerate(self.papers):
            for w in cites[a]:
                if works is None or w in works:
                    X[i, idx[w]] = math.log(len(citing) / df[w])
        nrm = np.linalg.norm(X, axis=1)
        G, den = X @ X.T, np.outer(nrm, nrm)
        self.c = np.divide(G, den, out=np.zeros_like(G), where=den > 0)
        n = len(self.papers)
        overlap = np.zeros((n, n), bool)
        for i, p in enumerate(self.papers):
            for j, q in enumerate(self.papers):
                overlap[i, j] = bool(self.concepts[p] & self.concepts[q]) or bool(keys[p] & keys[q])
        self.mask = np.triu(~overlap, 1)
        self.stratum = _strata([tkh.articles["year"].to_dict()[p] for p in self.papers], period, cutoffs or [snap.cutoff])
        self.nodes = concept
        col = {v: j for j, v in enumerate(concept)}
        rows = [(i, col[v]) for i, p in enumerate(self.papers) for v in self.concepts[p]]
        r, cc = zip(*rows) if rows else ((), ())
        n_p = np.bincount(np.asarray(r, int), minlength=n).astype(float)
        self.Pn = csr_matrix((1.0 / n_p[list(r)], (r, cc)), shape=(n, len(concept)))   # rows sum to 1
        self.removed = removed

    def labels(self, level):
        """Super-node index of every concept node (in self.nodes order) for a level {key: set(members)}."""
        where = {v: i for i, mem in enumerate(level.values()) for v in mem}
        return np.array([where[v] for v in self.nodes])

    def coassign(self, level=None, g=None):
        """a_pq for one level, given as {key: set(members)} or as a label array g (non-concept members are ignored)."""
        g = self.labels(level) if g is None else g
        N = (self.Pn @ csr_matrix((np.ones(len(g)), (np.arange(len(g)), g)), shape=(len(g), g.max() + 1))).toarray()
        return N @ N.T

    def expected(self, m):
        """e_pq: mean coupling of the (weighted) no-overlap pairs in the pair's period stratum."""
        e = np.zeros_like(self.c)
        for s in np.unique(self.stratum[m > 0]):
            sel = (self.stratum == s) & (m > 0)
            e[sel] = (m[sel] * self.c[sel]).sum() / m[sel].sum()
        return e

    def lift(self, a, weights=None, adjusted=False):
        """Lift for a co-assignment matrix `a` (from coassign); `weights`: paper multiplicities (bootstrap);
        adjusted: period-adjusted lift (expected coupling per period stratum instead of the overall mean)."""
        c, m = self.c, self.mask.astype(float)
        if weights is not None:
            m = m * np.outer(weights, weights)
        e = self.expected(m) if adjusted else np.full_like(c, (m * c).sum() / max(m.sum(), 1e-300))
        num, den = (m * a * c).sum(), (m * a * e).sum()
        return float(num / den) if den > 0 else math.nan

    def bootstrap(self, a, B=200, seed=0, adjusted=False):
        """Paper-cluster bootstrap of the lift: (SE, 2.5%, 97.5%, number of defined draws)."""
        rng = np.random.default_rng(seed)
        n = len(self.papers)
        v = np.array([self.lift(a, np.bincount(rng.integers(0, n, n), minlength=n).astype(float), adjusted) for _ in range(B)])
        v = v[np.isfinite(v)]   # a draw with no co-assigned (or no coupled-stratum) pair has no lift
        if len(v) < 2:
            return math.nan, math.nan, math.nan, len(v)
        return float(v.std(ddof=1)), float(np.percentile(v, 2.5)), float(np.percentile(v, 97.5)), len(v)

    def coverage(self):
        return {"citing_papers": len(self.papers), "no_overlap_pairs": int(self.mask.sum()),
                "period_strata": int(len(np.unique(self.stratum[self.mask]))),
                "coupled_no_overlap_pairs": int((self.mask & (self.c > 0)).sum()), "filtered_citations": self.removed}


def _strata(years, period, cutoffs):
    """Stratum id per pair of papers: an unordered pair of periods, or the year gap."""
    y = np.asarray(years, int)
    if period == "gap":
        return np.abs(np.subtract.outer(y, y))
    if period == "interval":
        b = np.array([bisect.bisect_left(sorted(cutoffs), v) for v in y])
    elif period in ("year1", "year2", "year3"):
        b = y // int(period[-1])
    else:
        raise ValueError(f"period must be one of {PERIODS}, got {period!r}")
    return np.minimum.outer(b, b) * 10000 + np.maximum.outer(b, b)


def _named_like(k, keys, fuzzy):
    if k in keys:
        return True
    return fuzzy and len(k) >= 4 and any(len(x) >= 4 and (k in x or x in k) for x in keys)


def split_works(tkh, snap, seed):
    """Seeded half split of the cited works, stratified by how many papers cite them: (A, B)."""
    rng = random.Random(seed)
    df = Counter(w for m, r in zip(snap.edges["members"], snap.edges["relation_type"]) if r == "cites" for w in set(m[1:]))
    by_df = defaultdict(list)
    for w, n in df.items():
        by_df[n].append(w)
    A, B = set(), set()
    for n in sorted(by_df):
        ws = sorted(by_df[n])
        rng.shuffle(ws)
        first, second = (A, B) if rng.random() < 0.5 else (B, A)   # an odd stratum's extra work goes to either half
        first.update(ws[0::2])
        second.update(ws[1::2])
    return A, B


def null_summary(obs, null):
    v = np.array([x for x in null if np.isfinite(x)])
    if not len(v):
        return {"R": 0}
    if not np.isfinite(obs):   # the evaluated level co-assigns no evaluable pair: no test
        return {"R": len(v), "mean": float(v.mean()), "q2.5": float(np.percentile(v, 2.5)),
                "q97.5": float(np.percentile(v, 97.5)), "z": None, "p": None}
    sd = v.std(ddof=1) if len(v) > 1 else 0.0
    return {"R": len(v), "mean": float(v.mean()), "q2.5": float(np.percentile(v, 2.5)), "q97.5": float(np.percentile(v, 97.5)),
            "z": float((obs - v.mean()) / sd) if sd > 0 else None, "p": float((1 + (v >= obs).sum()) / (len(v) + 1))}
