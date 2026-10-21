"""Tests for tkh/evaluate/stability.py: the ARI implementation, intervals, and the two T6 stability measures."""

from pathlib import Path
import sys

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from tkh.config import load_config  # noqa: E402
from tkh.evaluate.stability import (ari, cross_snapshot_stability, perturbation_stability,  # noqa: E402
                                    permutation_p, remove_edges, subsample_ari, t_interval)
from tkh.io import load  # noqa: E402


@pytest.mark.parametrize("a,b,expected", [  # reference values from scikit-learn's adjusted_rand_score docs
    ([0, 0, 1, 1], [0, 0, 1, 1], 1.0),
    ([0, 0, 1, 1], [1, 1, 0, 0], 1.0),
    ([0, 0, 1, 2], [0, 0, 1, 1], 0.5714285714285715),
    ([0, 0, 1, 1], [0, 0, 1, 2], 0.5714285714285715),
    ([0, 0, 0, 0], [0, 1, 2, 3], 0.0),
    ([0, 0, 1, 1], [0, 1, 0, 1], -0.5),
])
def test_ari_reference_values(a, b, expected):
    assert ari(a, b) == pytest.approx(expected)


def test_ari_is_symmetric_and_label_invariant():
    rng = np.random.default_rng(0)
    a, b = rng.integers(0, 5, 200), rng.integers(0, 7, 200)
    assert ari(a, b) == pytest.approx(ari(b, a))
    assert ari(a, b) == pytest.approx(ari(a * 3 + 11, np.array([f"x{v}" for v in b])))


def test_ari_of_independent_random_labels_is_near_zero():
    rng = np.random.default_rng(1)
    vals = [ari(rng.integers(0, 10, 2000), rng.integers(0, 10, 2000)) for _ in range(50)]
    assert abs(np.mean(vals)) < 0.005


def test_t_interval_contains_mean_and_uses_student_t():
    r = t_interval([1.0, 2.0, 3.0, 4.0, 5.0])
    assert r["lo"] < r["mean"] == 3.0 < r["hi"]
    assert r["hi"] - r["mean"] == pytest.approx(2.776445 * np.std([1, 2, 3, 4, 5], ddof=1) / np.sqrt(5), rel=1e-5)


def test_permutation_p_detects_identity_and_not_noise():
    rng = np.random.default_rng(2)
    a = rng.integers(0, 8, 500)
    assert permutation_p(a, a, n_perm=199) == pytest.approx(1 / 200)
    assert permutation_p(a, rng.integers(0, 8, 500), n_perm=199) > 0.01
    lo, hi = subsample_ari(a, a, n_rep=50)
    assert lo == hi == 1.0


@pytest.fixture(scope="module")
def fixture_graph():
    cfg = load_config(ROOT / "tests" / "fixtures" / "_input" / "config.toml")
    return cfg, load(cfg)


def test_remove_edges_removes_ten_percent_of_every_period_and_keeps_nodes():
    cfg = load_config()
    tkh = load(cfg)
    pert, dropped = remove_edges(tkh, 0.10, seed=0, cutoffs=cfg.cutoffs)
    y = tkh.edges["article_year"]
    for lo, hi in zip([-1] + list(cfg.cutoffs), cfg.cutoffs):
        period = set(y.index[(y > lo) & (y <= hi)])
        assert len(period & set(dropped)) == round(0.10 * len(period))
    for c in cfg.cutoffs:  # every cumulative snapshot loses ~10%
        n = int((y <= c).sum())
        assert abs(len(set(y.index[y <= c]) & set(dropped)) / n - 0.10) < 0.01
    assert len(pert.edges) == len(tkh.edges) - len(dropped)
    assert set(dropped).isdisjoint(pert.edges.index)
    assert pert.nodes is tkh.nodes  # node set and entry years untouched
    assert remove_edges(tkh, 0.10, 0, cfg.cutoffs)[1] == dropped and remove_edges(tkh, 0.10, 1, cfg.cutoffs)[1] != dropped


def test_perturbation_with_a_deterministic_builder_ignoring_edges_gives_ari_one(fixture_graph):
    cfg, tkh = fixture_graph
    from tkh.io import snapshot

    def by_type(g):  # partition that does not depend on edges: perturbation cannot change it
        return {c: [{t: set(n for n in snapshot(g, c).node_ids if g.nodes.at[n, "type"] == t)
                     for t in sorted(g.nodes["type"].unique())
                     if any(g.nodes.at[n, "type"] == t for n in snapshot(g, c).node_ids)}] for c in cfg.cutoffs}

    rows, summary = perturbation_stability(tkh, by_type, list(cfg.cutoffs), 0.34, seeds=(0, 1, 2))
    assert all(r["ari"] == 1.0 for r in rows) and all(s["mean"] == 1.0 for s in summary)


def test_cross_snapshot_identical_partitions_on_common_nodes():
    parts = {2020: [{"a": {"x", "y"}, "b": {"z"}}], 2022: [{"A": {"x", "y"}, "B": {"z", "w"}}]}
    (row,) = cross_snapshot_stability(parts, [2020, 2022], n_boot=20, n_perm=19)
    assert row["n_common"] == 3 and row["ari"] == 1.0


def test_clustering_relation_perturbation_never_touches_other_relations():
    from tkh.coarsen import CLUSTER_RELATIONS
    cfg = load_config()
    tkh = load(cfg)
    pert, dropped = remove_edges(tkh, 0.10, 0, cfg.cutoffs, relations=CLUSTER_RELATIONS)
    assert set(tkh.edges.loc[dropped, "relation_type"]) <= set(CLUSTER_RELATIONS)
    clu = tkh.edges["relation_type"].isin(CLUSTER_RELATIONS)
    assert abs(len(dropped) - 0.10 * clu.sum()) <= len(cfg.cutoffs) + 1
    assert (pert.edges["relation_type"] == "presents").sum() == (tkh.edges["relation_type"] == "presents").sum()


def test_perturbation_scores_concept_nodes_only():
    cfg = load_config()  # the fixture graph has no non-concept nodes
    tkh = load(cfg)
    from tkh.io import snapshot
    from tkh.semantic import CONCEPT_TYPES

    n_edges = len(tkh.edges)

    def anchored_noise(g):  # concept nodes always one cluster; non-concept nodes split off only after perturbation
        out = {}
        for c in cfg.cutoffs:
            ids = snapshot(g, c).node_ids
            conc = {n for n in ids if g.nodes.at[n, "type"] in CONCEPT_TYPES}
            out[c] = [{"c": set(ids)}] if len(g.edges) == n_edges else [{"c": conc, "x": ids - conc}]
        return out

    rows, _ = perturbation_stability(tkh, anchored_noise, list(cfg.cutoffs), 0.10, seeds=(0,))
    assert all(r["ari"] == 1.0 and r["variant"] == "clustering_relations" for r in rows)
    rows_all, _ = perturbation_stability(tkh, anchored_noise, list(cfg.cutoffs), 0.10, seeds=(0,), node_types=None)
    assert any(r["ari"] < 1.0 for r in rows_all)  # scoring all nodes would have been fooled


def test_change_localisation_ratio_detects_change_at_touched_nodes():
    import pandas as pd
    from types import SimpleNamespace
    from tkh.evaluate.stability import change_localisation
    nodes = pd.DataFrame({"type": ["method"] * 6}, index=list("abcdef"))
    edges = pd.DataFrame({"members": [["a", "b"]], "article_year": [2022], "relation_type": ["uses_technique"]})
    tkh = SimpleNamespace(nodes=nodes, edges=edges)
    p0 = {2020: [{"1": {"a", "c"}, "2": {"b", "d"}, "3": {"e", "f"}}]}
    p1 = {2022: [{"1": {"a", "b"}, "2": {"c", "d"}, "3": {"e", "f"}}]}
    (row,) = change_localisation(tkh, {**p0, **p1}, [2020, 2022], n_perm=99)
    assert row["n_touched"] == 2 and row["reassign_touched"] == 1.0
    assert row["reassign_untouched"] == 0.5 and row["ratio"] == 2.0
