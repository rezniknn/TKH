"""Tests for tkh/null.py (configuration model, random labels) and eval/p3.py (held-out P3 check)."""

from collections import Counter
from pathlib import Path
import json
import sys

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import validate  # noqa: E402
from tkh.coarsen import CLUSTER_RELATIONS, concept_nodes  # noqa: E402
from tkh.config import load_config  # noqa: E402
from tkh.hierarchy import Params  # noqa: E402
from tkh.io import load, snapshot  # noqa: E402
from tkh.null import _interval, configuration_null, null_tkh, random_labels  # noqa: E402
from eval.p3 import Ruler, split_works  # noqa: E402
from tkh.pipeline import run, with_graph  # noqa: E402

FIXTURE_CONFIG = ROOT / "tests" / "fixtures" / "_input" / "config.toml"


@pytest.fixture(scope="module")
def real():
    cfg = load_config()
    return cfg, load(cfg), json.loads(Path(cfg.graph).read_text())


def _profile(raw, cutoffs):
    ntype = {n["id"]: n["type"] for n in raw["nodes"]}
    deg, shape = Counter(), {}
    for e in raw["hyperedges"]:
        if e["relation_type"] in CLUSTER_RELATIONS:
            iv = _interval(e["provenance"]["article_year"], cutoffs)
            deg.update((v, e["relation_type"], iv) for v in e["members"][1:])
            shape[e["id"]] = (e["members"][0], len(e["members"]), len(set(e["members"])),
                              Counter(ntype[v] for v in e["members"]), e["provenance"]["article_id"])
    return deg, shape


def test_configuration_null_preserves_degrees_arity_types_hubs_and_other_relations(real):
    cfg, tkh, raw = real
    out, diag = configuration_null(raw, cfg.cutoffs, seed=3)
    assert _profile(out, cfg.cutoffs) == _profile(raw, cfg.cutoffs)
    assert diag["moved_share"] > 0.5                                           # it does mix
    keep = lambda r: [e for e in r["hyperedges"] if e["relation_type"] not in CLUSTER_RELATIONS]  # noqa: E731
    assert keep(out) == keep(raw)
    assert all(e["members"][0] not in e["members"][1:] for e in out["hyperedges"])
    assert configuration_null(raw, cfg.cutoffs, seed=3)[0] == out              # deterministic per seed
    assert configuration_null(raw, cfg.cutoffs, seed=4)[0] != out


def test_null_keeps_every_snapshot_node_set(real):
    cfg, tkh, raw = real
    null_tkh(raw, cfg.articles, cfg.cutoffs, seed=0, real=tkh)                 # raises if a node set changes


def test_null_run_on_fixture_validates_against_its_own_graph(tmp_path):
    cfg = load_config(FIXTURE_CONFIG)
    real = load(cfg)
    tk, raw_null, _ = null_tkh(json.loads(Path(cfg.graph).read_text()), cfg.articles, cfg.cutoffs, 1, real=real)
    (tmp_path / "graph.json").write_text(json.dumps(raw_null))
    run(with_graph(cfg, tmp_path / "graph.json"), Params.from_config({"hub_frac": 1.0}), tmp_path, tkh=tk)
    ncfg = load_config(tmp_path / "run_config.toml")
    assert validate.validate(tmp_path, ncfg, load(ncfg)) == []


def test_random_labels_keep_sizes_and_strata(real):
    cfg, tkh, _ = real
    snap = snapshot(tkh, 2020)
    items = concept_nodes(tkh, snap)
    lv = {g: set(items[g::7]) for g in range(7)}
    rl = random_labels([lv], tkh, snap, cfg.cutoffs, 0)[0]
    assert {g: len(m) for g, m in rl.items()} == {g: len(m) for g, m in lv.items()}
    assert set().union(*rl.values()) == set(items) and rl != lv


# ---------------------------------------------------------------- P3 ruler

def test_lift_is_one_for_constant_coupling_and_mask_excludes_overlap(real):
    cfg, tkh, _ = real
    snap = snapshot(tkh, 2026)
    ru = Ruler(tkh, snap)
    items = concept_nodes(tkh, snap)
    lv = {g: set(items[g::15]) for g in range(15)}
    a = ru.coassign(lv)
    c = ru.c.copy()
    ru.c = np.ones_like(c)
    assert ru.lift(a) == pytest.approx(1.0)
    ru.c = c
    P = ru.papers
    for i, j in zip(*np.nonzero(ru.mask)):
        assert not (ru.concepts[P[i]] & ru.concepts[P[j]])
    assert 0 < ru.mask.sum() < len(P) * (len(P) - 1) / 2


def test_ruler_does_not_depend_on_method_parameters(real):
    """The evaluator's hubs, pairs and coupling are fixed: building a ruler reads no [method] parameter."""
    cfg, tkh, _ = real
    snap = snapshot(tkh, 2026)
    a, b = Ruler(tkh, snap), Ruler(tkh, snap)
    assert np.array_equal(a.mask, b.mask) and np.array_equal(a.c, b.c)


def test_split_halves_are_disjoint_and_cover_all_cited_works(real):
    cfg, tkh, _ = real
    snap = snapshot(tkh, 2026)
    A, B = split_works(tkh, snap, 0)
    works = {w for m, r in zip(snap.edges["members"], snap.edges["relation_type"]) if r == "cites" for w in m[1:]}
    assert not A & B and A | B == works and abs(len(A) - len(B)) <= 20


def test_no_overlap_pairs_share_no_name_including_aliases(real):
    from tkh.semantic import name_keys
    cfg, tkh, _ = real
    snap = snapshot(tkh, 2026)
    ru, nk = Ruler(tkh, snap), name_keys(tkh)
    keys = {p: set().union(*(nk[v] for v in ru.concepts[p])) for p in ru.papers}
    P = ru.papers
    assert all(not keys[P[i]] & keys[P[j]] for i, j in zip(*np.nonzero(ru.mask)))


def test_period_adjusted_lift_removes_a_pure_period_effect(real):
    """If coupling depends only on the pair's period stratum, the adjusted lift is 1 for any partition,
    and with a single stratum it equals the unadjusted lift."""
    cfg, tkh, _ = real
    snap = snapshot(tkh, 2026)
    ru = Ruler(tkh, snap)
    items = concept_nodes(tkh, snap)
    a = ru.coassign({g: set(items[g::15]) for g in range(15)})
    unadj = ru.lift(a)
    c = ru.c.copy()
    ru.c = ru.stratum.astype(float) % 97 + 1.0          # coupling = a function of the period stratum only
    assert ru.lift(a, adjusted=True) == pytest.approx(1.0)
    ru.c, ru.stratum = c, np.zeros_like(ru.stratum)   # a single stratum
    assert ru.lift(a, adjusted=True) == pytest.approx(unadj)
