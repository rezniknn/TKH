"""Extrinsic task: coarse-to-fine drill-down retrieval vs a flat baseline, scored on hit-rate / steps-to-target.

Task (E4): for each ground-truth question (type A, with at least one expected method that
matches a concept node by name), find the expected methods among the snapshot's concept
nodes. Every method pays the same unit cost per thing a user would read:
- `hierarchy_search`: best-first drill-down. Profiles are the L2-normalised centroid of
  the members' word TF-IDF name vectors; the root super-nodes are read first (cost 1
  each), then the best-scoring unopened super-node is opened: its children's profiles are
  read (cost 1 each), and opening a finest-level super-node reads all its concept nodes
  (cost 1 each, in order of their own score), which retrieves them. A topic is read as a
  whole: a target with no lexical match of its own is still found once its super-node
  is opened.
- `flat_lexical`: all concept nodes ranked by the cosine of their name vector to the query
  (cost = rank).
- `ppr`: personalised PageRank (damping 0.85) on the clique expansion (w_e = 1/(|e|-1))
  of the same clustering hypergraph the method uses, personalised on the lexical scores
  (cost = rank). This is the structure-aware baseline.
- `degree`: a query-INDEPENDENT popularity ranking (number of clustering edges a node is
  in). It shows how much of a ranking's success comes from the targets being popular.
Scores per question: cost to the first target, recall@B and wrong_domain@B (wrong-domain
names retrieved within budget B). Ranked baselines are scored by their EXPECTED value
under uniformly random tie-breaking (`expected_score`): most questions have no lexical
match to any target, and breaking the resulting ~4k-way tie by node id would make the flat
cost an artefact of id order. The drill-down is scored the same way: its metrics are the
mean over `tie_draws` seeded runs in which ties between super-nodes and inside an opened
leaf are broken uniformly at random (`hierarchy_expected`).
"""

import heapq

import numpy as np
from scipy.sparse import diags

from tkh import semantic as sm
from tkh.coarsen import concept_nodes, hubs, incidence
from tkh.io import snapshot


class Index:
    """Name vectors of one snapshot's concept nodes and the query vectoriser."""

    def __init__(self, tkh, cutoff):
        self.snap = snapshot(tkh, cutoff)
        self.items = concept_nodes(tkh, self.snap)
        self.pos = {v: i for i, v in enumerate(self.items)}
        names = sm.names(tkh)
        self.X, self.vec = sm.vectorize([names[v] for v in self.items], "word")
        self.X = self.X.tocsr()

    def query(self, text):
        q = self.vec.transform([text])
        return np.asarray((self.X @ q.T).toarray()).ravel()


def _order(index, x):
    return [index.items[i] for i in sorted(range(len(x)), key=lambda i: (-x[i], index.items[i]))]


def flat_lexical(index, text):
    return _order(index, index.query(text))


def ppr(index, tkh, text, hub_frac=0.2, damping=0.85, iters=100):
    return _order(index, ppr_scores(index, tkh, text, hub_frac, damping, iters))


def degree_scores(index, tkh, hub_frac=0.2):
    B, _, _, _ = incidence(tkh, index.snap, index.items, hubs(tkh, index.snap, hub_frac))
    return np.asarray(B.sum(axis=1)).ravel()


def ppr_scores(index, tkh, text, hub_frac=0.2, damping=0.85, iters=100):
    s = np.clip(index.query(text), 0, None)
    if s.sum() == 0:
        return index.query(text)
    B, w, _, _ = incidence(tkh, index.snap, index.items, hubs(tkh, index.snap, hub_frac))
    A = (B @ diags(w) @ B.T).tocsr()
    A.setdiag(0)
    A.eliminate_zeros()
    deg = np.asarray(A.sum(axis=1)).ravel()
    T = diags(np.divide(1.0, deg, out=np.zeros_like(deg), where=deg > 0)) @ A  # row-stochastic where deg > 0
    p0 = s / s.sum()
    x = p0.copy()
    for _ in range(iters):
        nxt = damping * (T.T @ x) + (1 - damping) * p0
        nxt += damping * x[deg == 0].sum() * p0  # dangling mass back to the personalisation
        if np.abs(nxt - x).sum() < 1e-12:
            x = nxt
            break
        x = nxt
    return x


def expected_score(index, scores, targets, wrong, budgets=(50, 200)):
    """Expected cost to the first target, recall@B and wrong@B of a ranking by `scores` with
    uniformly random tie-breaking (rank of an item with score x is uniform on g_x+1 .. g_x+b_x)."""
    x = np.round(np.asarray(scores, float), 12)
    srt = np.sort(x)
    gt = lambda v: len(x) - np.searchsorted(srt, v, "right")  # noqa: E731  items strictly above
    eq = lambda v: np.searchsorted(srt, v, "right") - np.searchsorted(srt, v, "left")  # noqa: E731
    ti = [index.pos[v] for v in targets]
    out = {"n_targets": len(targets)}
    if ti:
        top = max(x[i] for i in ti)
        t = sum(x[i] == top for i in ti)
        out["first_cost"] = float(gt(top) + (eq(top) + 1) / (t + 1))
    else:
        out["first_cost"] = None
    p_in = lambda i, b: float(np.clip((b - gt(x[i])) / eq(x[i]), 0, 1))  # noqa: E731
    for b in budgets:
        out[f"recall@{b}"] = float(np.mean([p_in(i, b) for i in ti])) if ti else None
        out[f"wrong@{b}"] = float(sum(p_in(index.pos[v], b) for v in wrong))
    return out


def _profiles(index, members):
    rows = [index.pos[v] for v in members if v in index.pos]
    if not rows:
        return None
    c = np.asarray(index.X[rows].mean(axis=0)).ravel()
    n = np.linalg.norm(c)
    return c / n if n > 0 else c


class Tree:
    """Query-independent part of the drill-down: children, member lists and profile vectors per super-node."""

    def __init__(self, index, levels):
        self.index, self.levels = index, levels
        self.keys = [sorted(lv, key=lambda g: min(lv[g])) for lv in levels]
        self.children = []
        for k in range(len(levels) - 1):
            owner = {v: g for g, mem in levels[k].items() for v in mem}
            ch = {}
            for g in self.keys[k + 1]:
                ch.setdefault(owner[next(iter(levels[k + 1][g]))], []).append(g)
            self.children.append(ch)
        self.prof = []
        for k, lv in enumerate(levels):
            P = [_profiles(index, lv[g]) for g in self.keys[k]]
            dim = index.X.shape[1]
            self.prof.append({g: (p if p is not None else np.zeros(dim)) for g, p in zip(self.keys[k], P)})
        self.members = {g: sorted(u for u in levels[-1][g] if u in index.pos) for g in self.keys[-1]}
        self.n_groups = sum(len(lv) for lv in levels)


def hierarchy_search(index, levels, text, rng=None, tree=None, trace=None):
    """(retrieved concept nodes in order, cost at which each was retrieved) for a laminar hierarchy.
    levels: [ {key: set(members)} per level ] (level 0 coarsest), concept nodes only.
    rng=None breaks score ties by node id; with a numpy Generator, ties (between super-nodes and
    inside an opened leaf) are broken uniformly at random.
    trace: optional list that receives (cost, action, level, super-node, score) for every super-node
    read ("read") and opened ("open"), for inspection (notebooks/05)."""
    tree = tree or Tree(index, levels)
    q = index.vec.transform([text]).toarray().ravel()
    tie = (lambda: float(rng.random())) if rng is not None else (lambda: 0.0)  # noqa: E731
    cost, heap, order, costs = 0, [], [], []

    def push_group(k, g):
        nonlocal cost
        cost += 1
        sc = round(float(tree.prof[k][g] @ q), 12)
        heapq.heappush(heap, (-sc, tie(), min(levels[k][g]), k, g))
        if trace is not None:
            trace.append((cost, "read", k, g, sc))

    for g in tree.keys[0]:
        push_group(0, g)
    while heap:
        negsc, _, _, k, g = heapq.heappop(heap)
        if trace is not None:
            trace.append((cost, "open", k, g, -negsc))
        if k < len(levels) - 1:
            for c in tree.children[k].get(g, []):
                push_group(k + 1, c)
            continue
        mem = tree.members[g]
        sc = np.round(index.X[[index.pos[u] for u in mem]] @ q, 12) if mem else []
        for u, _, _ in sorted(((u, x, tie()) for u, x in zip(mem, sc)), key=lambda t: (-t[1], t[2], t[0])):
            cost += 1
            order.append(u)
            costs.append(cost)
    return order, costs


def hierarchy_expected(index, tree, text, targets, wrong, budgets=(50, 200), draws=20, seed=0):
    """Mean over `draws` uniformly random tie-breaks of the drill-down scores (as the ranked baselines get
    their expectation under random ties)."""
    rng = np.random.default_rng(seed)
    runs = [score(*hierarchy_search(index, tree.levels, text, rng, tree), targets, wrong, budgets) for _ in range(draws)]
    out = {"n_targets": len(targets), "tie_draws": draws}
    for k in runs[0]:
        if k == "n_targets":
            continue
        vals = [r[k] for r in runs]
        out[k] = None if any(v is None for v in vals) else float(np.mean(vals))
    return out


def score(order, costs, targets, wrong, budgets=(50, 200)):
    """cost to first target, recall@B, wrong_domain@B from a retrieval order and its costs."""
    costs = costs if costs is not None else list(range(1, len(order) + 1))
    first = next((c for v, c in zip(order, costs) if v in targets), None)
    out = {"first_cost": first, "n_targets": len(targets)}
    for b in budgets:
        got = {v for v, c in zip(order, costs) if c <= b}
        out[f"recall@{b}"] = len(got & targets) / len(targets) if targets else None
        out[f"wrong@{b}"] = len(got & wrong)
    return out


def evaluate(tkh, cutoff, levels, questions, targets, budgets=(50, 200), baselines=True, hub_frac=0.2, index=None,
             tie_draws=20, seed=0):
    """Rows per question for 'hierarchy' (and 'flat', 'ppr', 'degree' when baselines=True)."""
    index = index or Index(tkh, cutoff)
    tree = Tree(index, levels)
    rows = []
    for q, t in sorted(targets.items()):
        tg = {v for ids in t["expected"].values() for v in ids if v in index.pos}
        wr = {v for ids in t["wrong_domain"].values() for v in ids if v in index.pos} - tg
        if not tg or q not in questions:
            continue
        text = questions[q]
        rows.append({"question": q, "method": "hierarchy",
                     **hierarchy_expected(index, tree, text, tg, wr, budgets, tie_draws, seed)})
        if baselines:
            for m, sc in (("flat", index.query(text)), ("ppr", ppr_scores(index, tkh, text, hub_frac)),
                          ("degree", degree_scores(index, tkh, hub_frac))):
                rows.append({"question": q, "method": m, **expected_score(index, sc, tg, wr, budgets)})
    return rows


def load_questions(path):
    import pandas as pd
    df = pd.read_csv(path, sep=";")
    return dict(zip(df["question_id"], df["question"]))


def penalised_first_cost(rows, max_cost):
    """first_cost with misses set to max_cost + 1, where max_cost bounds every method's cost (all concept nodes
    plus all super-node profiles), so that every question contributes to the paired tests."""
    return [r["first_cost"] if r["first_cost"] is not None else max_cost + 1 for r in rows]


