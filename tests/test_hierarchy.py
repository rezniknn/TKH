"""Tests for tkh/coarsen.py (clustering hypergraph, T4 collapse) and tkh/hierarchy.py (SHAC)."""

from dataclasses import replace
from pathlib import Path
import json
import random
import sys

import numpy as np
import pytest
from scipy.sparse import csr_matrix

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import validate  # noqa: E402
from tkh.coarsen import collapse, concept_nodes, connectivity_cut, hubs, incidence  # noqa: E402
from tkh.config import load_config  # noqa: E402
from tkh.export import assemble_hierarchies, write_outputs  # noqa: E402
from tkh.hierarchy import Params, _Level, _MidRankCDF, anchors, build  # noqa: E402
from tkh.io import load, snapshot  # noqa: E402
from tkh.label import placeholder_labeller  # noqa: E402
from tkh.pipeline import run  # noqa: E402
from tkh.temporal import match_and_name  # noqa: E402

FIXTURE_CONFIG = ROOT / "tests" / "fixtures" / "_input" / "config.toml"


def inc(edges, n):
    rows = [v for e in edges for v in e]
    cols = [j for j, e in enumerate(edges) for _ in e]
    return csr_matrix((np.ones(len(rows)), (rows, cols)), shape=(n, len(edges)))


def _level(n, edges, alpha=0.0, cap=np.inf, Z=None):
    B = inc(edges, n).toarray()
    w = np.array([1 / (len(e) - 1) for e in edges])
    Z = np.eye(n) if Z is None else Z
    return _Level(Z, np.ones(n), B, w, alpha, cap)


@pytest.fixture(scope="module")
def real():
    cfg = load_config()
    return cfg, load(cfg)


# ---------------------------------------------------------------- T4 collapse

def test_collapse_cases_internal_partial_multiway():
    B = inc([[0, 1, 2, 3], [0, 1, 4, 5], [0, 2, 4, 6], [0, 1]], 7)
    labels = np.array([0, 0, 1, 1, 2, 2, 3])  # super-nodes {0,1}, {2,3}, {4,5}, {6}
    c = collapse(labels, B)
    assert list(c["lam"]) == [2, 2, 4, 1]
    assert list(c["cls"]) == ["partial", "partial", "uncollapsed", "internal"]
    assert list(c["multiway"]) == [False, False, True, False]
    assert c["counts"].toarray()[:, 0].tolist() == [2, 2, 0, 0]  # endpoint counts kept as metadata
    assert (c["counts"].toarray()[:, 2] > 0).sum() == 4           # a 4-way coarse edge stays ONE edge


def test_merge_gain_equals_connectivity_cut_reduction():
    """Prop. 1: the H numerator of a merge equals the reduction of sum_e w_e (lambda_e - 1)."""
    rng = random.Random(0)
    for _ in range(50):
        n = rng.randint(4, 12)
        edges = [rng.sample(range(n), rng.randint(2, min(5, n))) for _ in range(rng.randint(2, 8))]
        B, w = inc(edges, n), np.array([1 / (len(e) - 1) for e in edges])
        labels = np.array([rng.randint(0, 3) for _ in range(n)])
        before = connectivity_cut(collapse(labels, B)["lam"], w)
        merged = np.unique(np.where(labels == 1, 0, labels), return_inverse=True)[1]
        after = connectivity_cut(collapse(merged, B)["lam"], w)
        pres = collapse(labels, B)["counts"].toarray() > 0
        gain = float(np.sum(w * (pres[0] & pres[1]))) if pres.shape[0] > 1 else 0.0
        assert before - after == pytest.approx(gain)


def test_relation_balanced_weights_give_every_relation_the_same_total(real):
    cfg, tkh = real
    snap = snapshot(tkh, 2026)
    items = concept_nodes(tkh, snap)
    _, w, _, rels = incidence(tkh, snap, items, hubs(tkh, snap, 0.2), "relation_balanced")
    totals = {r: w[np.array(rels) == r].sum() for r in set(rels)}
    assert len(totals) == 6 and np.allclose(list(totals.values()), 1.0)


def test_hub_frac_one_means_no_hubs(real):
    cfg, tkh = real
    assert hubs(tkh, snapshot(tkh, 2026), 1.0) == set()
    assert len(hubs(tkh, snapshot(tkh, 2026), 0.2)) > 0


# ---------------------------------------------------------------- engine

def test_structural_rank_gives_unlinked_pairs_no_credit():
    F = _MidRankCDF(np.array([0.0, 0.0, 0.0, 0.2, 0.5]), positive=True)
    assert F(np.array([0.0]))[0] == 0.0 and 0 < F(np.array([0.2]))[0] < F(np.array([0.5]))[0] <= 1.0
    lvl = _level(4, [[0, 1]], alpha=0.0)
    assert lvl.score[2, 3] == 0.0 and lvl.score[0, 1] > 0     # alpha = 0: only linked pairs score


def test_native_differs_from_clique_only_after_a_super_node_holds_two_endpoints():
    edges = [[0, 1, 2], [0, 1, 3], [2, 3], [3, 4]]
    lvl = _level(5, edges)
    lvl.merge(0, 1)                                     # {0,1} now holds 2 endpoints of edges 0 and 1
    assert lvl.stats["multi_endpoint"] == 0             # that merge itself was scored on singletons
    lvl.merge(0, 2)                                     # {0,1} + {2} share edge 0, where {0,1} has 2 endpoints
    assert lvl.stats["multi_endpoint"] == 1


def test_alpha_one_is_semantic_average_linkage():
    Z = np.array([[1, 0], [0.9, 0.1], [0, 1], [0.1, 0.9]], float)
    Z /= np.linalg.norm(Z, axis=1, keepdims=True)
    groups = _level(4, [[0, 2], [1, 3]], alpha=1.0, Z=Z).run(2)
    assert sorted(map(sorted, groups)) == [[0, 1], [2, 3]]   # structure ignored: names decide


def test_cap_rho_two_always_reaches_the_target():
    rng = random.Random(1)
    for trial in range(40):
        n = rng.randint(6, 40)
        target = rng.randint(1, n - 1)
        edges = [rng.sample(range(n), rng.randint(2, min(6, n))) for _ in range(rng.randint(1, 12))]
        lvl = _level(n, edges, alpha=0.5, cap=2.0 * n / target, Z=np.random.default_rng(trial).normal(size=(n, 5)))
        groups = lvl.run(target)
        assert len(groups) == target and max(len(g) for g in groups) <= 2.0 * n / target


@pytest.mark.parametrize("bad", [{"alpha": 1.5}, {"rho": 1.0}, {"hub_frac": 0.0}, {"edge_weight": "clique"},
                                 {"lsa_dim": 0}, {"gamma": 0.5}])
def test_invalid_or_unknown_params_rejected(bad):
    with pytest.raises(ValueError):
        Params.from_config(bad)


# ---------------------------------------------------------------- full build

@pytest.fixture(scope="module")
def fixture_build():
    cfg = load_config(FIXTURE_CONFIG)
    tkh = load(cfg)
    params = Params.from_config({"hub_frac": 1.0})  # 3 papers: keep structure in the toy graph
    return cfg, tkh, params, build(tkh, cfg.cutoffs, cfg.budgets, params)[0]


def test_fixture_build_is_laminar_in_budget_and_validates(fixture_build, tmp_path):
    cfg, tkh, params, parts = fixture_build
    for c, levels in parts.items():
        nodes = snapshot(tkh, c).node_ids
        for k, lv in enumerate(levels):
            assert len(lv) == min(cfg.budgets[k], len(concept_nodes(tkh, snapshot(tkh, c))))
            assert set().union(*lv.values()) == nodes                      # full coverage incl. anchored nodes
            assert sum(len(m) for m in lv.values()) == len(nodes)          # no overlap
            if k:
                assert all(any(m <= pm for pm in levels[k - 1].values()) for m in lv.values())   # nested
    ids, events = match_and_name(parts, list(cfg.cutoffs))
    write_outputs(tmp_path, assemble_hierarchies(parts, ids, placeholder_labeller(tkh), cfg.budgets), events)
    assert validate.validate(tmp_path, cfg, tkh) == []


def test_build_is_deterministic(fixture_build):
    cfg, tkh, params, parts = fixture_build
    assert build(tkh, cfg.cutoffs, cfg.budgets, params)[0] == parts


@pytest.mark.parametrize("budgets", [(1, 2), (2, 3), (1, 2, 4, 8, 16), (3, 100), (4, 4, 6)])
def test_any_budget_list_gives_exact_level_sizes_and_validates(budgets, tmp_path):
    cfg = replace(load_config(FIXTURE_CONFIG), budgets=budgets)
    tkh = load(cfg)
    run(cfg, Params.from_config({"hub_frac": 1.0}), tmp_path)
    assert validate.validate(tmp_path, load_config(tmp_path / "run_config.toml"), tkh) == []
    for c in cfg.cutoffs:
        n = len(concept_nodes(tkh, snapshot(tkh, c)))
        h = json.loads((tmp_path / str(c) / "hierarchy.json").read_text())
        assert [sum(s["level"] == k for s in h["supernodes"]) for k in range(len(budgets))] == [min(b, n) for b in budgets]


def test_real_build_at_2020_is_deterministic(real):
    cfg, tkh = real
    p = Params.from_config(cfg.method)
    assert build(tkh, [2020], cfg.budgets, p)[0] == build(tkh, [2020], cfg.budgets, p)[0]


def test_anchors_cover_all_non_concept_nodes_with_snapshot_concepts(real):
    cfg, tkh = real
    for c in (2020, 2026):
        snap = snapshot(tkh, c)
        concept = set(concept_nodes(tkh, snap))
        anc = anchors(tkh, snap, concept)
        assert set(anc) == snap.node_ids - concept
        assert set(anc.values()) <= concept
