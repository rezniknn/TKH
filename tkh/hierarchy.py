"""T2: SHAC, the laminar multi-level hierarchy P_0..P_K per snapshot; P1 by construction, P2 budgets as hard limits.

Semantic-Hypergraph Agglomerative Coarsening; the formal statement is docs/formal_statement.md.
Per snapshot and level k (finest first), starting from the concept nodes as singletons and then
from the level-(k+1) super-nodes:

  repeat: merge the feasible pair (A, B) with the highest score s(A, B)
  until exactly min(N_k, #items) super-nodes remain

  s(A, B) = alpha * F_S(S(A, B)) + (1 - alpha) * F_H(H(A, B))
  S(A, B) = mean_A . mean_B of centred, L2-normalised char-n-gram LSA vectors of the member names
            (= average pairwise cosine)
  H(A, B) = sum_{e containing A and B} w_e / sqrt(d_A d_B),  d_A = sum_{e containing A} w_e, on the
            CURRENT collapsed incidence (tkh/coarsen.py): the degree-normalised reduction of the
            weighted connectivity cut sum_e w_e (lambda_e - 1) when A and B merge; 0 if d_A d_B = 0
  F_S     = mid-rank empirical CDF of S over all item pairs at the start of the level
  F_H     = mid-rank empirical CDF of H over the item pairs with H > 0, and F_H(0) = 0: a pair that
            shares no edge gets no structural credit
  feasible: |A| + |B| <= rho * n_t / N_k  (concept nodes; rho >= 2 always leaves a feasible pair)
  ties    : scores rounded to 1e-9, then the lowest item index

Non-concept nodes are anchored (`anchors`) and inherit their anchor's super-node.
"""

from dataclasses import dataclass, asdict, fields
import math

import numpy as np
from scipy.sparse import csr_matrix
from sklearn.decomposition import TruncatedSVD

from tkh import semantic as sm
from tkh.coarsen import EDGE_WEIGHTS, concept_nodes, hub_threshold, hubs, incidence
from tkh.io import make_snapshots


@dataclass(frozen=True)
class Params:
    alpha: float = 0.5                     # weight of the semantic rank; 0 = structure only, 1 = semantics only
    rho: float = 2.0                       # size cap factor (>= 2, or inf)
    edge_weight: str = "relation_balanced"
    hub_frac: float = 0.2                  # hubs: concept nodes in more than this share of the snapshot's papers
    lsa_dim: int = 100

    @classmethod
    def from_config(cls, d):
        d = dict(d or {})
        unknown = set(d) - {f.name for f in fields(cls)}
        if unknown:
            raise ValueError(f"unknown [method] parameters {sorted(unknown)}")
        if "rho" in d:
            d["rho"] = math.inf if str(d["rho"]).lower() in ("inf", "none") else float(d["rho"])
        p = cls(**d)
        if not 0 <= p.alpha <= 1 or p.rho < 2 or not 0 < p.hub_frac <= 1:
            raise ValueError(f"need 0 <= alpha <= 1, rho >= 2, 0 < hub_frac <= 1: {p}")
        if p.edge_weight not in EDGE_WEIGHTS or not (isinstance(p.lsa_dim, int) and p.lsa_dim > 0):
            raise ValueError(f"need edge_weight in {EDGE_WEIGHTS} and a positive integer lsa_dim: {p}")
        return p

    def as_dict(self):
        d = asdict(self)
        d["rho"] = "inf" if math.isinf(self.rho) else self.rho
        return d

    def cid(self):
        r = "inf" if math.isinf(self.rho) else f"{self.rho:g}"
        return f"a{self.alpha:g}_r{r}_{self.edge_weight}_h{self.hub_frac:g}_d{self.lsa_dim}"


# ---------------------------------------------------------------- signals

def centred_lsa(texts, dim):
    """Deterministic char-n-gram LSA, mean-centred and L2-normalised (rows of zeros stay zero)."""
    X, _ = sm.vectorize(texts, "char")
    k = min(dim, min(X.shape) - 1)
    if k < 1:
        return np.zeros((len(texts), 1))
    if min(X.shape) <= 400:  # small inputs: exact dense SVD
        U, s, _ = np.linalg.svd(X.toarray(), full_matrices=False)
        Z = U[:, :k] * s[:k]
    else:
        Z = TruncatedSVD(k, algorithm="arpack", random_state=0).fit_transform(X)
    Z = Z - Z.mean(axis=0)
    norms = np.linalg.norm(Z, axis=1, keepdims=True)
    return np.divide(Z, norms, out=np.zeros_like(Z), where=norms > 0)


class _MidRankCDF:
    """F(x) = (#{v < x} + #{v <= x}) / (2N) over a fixed sample; positive=True: sample of x > 0 only, F(x <= 0) = 0."""

    def __init__(self, values, positive=False):
        self.positive = positive
        values = values[values > 0] if positive else values
        self.u, cnt = np.unique(values, return_counts=True)
        self.cum = np.concatenate([[0], np.cumsum(cnt)])
        self.n = max(len(values), 1)

    def __call__(self, x):
        x = np.asarray(x, dtype=float)
        flat = x.ravel()
        order = np.argsort(flat, kind="stable")  # sorted queries make the binary searches faster
        xs = flat[order]
        out = np.empty_like(flat)
        out[order] = (self.cum[np.searchsorted(self.u, xs, "left")] + self.cum[np.searchsorted(self.u, xs, "right")]) / (2.0 * self.n)
        if self.positive:
            out[flat <= 0] = 0.0
        return out.reshape(x.shape)


# ---------------------------------------------------------------- engine

class _Level:
    """Greedy constrained agglomeration of n items down to a target count, on the collapsed incidence."""

    def __init__(self, sem, size, C, w, alpha, cap):
        self.alpha, self.cap = alpha, cap
        self.sem = sem.astype(np.float64)            # sum of member vectors
        self.size = size.astype(np.float64)          # concept nodes per item
        self.C = C.astype(np.float64)                # endpoint counts per item and fine edge (n x E)
        self.X = (self.C > 0).astype(np.float64)     # collapsed incidence (presence)
        self.w = w.astype(np.float64)
        self.d = self.X @ self.w
        n = len(size)
        self.alive = np.ones(n, bool)
        iu = np.triu_indices(n, 1)
        S, H = self._S(), self._H()
        self.FS, self.FH = _MidRankCDF(S[iu]), _MidRankCDF(H[iu], positive=True)
        self.score = self._combine(S, H)
        del S, H
        np.fill_diagonal(self.score, -np.inf)
        if math.isfinite(cap):
            self.score[np.add.outer(self.size, self.size) > cap] = -np.inf
        self.best = np.argmax(self.score, axis=1)
        self.bval = self.score[np.arange(n), self.best]
        self.stats = {"merges": 0, "linked": 0, "multi_endpoint": 0}

    def _S(self, r=None):
        mean = self.sem / self.size[:, None]
        return (mean if r is None else mean[r]) @ mean.T

    def _H(self, r=None):
        Xr = self.X if r is None else self.X[r]
        num = (Xr * self.w) @ self.X.T
        dr = self.d if r is None else self.d[r]
        den = np.sqrt(np.outer(dr, self.d))
        return np.divide(num, den, out=np.zeros_like(num), where=den > 0)

    def _combine(self, S, H):
        return np.round(self.alpha * self.FS(S) + (1 - self.alpha) * self.FH(H), 9)

    def merge(self, i, j):
        """Merge item j into item i (i < j)."""
        shared = (self.X[i] > 0) & (self.X[j] > 0)
        self.stats["merges"] += 1
        self.stats["linked"] += bool(shared.any())
        # native and clique-expansion H differ exactly when a shared edge has >= 2 endpoints on one side
        self.stats["multi_endpoint"] += bool((shared & ((self.C[i] >= 2) | (self.C[j] >= 2))).any())
        self.sem[i] += self.sem[j]
        self.size[i] += self.size[j]
        self.C[i] += self.C[j]
        self.X[i] = self.C[i] > 0
        self.d[i] = self.X[i] @ self.w
        self.alive[j] = False
        self.score[j, :] = self.score[:, j] = -np.inf
        row = self._combine(self._S([i]), self._H([i]))[0]
        row[i] = -np.inf
        row[~self.alive] = -np.inf
        if math.isfinite(self.cap):
            row[self.size[i] + self.size > self.cap] = -np.inf
        self.score[i, :] = self.score[:, i] = row
        self.bval[j] = -np.inf
        self.best[i] = int(np.argmax(row))
        self.bval[i] = row[self.best[i]]
        a = np.where(self.alive)[0]
        a = a[a != i]
        col = self.score[a, i]
        better = (col > self.bval[a]) | ((col == self.bval[a]) & (i < self.best[a]))
        stale = np.isin(self.best[a], (i, j)) & ~better   # partner gone or its score changed
        self.best[a[better]] = i
        self.bval[a[better]] = col[better]
        r = a[stale]
        if len(r):
            self.best[r] = np.argmax(self.score[r], axis=1)
            self.bval[r] = self.score[r, self.best[r]]

    def run(self, target):
        groups = {i: [i] for i in range(len(self.size))}
        while self.alive.sum() > target:
            r = int(np.argmax(self.bval))
            if not np.isfinite(self.bval[r]):
                raise RuntimeError(f"no feasible merge left with {self.alive.sum()} items > target {target}")
            i, j = sorted((r, int(self.best[r])))
            self.merge(i, j)
            groups[i] += groups.pop(j)
        return [groups[i] for i in sorted(groups)]


# ---------------------------------------------------------------- per snapshot

def build_snapshot(tkh, snap, budgets, params, hubset=None):
    """Concept-node partitions [level 0 .. K-1] (level 0 coarsest) for one snapshot, plus diagnostics.

    hubset: optional fixed hub set (a null model passes the real snapshot's hubs); default: computed here.
    Returns (levels, graph, diag): graph = (items, B, w, edge_ids, relations), the clustering hypergraph."""
    items = concept_nodes(tkh, snap)
    n = len(items)
    if hubset is None:
        hubset = hubs(tkh, snap, params.hub_frac)
    B, w, edge_ids, rels = incidence(tkh, snap, items, hubset, params.edge_weight)
    names = sm.names(tkh)
    Z = centred_lsa([names[v] for v in items], params.lsa_dim)
    Xfine = B.toarray()

    groups = [[i] for i in range(n)]  # items of the level being built, as fine indices
    levels, level_diag = [None] * len(budgets), [None] * len(budgets)
    for k in reversed(range(len(budgets))):
        target = min(budgets[k], len(groups))
        cap = params.rho * n / budgets[k] if math.isfinite(params.rho) else math.inf
        P = csr_matrix((np.ones(n), (np.concatenate([[g] * len(m) for g, m in enumerate(groups)]).astype(int),
                                     np.concatenate(groups))), shape=(len(groups), n))
        lvl = _Level(P @ Z, np.asarray(P.sum(axis=1)).ravel(), P @ Xfine, w, params.alpha, cap)
        merged = lvl.run(target)
        groups = [sorted(i for item in grp for i in groups[item]) for grp in merged]
        levels[k] = {g: {items[i] for i in mem} for g, mem in enumerate(groups)}
        sizes = [len(m) for m in groups]
        level_diag[k] = {"budget": budgets[k], "super_nodes": len(groups), "cap": round(cap, 2) if math.isfinite(cap) else "inf",
                         "max_size": max(sizes), "singletons": sizes.count(1), **lvl.stats}
    diag = {"n_concept": n, "n_edges": len(edge_ids), "hub_threshold_papers": hub_threshold(snap, params.hub_frac),
            "hubs": sorted(hubset), "levels": level_diag}
    return levels, (items, B, w, edge_ids, rels), diag


# ---------------------------------------------------------------- anchoring and full build

def anchors(tkh, snap, concept):
    """{non-concept node: concept node whose super-node it joins} for one snapshot."""
    e = snap.edges
    ntype = tkh.nodes["type"].to_dict()
    year = tkh.articles["year"].to_dict()
    presented = {a: m[1] for m, r, a in zip(e["members"], e["relation_type"], e["article_id"]) if r == "presents"}
    art_node = {}
    if "node_id" in tkh.articles:
        art_node = {nid: a for a, nid in tkh.articles["node_id"].items() if isinstance(nid, str)}
    order = lambda arts: sorted(arts, key=lambda a: (year[a], str(a)))  # noqa: E731
    papers_of = {}
    for m, a in zip(e["members"], e["article_id"]):
        for v in m:
            papers_of.setdefault(v, set()).add(a)
    claim_method, citer = {}, {}
    for m, r, a in zip(e["members"], e["relation_type"], e["article_id"]):
        if r == "claims":
            meth = [v for v in m if ntype[v] == "method" and v in concept]
            for v in m:
                if ntype[v] == "claim":
                    claim_method.setdefault(v, meth[0] if meth else presented.get(a))
        elif r == "cites":
            for v in m[1:]:
                citer.setdefault(v, set()).add(a)
    out = {}
    for v in sorted(snap.node_ids - set(concept)):
        t = ntype[v]
        if t == "claim" and claim_method.get(v):
            out[v] = claim_method[v]
            continue
        if t == "cited_work" and v in citer:
            arts = citer[v]
        elif t == "article" and v in art_node:
            arts = {art_node[v]}
        else:
            arts = (set(tkh.nodes.at[v, "prov_articles"]) & snap.articles) | papers_of.get(v, set())
        cand = [presented[a] for a in order(arts) if a in presented and presented[a] in concept]
        if not cand:
            raise ValueError(f"no anchor for {v} ({t}) in snapshot <= {snap.cutoff}")
        out[v] = cand[0]
    return out


def build(tkh, cutoffs, budgets, params, hubsets=None):
    """Full build. Returns (parts, graphs, diag):
    parts[cutoff] = [ {key: set(all members)} per level ] (level 0 coarsest); graphs[cutoff] = the clustering
    hypergraph plus the concept-only levels (for the T4 records); diag[cutoff] = run diagnostics."""
    parts, graphs, diag = {}, {}, {}
    for snap in make_snapshots(tkh, cutoffs):
        levels, graph, d = build_snapshot(tkh, snap, budgets, params, (hubsets or {}).get(snap.cutoff))
        anc = anchors(tkh, snap, set(graph[0]))
        full = []
        for lv in levels:
            where = {v: g for g, mem in lv.items() for v in mem}
            groups = {g: set(mem) for g, mem in lv.items()}
            for v, a in anc.items():
                groups[where[a]].add(v)
            full.append(groups)
        parts[snap.cutoff], graphs[snap.cutoff] = full, (levels, *graph)
        diag[snap.cutoff] = {**d, "n_anchored": len(anc)}
    return parts, graphs, diag
