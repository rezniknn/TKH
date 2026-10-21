"""Tests for tkh/coarsen.py (T4 collapse) and tkh/hierarchy.py (SHAC-T)."""

from pathlib import Path
import random
import sys

import numpy as np
import pytest
from scipy.sparse import csr_matrix

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import validate  # noqa: E402
from tkh.coarsen import collapse, concept_nodes, connectivity_cut  # noqa: E402
from tkh.config import load_config  # noqa: E402
from tkh.export import assemble_hierarchies, write_outputs  # noqa: E402
from tkh.hierarchy import Params, _Level, anchors, build, build_snapshot, concept_only  # noqa: E402
from tkh.io import load, snapshot  # noqa: E402
from tkh.label import placeholder_labeller  # noqa: E402
from tkh.temporal import match_and_name  # noqa: E402

FIXTURE_CONFIG = ROOT / "tests" / "fixtures" / "_input" / "config.toml"


def inc(edges, n):
    rows = [v for e in edges for v in e]
    cols = [j for j, e in enumerate(edges) for _ in e]
    return csr_matrix((np.ones(len(rows)), (rows, cols)), shape=(n, len(edges)))


# ---------------------------------------------------------------- T4 collapse

def test_collapse_cases_internal_partial_multiway():
    B = inc([[0, 1, 2, 3], [0, 1, 4, 5], [0, 2, 4, 6], [0, 1]], 7)
    labels = np.array([0, 0, 1, 1, 2, 2, 3])  # super-nodes {0,1}, {2,3}, {4,5}, {6}
    c = collapse(labels, B)
    assert list(c["lam"]) == [2, 2, 4, 1]
    assert list(c["cls"]) == ["partial", "partial", "uncollapsed", "internal"]
    assert list(c["multiway"]) == [False, False, True, False]
    assert c["counts"].toarray()[:, 0].tolist() == [2, 2, 0, 0]  # endpoint counts kept as metadata
    # a 4-way coarse edge stays ONE edge over 4 super-nodes, never split into pairs
    assert (c["counts"].toarray()[:, 2] > 0).sum() == 4


def test_merge_gain_equals_connectivity_cut_reduction():
    rng = random.Random(0)
    for _ in range(50):
        n = rng.randint(4, 12)
        edges = [rng.sample(range(n), rng.randint(2, min(5, n))) for _ in range(rng.randint(2, 8))]
        B = inc(edges, n)
        w = np.array([1 / (len(e) - 1) for e in edges])
        labels = np.array([rng.randint(0, 3) for _ in range(n)])
        A, Bn = 0, 1
        before = connectivity_cut(collapse(labels, B)["lam"], w)
        merged = np.where(labels == Bn, A, labels)
        merged = np.unique(merged, return_inverse=True)[1]
        after = connectivity_cut(collapse(merged, B)["lam"], w)
        pres = collapse(labels, B)["counts"].toarray() > 0
        gain = float(np.sum(w * (pres[A] & pres[Bn]))) if pres.shape[0] > Bn else 0.0
        assert before - after == pytest.approx(gain)


# ---------------------------------------------------------------- engine

def _level(n, edges, params, cap=np.inf, Z=None):
    B = inc(edges, n).toarray()
    w = np.array([1 / (len(e) - 1) for e in edges])
    Z = np.eye(n) if Z is None else Z
    W = None
    if params.structure == "projection":
        num = (B * w) @ B.T
        d = B @ w
        W = num / np.sqrt(np.outer(d, d))
        np.fill_diagonal(W, 0)
    return _Level(Z, np.ones(n), B, w, W, None, None, params, cap)


def test_native_and_projection_agree_at_singletons_and_diverge_later():
    edges = [[0, 1, 2], [0, 1, 3], [2, 3], [3, 4]]
    nat = _level(5, edges, Params(alpha=0, gamma=0, structure="native"))
    prj = _level(5, edges, Params(alpha=0, gamma=0, structure="projection"))
    assert np.allclose(nat.score, prj.score)                     # identical at singletons
    assert int(np.argmax(nat.bval)) == int(np.argmax(prj.bval))
    nat.merge(0, 1); prj.merge(0, 1)                              # A={0,1} now holds 2 endpoints of edges 0 and 1
    assert not np.allclose(nat._H_all([0]), prj._H_all([0]))     # native counts each edge once per super-node pair


def test_cap_rho_two_always_reaches_the_target():
    rng = random.Random(1)
    for trial in range(40):
        n = rng.randint(6, 40)
        target = rng.randint(1, n - 1)
        edges = [rng.sample(range(n), rng.randint(2, min(6, n))) for _ in range(rng.randint(1, 12))]
        lvl = _level(n, edges, Params(alpha=0.5, gamma=0), cap=2.0 * n / target, Z=np.random.default_rng(trial).normal(size=(n, 5)))
        groups = lvl.run(target)
        assert len(groups) == target and max(len(g) for g in groups) <= 2.0 * n / target


# ---------------------------------------------------------------- full build

@pytest.fixture(scope="module")
def fixture_build():
    cfg = load_config(FIXTURE_CONFIG)
    tkh = load(cfg)
    params = Params.from_config({**cfg.method, "hub_frac": 1.0})  # 3 papers: keep structure in the toy graph
    return cfg, tkh, params, build(tkh, cfg.cutoffs, cfg.budgets, params)


def test_fixture_build_is_laminar_in_budget_and_validates(fixture_build, tmp_path):
    cfg, tkh, params, parts = fixture_build
    for c, levels in parts.items():
        nodes = snapshot(tkh, c).node_ids
        for k, lv in enumerate(levels):
            assert len(lv) == min(cfg.budgets[k], len(concept_nodes(tkh, snapshot(tkh, c))))
            assert set().union(*lv.values()) == nodes                      # full coverage incl. anchored nodes
            assert sum(len(m) for m in lv.values()) == len(nodes)          # no overlap
            if k:
                parents = [next(p for p, pm in levels[k - 1].items() if m <= pm) for m in lv.values()]
                assert len(parents) == len(lv)                             # each child inside one parent
    ids, events = match_and_name(parts, list(cfg.cutoffs))
    write_outputs(tmp_path, assemble_hierarchies(parts, ids, placeholder_labeller(tkh), cfg.budgets), events)
    assert validate.validate(tmp_path, cfg, tkh) == []


def test_build_is_deterministic(fixture_build):
    cfg, tkh, params, parts = fixture_build
    assert build(tkh, cfg.cutoffs, cfg.budgets, params) == parts


def test_gamma_one_reproduces_previous_partition_on_unchanged_snapshot():
    cfg = load_config()
    tkh = load(cfg)
    snap = snapshot(tkh, 2020)
    p = Params.from_config({**cfg.method, "gamma": 1.0})
    first = build_snapshot(tkh, snap, cfg.budgets, p)
    again = build_snapshot(tkh, snap, cfg.budgets, p, prev=first)
    canon = lambda lv: sorted(sorted(m) for m in lv.values())  # noqa: E731
    assert all(canon(a) == canon(b) for a, b in zip(first, again))


def test_anchors_cover_all_non_concept_nodes_with_snapshot_concepts():
    cfg = load_config()
    tkh = load(cfg)
    for c in (2020, 2026):
        snap = snapshot(tkh, c)
        concept = set(concept_nodes(tkh, snap))
        anc = anchors(tkh, snap, concept)
        assert set(anc) == snap.node_ids - concept
        assert set(anc.values()) <= concept


def test_concept_only_drops_anchored_nodes(fixture_build):
    cfg, tkh, params, parts = fixture_build
    cp = concept_only(parts, tkh)
    for c, levels in cp.items():
        assert set().union(*levels[0].values()) == set(concept_nodes(tkh, snapshot(tkh, c)))


@pytest.mark.parametrize("bad", [{"alpha": 1.5}, {"rho": 1.0}, {"structure": "clique"}])
def test_invalid_params_rejected(bad):
    with pytest.raises(ValueError):
        Params.from_config(bad)


def test_freeze_reference_keeps_old_assignments():
    from tkh.evaluate.stability import ari, labels
    cfg = load_config()
    tkh = load(cfg)
    p = Params.from_config({**cfg.method, "freeze": True})
    parts = concept_only(build(tkh, cfg.cutoffs[:2], cfg.budgets, p), tkh)
    a, b = cfg.cutoffs[:2]
    for k in range(len(cfg.budgets)):
        old = sorted(set().union(*parts[a][k].values()))
        assert ari(labels(parts[a][k], old), labels(parts[b][k], old)) == 1.0
        assert len(parts[b][k]) == cfg.budgets[k]
