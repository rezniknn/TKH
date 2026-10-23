"""Tests for eval/stability.py (HARI, perturbation) and the interval-restricted configuration null."""

from collections import Counter
from pathlib import Path
import json
import random
import sys

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from eval.stability import hari, remove_edges  # noqa: E402
from tkh.coarsen import CLUSTER_RELATIONS  # noqa: E402
from tkh.config import load_config  # noqa: E402
from tkh.io import load  # noqa: E402
from tkh.null import _interval, attachment_null, configuration_null  # noqa: E402


@pytest.fixture(scope="module")
def real():
    cfg = load_config()
    return cfg, load(cfg), json.loads(Path(cfg.graph).read_text())


def test_hari_is_one_on_identical_trees_and_near_zero_under_permutation():
    rng = random.Random(0)
    nodes = list(range(600))
    fine = {g: set(nodes[g::60]) for g in range(60)}
    coarse = {g: set().union(*(fine[h] for h in range(g, 60, 6))) for g in range(6)}
    tree = [coarse, fine]
    assert hari(tree, tree, nodes) == pytest.approx(1.0)
    vals = []
    for s in range(30):
        perm = nodes[:]
        random.Random(s).shuffle(perm)
        p = dict(zip(nodes, perm))
        vals.append(hari(tree, [{g: {p[v] for v in m} for g, m in lv.items()} for lv in tree], nodes))
    assert abs(sum(vals) / len(vals)) < 0.02 and rng is not None


def test_remove_edges_drops_ten_percent_per_period_and_is_deterministic(real):
    cfg, tkh, _ = real
    pert, drop = remove_edges(tkh, 0.10, 3, cfg.cutoffs)
    again = remove_edges(tkh, 0.10, 3, cfg.cutoffs)[1]
    assert drop == again and len(pert.edges) == len(tkh.edges) - len(drop)
    key = lambda ids: Counter((_interval(y, cfg.cutoffs), r) for y, r in zip(tkh.edges.loc[ids, "article_year"],  # noqa: E731
                                                                            tkh.edges.loc[ids, "relation_type"]))
    per, tot = key(drop), key(tkh.edges.index)
    assert all(per[k] == round(0.10 * n) for k, n in tot.items())          # 10% of every (period, relation)
    assert (pert.nodes["entry_year"] == tkh.nodes["entry_year"]).all()     # node sets of every snapshot kept


def test_interval_restricted_null_rewires_only_the_new_papers(real):
    cfg, tkh, raw = real
    cs = sorted(cfg.cutoffs)
    last = cs.index(2026)
    out, diag = configuration_null(raw, cs, 0, intervals={last})
    old = lambda r: [e for e in r["hyperedges"] if _interval(e["provenance"]["article_year"], cs) != last]  # noqa: E731
    assert old(out) == old(raw) and diag["moved_share"] > 0.3
    deg = lambda r: Counter((v, e["relation_type"]) for e in r["hyperedges"] if e["relation_type"] in CLUSTER_RELATIONS  # noqa: E731
                            for v in e["members"][1:])
    assert deg(out) == deg(raw)


def test_attachment_null_redraws_only_the_old_endpoints_of_new_edges(real):
    cfg, tkh, _ = real
    a = attachment_null(tkh, 2024, 2026, 0)
    old, new = tkh.edges["article_year"] <= 2024, tkh.edges["article_year"] > 2024
    assert (a.edges.loc[old, "members"] == tkh.edges.loc[old, "members"]).all()       # the graph <= 2024 is real
    assert (a.edges["members"].map(len) == tkh.edges["members"].map(len)).all()
    assert a.edges["members"].map(lambda m: len(set(m)) == len(m)).all()
    ntype, entry = tkh.nodes["type"].to_dict(), tkh.nodes["entry_year"].to_dict()
    changed = 0
    for m0, m1 in zip(tkh.edges.loc[new, "members"], a.edges.loc[new, "members"]):
        assert m0[0] == m1[0] and [ntype[v] for v in m0] == [ntype[v] for v in m1]       # head and type mix kept
        assert all(u == v for u, v in zip(m0, m1) if entry[u] > 2024)                    # new nodes stay
        changed += m0 != m1
    assert changed > 50
    assert (attachment_null(tkh, 2024, 2026, 0).edges["members"] == a.edges["members"]).all()
