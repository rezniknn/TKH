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
from tkh.null import _interval, configuration_null  # noqa: E402


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
    per = Counter(_interval(y, cfg.cutoffs) for y in tkh.edges.loc[drop, "article_year"])
    tot = Counter(_interval(y, cfg.cutoffs) for y in tkh.edges["article_year"])
    assert all(per[p] == round(0.10 * n) for p, n in tot.items())
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
