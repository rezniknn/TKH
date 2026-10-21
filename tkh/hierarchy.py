"""T2: builds the laminar multi-level hierarchy P_0..P_K per snapshot, combining structural and semantic signal; enforces P1 by construction and P2 budgets as hard limits.

SHAC-T (Semantic-Hypergraph Agglomerative Coarsening with Temporal coupling); the formal
statement is docs/formal_statement.md. Per snapshot t and level k (finest first), starting
from the concept nodes as singletons and then from the level-(k+1) super-nodes:

  repeat: merge the feasible pair (A, B) with the highest score s_t(A, B)
  until exactly min(N_k, #items) super-nodes remain

  s(A, B)   = alpha * F_S(S(A, B)) + (1 - alpha) * F_H(H(A, B))
  s_t(A, B) = (1 - gamma) * s(A, B) + gamma * P(A, B)    if A and B both hold old nodes, else s(A, B)

  S(A, B) = mean_A . mean_B of centred, L2-normalised char-n-gram LSA vectors of the member
            names (= average pairwise cosine)
  H(A, B) = sum_{e containing A and B} w_e / sqrt(d_A d_B),  d_A = sum_{e containing A} w_e,
            on the CURRENT collapsed incidence (tkh/coarsen.py): the degree-normalised
            reduction of the weighted connectivity cut sum_e w_e (lambda_e - 1) when A, B merge
            ("projection" variant: average over member pairs of the singleton values instead)
  P(A, B) = fraction of (old a in A, old b in B) pairs co-clustered at the same level in
            the previous snapshot
  F_X     = mid-rank empirical CDF of X over all item pairs at the start of the level
  feasible: |A| + |B| <= rho * n_t / N_k  (concept nodes; rho >= 2 always leaves a feasible pair)

freeze=True is a reference, not the method: old nodes keep their previous same-level groups
(pre-merged, and two such groups never merge), so only new nodes are placed (E2, P5). It runs
without the size cap: the frozen sizes are fixed, so the feasibility lemma does not apply.

Non-concept nodes are anchored (`anchors`) and inherit their anchor's super-node.
"""

from dataclasses import dataclass, asdict
import math

import numpy as np
from scipy.sparse import csr_matrix
from sklearn.decomposition import TruncatedSVD

from tkh import semantic as sm
from tkh.coarsen import concept_nodes, hubs, incidence
from tkh.io import make_snapshots


@dataclass(frozen=True)
class Params:
    alpha: float = 0.5
    gamma: float = 0.5
    rho: float = 2.0
    structure: str = "native"     # "native" | "projection"
    lsa_dim: int = 100
    hub_frac: float = 0.2
    freeze: bool = False          # reference variant: old assignments frozen

    @classmethod
    def from_config(cls, d):
        d = dict(d or {})
        if isinstance(d.get("freeze"), str):
            d["freeze"] = d["freeze"].lower() in ("1", "true", "yes")
        if "rho" in d:
            d["rho"] = float("inf") if str(d["rho"]).lower() in ("inf", "none") else float(d["rho"])
        p = cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})
        if p.structure not in ("native", "projection"):
            raise ValueError(f"structure must be 'native' or 'projection', got {p.structure!r}")
        if not (0 <= p.alpha <= 1 and 0 <= p.gamma <= 1) or p.rho < 2:
            raise ValueError(f"need 0<=alpha<=1, 0<=gamma<=1, rho>=2: {p}")
        return p

    def cid(self):
        r = "inf" if math.isinf(self.rho) else f"{self.rho:g}"
        cid = f"a{self.alpha:g}_g{self.gamma:g}_r{r}_{self.structure}_d{self.lsa_dim}_h{self.hub_frac:g}"
        return cid + ("_freeze" if self.freeze else "")

    def as_dict(self):
        d = asdict(self)
        d["rho"] = "inf" if math.isinf(self.rho) else self.rho
        return d


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
    """F(x) = (#{v < x} + #{v <= x}) / (2N) over a fixed sample of values (mid-rank empirical CDF)."""

    def __init__(self, values):
        self.u, inv, cnt = np.unique(values, return_inverse=True, return_counts=True)
        self.cum = np.concatenate([[0], np.cumsum(cnt)])
        self.n = len(values)
        self.at_sample = (self.cum[inv] + self.cum[inv + 1]) / (2.0 * self.n)  # F of each sample value

    def __call__(self, x):
        x = np.asarray(x, dtype=float)
        flat = x.ravel()
        order = np.argsort(flat, kind="stable")  # sorted queries make the binary searches ~3x faster
        xs = flat[order]
        out = np.empty_like(flat)
        out[order] = (self.cum[np.searchsorted(self.u, xs, "left")] + self.cum[np.searchsorted(self.u, xs, "right")]) / (2.0 * self.n)
        return out.reshape(x.shape)


def _sym_from_upper(n, iu, vals):
    out = np.zeros((n, n))
    out[iu] = vals
    out[(iu[1], iu[0])] = vals
    return out


# ---------------------------------------------------------------- engine

class _Level:
    """Greedy constrained agglomeration of `n` items down to `target` items."""

    def __init__(self, sem, size, X, w, Wfine_sum, M, old, params, cap, frozen=None):
        self.p, self.cap = params, cap
        self.frozen = frozen                         # freeze reference: items holding old nodes (never merged together)
        self.sem = sem.astype(np.float64)            # sum of member vectors
        self.size = size.astype(np.float64)          # concept nodes per item
        self.X = X.astype(np.float64)                # native: presence; (dense n x E)
        self.w = w.astype(np.float64)
        self.W = Wfine_sum                           # projection: summed singleton H between items (n x n) or None
        self.M = M                                   # temporal: counts of old members per previous cluster (n x K') or None
        self.old = old                               # old members per item
        self.alive = np.ones(len(size), bool)
        n = len(size)
        self.d = self.X @ self.w
        iu = np.triu_indices(n, 1)
        S, H = self._S_all(), self._H_all()
        if n > 1:
            self.FS, self.FH = _MidRankCDF(S[iu]), _MidRankCDF(H[iu])
            fs, fh = _sym_from_upper(n, iu, self.FS.at_sample), _sym_from_upper(n, iu, self.FH.at_sample)
        else:
            self.FS = self.FH = (lambda x: np.zeros_like(np.asarray(x, float)))
            fs = fh = np.zeros((n, n))
        del S, H
        self.score = self._combine(None, None, np.arange(n), fs=fs, fh=fh)
        np.fill_diagonal(self.score, -np.inf)
        self._mask_all()
        self.best = np.argmax(self.score, axis=1)
        self.bval = self.score[np.arange(n), self.best]

    # signal values for item rows `r` against all items
    def _S_all(self, r=None):
        mean = self.sem / self.size[:, None]
        return (mean if r is None else mean[r]) @ mean.T

    def _H_all(self, r=None):
        if self.p.structure == "projection":
            W = self.W if r is None else self.W[r]
            sz = self.size if r is None else self.size[r]
            return W / np.outer(sz, self.size)
        Xr = self.X if r is None else self.X[r]
        num = (Xr * self.w) @ self.X.T
        d = self.d
        dr = d if r is None else d[r]
        den = np.sqrt(np.outer(dr, d))
        return np.divide(num, den, out=np.zeros_like(num), where=den > 0)

    def _P_all(self, r=None):
        if self.M is None:
            return None
        num = (self.M if r is None else self.M[r]) @ self.M.T
        o = self.old if r is None else self.old[r]
        den = np.outer(o, self.old)
        return np.divide(num, den, out=np.full_like(num, np.nan, dtype=float), where=den > 0)

    def _combine(self, S, H, rows, fs=None, fh=None):
        a, g = self.p.alpha, self.p.gamma
        fs = self.FS(S) if fs is None else fs
        fh = self.FH(H) if fh is None else fh
        s = a * fs + (1 - a) * fh
        if g > 0 and self.M is not None:
            P = self._P_all(rows if len(rows) < len(self.size) else None)
            s = np.where(np.isnan(P), s, (1 - g) * s + g * np.nan_to_num(P))
        return np.round(s, 9)

    def _mask_all(self):
        if math.isfinite(self.cap):
            self.score[np.add.outer(self.size, self.size) > self.cap] = -np.inf
        self.score[:, ~self.alive] = -np.inf
        self.score[~self.alive, :] = -np.inf
        if self.frozen is not None:
            self.score[np.outer(self.frozen, self.frozen)] = -np.inf

    def _row(self, i):
        S, H = self._S_all([i]), self._H_all([i])
        row = self._combine(S, H, np.array([i]))[0]
        row[i] = -np.inf
        row[~self.alive] = -np.inf
        if math.isfinite(self.cap):
            row[self.size[i] + self.size > self.cap] = -np.inf
        if self.frozen is not None and self.frozen[i]:
            row[self.frozen] = -np.inf
        return row

    def merge(self, i, j):
        """Merge item j into item i (i < j)."""
        self.sem[i] += self.sem[j]
        self.size[i] += self.size[j]
        if self.p.structure == "projection":
            self.W[i, :] += self.W[j, :]
            self.W[:, i] += self.W[:, j]
        else:
            self.X[i] = np.maximum(self.X[i], self.X[j])  # presence on the collapsed incidence
            self.d[i] = self.X[i] @ self.w
        if self.M is not None:
            self.M[i] += self.M[j]
            self.old[i] += self.old[j]
        if self.frozen is not None:
            self.frozen[i] |= self.frozen[j]
        self.alive[j] = False
        self.score[j, :] = -np.inf
        self.score[:, j] = -np.inf
        row = self._row(i)
        self.score[i, :] = row
        self.score[:, i] = row
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

def build_snapshot(tkh, snap, budgets, params, prev=None, text_perm=None, return_diag=False, hub_set=None):
    """Concept-node partitions [level 0 .. K-1] (level 0 coarsest) for one snapshot.

    prev: previous snapshot's concept partitions in the same format (for gamma), or None.
    text_perm: optional {node: node whose name text to use} (semantic null).
    hub_set: optional fixed hub set (structure nulls use the REAL graph's hubs, so that model and
        null cluster the same nodes structurally); default: hubs of `snap` at params.hub_frac.
    """
    items = concept_nodes(tkh, snap)
    n = len(items)
    hubset = set(hub_set) if hub_set is not None else hubs(tkh, snap, params.hub_frac)
    B, w, edge_ids, rels = incidence(tkh, snap, items, hubset)
    names = sm.names(tkh)
    texts = [names[text_perm.get(v, v) if text_perm else v] for v in items]
    Z = centred_lsa(texts, params.lsa_dim)
    Xfine = B.toarray()
    Wfine = None
    if params.structure == "projection":
        Xw = Xfine * w
        num = Xw @ Xfine.T
        d = Xfine @ w
        den = np.sqrt(np.outer(d, d))
        Wfine = np.divide(num, den, out=np.zeros_like(num), where=den > 0)
        np.fill_diagonal(Wfine, 0.0)
    pos = {v: i for i, v in enumerate(items)}

    groups = [[i] for i in range(n)]  # items of the level being built, as fine indices
    levels = [None] * len(budgets)
    for k in reversed(range(len(budgets))):
        frozen = None
        if prev is not None and params.freeze:
            groups, frozen = _freeze_groups(groups, items, prev[k])
        target = min(budgets[k], len(groups))
        cap = params.rho * n / budgets[k] if math.isfinite(params.rho) else math.inf
        if frozen is not None:
            cap = math.inf  # frozen groups fix the sizes, so the feasibility lemma no longer applies
        P = csr_matrix((np.ones(n), (np.concatenate([[g] * len(m) for g, m in enumerate(groups)]).astype(int),
                                     np.concatenate(groups))), shape=(len(groups), n))
        sem = P @ Z
        size = np.asarray(P.sum(axis=1)).ravel()
        X = (P @ Xfine > 0).astype(float)
        W = (P @ Wfine @ P.T) if Wfine is not None else None
        if W is not None:
            np.fill_diagonal(W, 0.0)
        M = old = None
        if prev is not None and params.gamma > 0 and not params.freeze:
            prev_of = {v: c for c, mem in prev[k].items() for v in mem if v in pos}
            keys = sorted(set(prev_of.values()), key=str)
            kidx = {c: j for j, c in enumerate(keys)}
            M = np.zeros((len(groups), max(len(keys), 1)))
            for g, mem in enumerate(groups):
                for i in mem:
                    c = prev_of.get(items[i])
                    if c is not None:
                        M[g, kidx[c]] += 1
            old = M.sum(axis=1)
        lvl = _Level(sem, size, X, w, W, M, old, params, cap, frozen)
        merged = lvl.run(target)
        groups = [sorted(i for item in grp for i in groups[item]) for grp in merged]
        levels[k] = {g: {items[i] for i in mem} for g, mem in enumerate(groups)}
    if return_diag:
        return levels, {"n_concept": n, "hubs": sorted(hubset), "n_edges": len(edge_ids)}
    return levels


def _freeze_groups(groups, items, prev_level):
    """Pre-merge the groups whose old nodes share a previous cluster; returns (groups, frozen mask).
    Laminarity of the previous hierarchy guarantees each group's old nodes lie in one previous cluster."""
    prev_of = {v: c for c, mem in prev_level.items() for v in mem}
    by_prev, free = {}, []
    for g in groups:
        cs = {prev_of[items[i]] for i in g if items[i] in prev_of}
        if len(cs) > 1:
            raise ValueError(f"group spans previous clusters {cs}")
        (by_prev.setdefault(cs.pop(), []).extend(g)) if cs else free.append(g)
    old = [sorted(m) for _, m in sorted(by_prev.items(), key=lambda kv: min(kv[1]))]
    merged = sorted(old + free, key=min)
    return merged, np.array([min(g) in {min(o) for o in old} for g in merged])


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
    claim_method = {}
    citer = {}
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


def build(tkh, cutoffs, budgets, params, text_perm=None, return_diag=False, hub_sets=None):
    """{cutoff: [ {key: set(all members)} per level ]} (level 0 coarsest), plus optional diagnostics.

    The same signature serves perturbation stability (build(tkh_perturbed)) and the nulls.
    """
    out, diag, prev = {}, {}, None
    for snap in make_snapshots(tkh, cutoffs):
        concept_levels, d = build_snapshot(tkh, snap, budgets, params, prev=prev, text_perm=text_perm, return_diag=True,
                                           hub_set=None if hub_sets is None else hub_sets[snap.cutoff])
        concept = set().union(*concept_levels[-1].values()) if concept_levels else set()
        anc = anchors(tkh, snap, concept)
        full = []
        for lv in concept_levels:
            where = {v: g for g, mem in lv.items() for v in mem}
            groups = {g: set(mem) for g, mem in lv.items()}
            for v, a in anc.items():
                groups[where[a]].add(v)
            full.append(groups)
        out[snap.cutoff] = full
        diag[snap.cutoff] = {**d, "n_anchored": len(anc)}
        prev = concept_levels
    return (out, diag) if return_diag else out


def concept_only(parts, tkh):
    """Restrict full partitions to concept nodes (metrics are computed on concept nodes only)."""
    t = tkh.nodes["type"]
    return {c: [{g: {v for v in mem if t.at[v] in sm.CONCEPT_TYPES} for g, mem in lv.items()} for lv in levels]
            for c, levels in parts.items()}
