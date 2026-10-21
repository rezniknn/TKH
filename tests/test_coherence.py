"""Tests for E1a / E1b (tkh/evaluate/coherence.py), statistics (stats.py) and alpha selection (selection.py)."""

from pathlib import Path
import json
import math
import random
import sys

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from tkh.config import load_config  # noqa: E402
from tkh.evaluate.coherence import Ruler, _lift_parts, _lifts, coupling_lift, gt_comembership, make_split  # noqa: E402
from tkh.evaluate.selection import one_se  # noqa: E402
from tkh.evaluate.stats import holm, null_compare, wilson  # noqa: E402
from tkh.io import load  # noqa: E402


@pytest.fixture(scope="module")
def real():
    cfg = load_config()
    tkh = load(cfg)
    return cfg, tkh, Ruler(tkh, 2026)


class Toy:
    """Hand-made ruler: 3 papers, coupling known, single-paper concepts known."""
    def __init__(self):
        self.single = {"a1": "p", "a2": "p", "b1": "q", "c1": "r"}
        self.overlap_pairs = {("p", "q")}
        self.papers = ["p", "q", "r"]
        self.cites = {"p": {"x", "y"}, "q": {"x", "z"}, "r": {"w"}}

    coupling = Ruler.coupling
    _coupling = Ruler._coupling


def test_toy_lift_by_hand():
    r = Toy()
    level = {0: {"a1", "b1"}, 1: {"a2"}, 2: {"c1"}}  # half of p's concepts with q's only concept
    C = r.coupling(r.papers)
    # idf over 3 papers: x df 2 -> log 1.5, y,z,w df 1 -> log 3
    lx, l1 = math.log(1.5), math.log(3)
    assert C[0, 1] == pytest.approx(lx ** 2 / (lx ** 2 + l1 ** 2))
    assert C[0, 2] == C[1, 2] == 0
    parts = _lift_parts(r, level, r.papers)
    # pairs (p,q) w = 1/2 * 1 = .5 ; (p,r) 0 ; (q,r) 0
    O, E, n = parts["all"]
    assert O == pytest.approx(0.5 * C[0, 1]) and E == pytest.approx(0.5 * C[0, 1] / 3) and n == 3
    lifts = _lifts(parts)
    assert lifts["all"] == pytest.approx(3.0)
    assert lifts["overlap"] == pytest.approx(1.0)  # one overlap pair: weighted mean = mean
    assert lifts["pooled"] == pytest.approx(1.0)


def test_random_partitions_have_lift_about_one(real):
    cfg, tkh, ruler = real
    rng = random.Random(0)
    vals = []
    for _ in range(40):
        level = {}
        for v in ruler.concept:
            level.setdefault(rng.randrange(60), set()).add(v)
        vals.append(coupling_lift(ruler, level, jackknife=False)["all"]["value"])
    assert abs(np.mean(vals) - 1) < 0.03


def test_residual_filter_drops_name_matched_cited_works(real):
    cfg, tkh, ruler = real
    from tkh.evaluate.coherence import _names, citations
    names = _names(tkh)
    for a, kept in ruler.cites.items():
        concept_keys = set().union(*(names[v] for v in ruler.concept if a in _papers_of(tkh, v, ruler)), set())
        assert not any(names[w] & concept_keys for w in kept)
    assert sum(ruler.dropped.values()) > 0
    assert all(set(ruler.cites[a]) <= citations(tkh, 2026)[a] for a in ruler.cites)


def _papers_of(tkh, v, ruler, _cache={}):
    if not _cache:
        from tkh.coarsen import node_papers
        from tkh.io import snapshot
        _cache.update(node_papers(tkh, snapshot(tkh, 2026)))
    return _cache[v]


def test_split_is_disjoint_stratified_deterministic_and_committed(real):
    cfg, tkh, _ = real
    s = make_split(tkh, 0)
    assert not set(s["A"]) & set(s["B"]) and abs(len(s["A"]) - len(s["B"])) <= 1
    assert s == make_split(tkh, 0) and s != make_split(tkh, 1)
    from tkh.evaluate.coherence import citations
    df = {}
    for ws in citations(tkh, 10 ** 9).values():
        for w in ws:
            df[w] = df.get(w, 0) + 1
    for d in set(df.values()):
        a = sum(df[w] == d for w in s["A"])
        b = sum(df[w] == d for w in s["B"])
        assert abs(a - b) <= 1
    committed = ROOT / "data" / "eval_splits.json"
    if committed.exists():
        assert json.loads(committed.read_text()) == s


def test_gt_comembership_counts(real):
    cfg, tkh, _ = real
    targets = {"Q": {"expected": {"x": {"u"}, "y": {"v"}}, "wrong_domain": {"z": {"w"}}}}
    from types import SimpleNamespace  # noqa: F401
    level = {0: {"u", "v"}, 1: {"w"}}

    class G:  # tiny graph stub: three concept nodes of one paper each
        pass
    import pandas as pd
    g = G()
    g.nodes = pd.DataFrame({"type": ["method"] * 3, "prov_articles": [[1], [2], [1]], "entry_year": [2020] * 3},
                           index=["u", "v", "w"])
    g.edges = pd.DataFrame({"members": [["u", "w"]], "article_id": [1], "article_year": [2020], "relation_type": ["uses_technique"]})
    g.articles = pd.DataFrame({"year": [2020, 2020]}, index=[1, 2])
    r = gt_comembership(g, level, targets, 2020, n_boot=10)
    assert r["exp_cross_paper"]["hits"] == 1 and r["exp_cross_paper"]["pairs"] == 1
    assert r["exp_wrong"]["hits"] == 0 and r["exp_wrong"]["pairs"] == 2


# ---------------------------------------------------------------- stats and selection

def test_null_compare_and_holm():
    r = null_compare(5.0, [1, 2, 3, 4], higher_is_better=True)
    assert r["p"] == pytest.approx(1 / 5) and r["null_mean"] == 2.5
    assert null_compare(0.0, [1, 2, 3], higher_is_better=False)["p"] == pytest.approx(1 / 4)
    h = holm({"a": 0.01, "b": 0.04, "c": 0.03, "d": None})
    assert h == {"a": 0.03, "c": 0.06, "b": 0.06, "d": None}


def test_wilson_interval():
    lo, hi = wilson(0, 20)
    assert lo == pytest.approx(0, abs=1e-12) and 0.1 < hi < 0.2
    lo, hi = wilson(10, 20)
    assert lo < 0.5 < hi and hi - 0.5 == pytest.approx(0.5 - lo)


def test_one_se_rule_and_tie_break():
    rows = [{"cid": f"a{a}", "alpha": a, "value": v, "se": s, "eligible": e}
            for a, v, s, e in [(0.0, 1.0, 0.1, True), (0.25, 1.5, 0.3, True), (0.5, 1.3, 0.2, True),
                               (0.75, 1.1, 0.2, True), (1.0, 3.0, 0.1, False)]]
    win, out = one_se([dict(r) for r in rows], 0.5)
    assert win == "a0.5"                                   # 1.3 >= 1.5 - 0.3, closest to 0.5
    rows[2]["value"] = 1.1
    win, _ = one_se([dict(r) for r in rows], 0.5)
    assert win == "a0.25"                                  # 0.5 now outside one SE; 0.25 is best
    rows[3]["value"] = 1.3
    win, _ = one_se([dict(r) for r in rows], 0.5)
    assert win == "a0.25"                                  # 0.25 (1.5) and 0.75 (1.3) equidistant: higher score wins
    rows[1]["value"], rows[3]["value"] = 1.3, 1.5
    win, _ = one_se([dict(r) for r in rows], 0.5)
    assert win == "a0.75"
