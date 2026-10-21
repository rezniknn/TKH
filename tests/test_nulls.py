"""Tests for tkh/evaluate/nulls.py: invariants of the structure shuffle, the semantic permutation and random labels."""

from collections import Counter
from pathlib import Path
import sys

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import validate  # noqa: E402
from tkh.coarsen import CLUSTER_RELATIONS, hubs  # noqa: E402
from tkh.config import load_config  # noqa: E402
from tkh.evaluate.nulls import _period, permute_hierarchy, semantic_permutation, shuffle_hypergraph  # noqa: E402
from tkh.export import assemble_hierarchies, write_outputs  # noqa: E402
from tkh.hierarchy import Params, build  # noqa: E402
from tkh.io import load, snapshot  # noqa: E402
from tkh.label import placeholder_labeller  # noqa: E402
from tkh.semantic import CONCEPT_TYPES  # noqa: E402
from tkh.temporal import match_and_name  # noqa: E402


@pytest.fixture(scope="module")
def real():
    cfg = load_config()
    tkh = load(cfg)
    fixed = set().union(*(hubs(tkh, snapshot(tkh, c), 0.2) for c in cfg.cutoffs))
    g, diag = shuffle_hypergraph(tkh, 0, cfg.cutoffs, fixed)
    return cfg, tkh, fixed, g, diag


def test_shuffle_preserves_arity_types_first_member_hubs_and_period_degrees(real):
    cfg, tkh, fixed, g, diag = real
    t = tkh.nodes["type"]
    clu = tkh.edges.index[tkh.edges["relation_type"].isin(CLUSTER_RELATIONS)]
    deg = lambda E: Counter((v, _period(y, cfg.cutoffs)) for m, y in zip(E.loc[clu, "members"], E.loc[clu, "article_year"]) for v in m)  # noqa: E731
    assert deg(tkh.edges) == deg(g.edges)
    for i in clu:
        a, b = tkh.edges.at[i, "members"], g.edges.at[i, "members"]
        assert len(a) == len(b) == len(set(b)) and a[0] == b[0]
        assert Counter(t[v] for v in a) == Counter(t[v] for v in b)
        assert [v for v in a if v in fixed] == [v for v in b if v in fixed]
    rest = tkh.edges.index.difference(clu)
    assert all(tkh.edges.at[i, "members"] == g.edges.at[i, "members"] for i in rest)
    assert list(g.edges.index) == list(tkh.edges.index) and g.nodes is tkh.nodes
    assert 0 < diag["retained_incidence"] < 0.5  # actually mixes


def test_shuffle_keeps_snapshot_node_sets_and_is_deterministic(real):
    cfg, tkh, fixed, g, diag = real
    for c in cfg.cutoffs:
        assert snapshot(g, c).node_ids == snapshot(tkh, c).node_ids
    again, _ = shuffle_hypergraph(tkh, 0, cfg.cutoffs, fixed)
    other, _ = shuffle_hypergraph(tkh, 1, cfg.cutoffs, fixed)
    assert list(again.edges["members"]) == list(g.edges["members"])
    assert list(other.edges["members"]) != list(g.edges["members"])


def test_semantic_permutation_is_a_bijection_within_type_and_period(real):
    cfg, tkh, *_ = real
    p = semantic_permutation(tkh, 0, cfg.cutoffs)
    n = tkh.nodes
    assert set(p) == set(p.values()) == set(n.index[n["type"].isin(CONCEPT_TYPES)])
    for v, u in p.items():
        assert n.at[v, "type"] == n.at[u, "type"]
        assert _period(n.at[v, "entry_year"], cfg.cutoffs) == _period(n.at[u, "entry_year"], cfg.cutoffs)
    assert p == semantic_permutation(tkh, 0, cfg.cutoffs) != semantic_permutation(tkh, 1, cfg.cutoffs)


def test_permuted_hierarchy_keeps_sizes_and_passes_the_validator(tmp_path):
    cfg = load_config(ROOT / "tests" / "fixtures" / "_input" / "config.toml")
    tkh = load(cfg)
    parts = build(tkh, cfg.cutoffs, cfg.budgets, Params.from_config({**cfg.method, "hub_frac": 1.0}))
    perm = permute_hierarchy(parts, tkh, 0, cfg.cutoffs)
    for c in parts:
        for a, b in zip(parts[c], perm[c]):
            assert sorted(map(len, a.values())) == sorted(map(len, b.values()))
            assert set().union(*a.values()) == set().union(*b.values())
    ids, events = match_and_name(perm, list(cfg.cutoffs))
    write_outputs(tmp_path, assemble_hierarchies(perm, ids, placeholder_labeller(tkh), cfg.budgets), events)
    assert validate.validate(tmp_path, cfg, tkh) == []


def test_structure_null_build_uses_the_real_hubs(real):
    cfg, tkh, fixed, g, diag = real
    from tkh.hierarchy import build
    p = Params.from_config(cfg.method)
    cut = cfg.cutoffs[:1]
    real_hubs = {c: hubs(tkh, snapshot(tkh, c), p.hub_frac) for c in cut}
    shuffled_hubs = {c: hubs(g, snapshot(g, c), p.hub_frac) for c in cut}
    assert real_hubs != shuffled_hubs  # the shuffle changes paper counts, hence recomputed hubs
    _, d = build(g, cut, cfg.budgets, p, hub_sets=real_hubs, return_diag=True)
    assert set(d[cut[0]]["hubs"]) == real_hubs[cut[0]]
