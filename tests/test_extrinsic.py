"""Tests for E4 (tkh/evaluate/extrinsic.py): drill-down cost accounting, flat cost = rank, PPR sanity."""

from pathlib import Path
from types import SimpleNamespace
import sys

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from tkh import semantic as sm  # noqa: E402
from tkh.evaluate.extrinsic import flat_lexical, hierarchy_search, score  # noqa: E402


def toy_index(names):
    items = sorted(names)
    X, vec = sm.vectorize([names[v] for v in items], "word")
    idx = SimpleNamespace(items=items, pos={v: i for i, v in enumerate(items)}, X=X.tocsr(), vec=vec)
    idx.query = lambda text: np.asarray((idx.X @ vec.transform([text]).T).toarray()).ravel()
    return idx


NAMES = {"a": "graph neural network", "b": "graph kernel", "c": "phonon spectrum", "d": "phonon dispersion",
         "e": "VGNN", "f": "random forest"}
LEVELS = [{0: {"a", "b", "f"}, 1: {"c", "d", "e"}},
          {0: {"a", "b"}, 1: {"f"}, 2: {"c", "e"}, 3: {"d"}}]


def test_best_first_cost_on_toy_tree():
    idx = toy_index(NAMES)
    order, costs = hierarchy_search(idx, LEVELS, "phonon spectrum prediction")
    # read 2 roots (2), open root 1 -> read children {c,e} and {d} (4); open {c,e}: read c (5), e (6)
    assert order[:2] == ["c", "e"] and costs[:2] == [5, 6]
    r = score(order, costs, {"e"}, {"f"}, budgets=(6,))
    assert r["first_cost"] == 6 and r["recall@6"] == 1.0 and r["wrong@6"] == 0
    assert sorted(order) == sorted(NAMES)             # every node is eventually retrieved
    assert costs == sorted(costs)


def test_flat_cost_equals_rank():
    idx = toy_index(NAMES)
    order = flat_lexical(idx, "graph network")
    assert order[0] == "a"
    r = score(order, None, {"b"}, set(), budgets=(1, 2))
    assert r["first_cost"] == order.index("b") + 1 and r["recall@1"] == 0.0 and r["recall@2"] == 1.0


def test_a_target_without_lexical_match_is_found_by_opening_its_topic():
    idx = toy_index(NAMES)
    flat = flat_lexical(idx, "phonon spectrum")
    order, costs = hierarchy_search(idx, LEVELS, "phonon spectrum")
    assert flat.index("e") > flat.index("d")           # flat ranking puts the unmatched target after both phonon nodes
    assert costs[order.index("e")] == 6                 # the drill-down reads it as part of the opened topic


def test_expected_score_under_random_ties():
    from tkh.evaluate.extrinsic import expected_score
    idx = toy_index(NAMES)
    scores = np.zeros(len(idx.items))
    scores[idx.pos["a"]] = 1.0                          # a first, then a 5-way tie
    r = expected_score(idx, scores, {"e"}, {"f"}, budgets=(1, 2, 6))
    assert r["first_cost"] == pytest.approx(1 + (5 + 1) / 2)   # uniform position in the 5-way tie
    assert r["recall@1"] == 0 and r["recall@2"] == pytest.approx(1 / 5) and r["recall@6"] == 1
    assert r["wrong@2"] == pytest.approx(1 / 5)
    r2 = expected_score(idx, scores, {"e", "f"}, set(), budgets=(2,))
    assert r2["first_cost"] == pytest.approx(1 + 6 / 3)          # first of 2 targets in a tie of 5
