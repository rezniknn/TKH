"""Tests for tkh/retrieve.py (drill-down agent, flat baseline) and eval/retrieval.py (gold resolution, hit-rate, steps)."""

from pathlib import Path
import json
import sys

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from eval.retrieval import parse_citation, read_questions, resolve_citation, resolve_method, retrieval_check, score  # noqa: E402
from tkh.config import load_config  # noqa: E402
from tkh.io import load, snapshot  # noqa: E402
from eval.retrieval import objective  # noqa: E402
from eval.retrieval_experiments import BASELINE  # noqa: E402
from tkh.retrieve import KINDS, LEAF_INFO, Index, Space, _keep, choose_snapshot, descend, flat, leaf_texts  # noqa: E402
from tkh import semantic as sm  # noqa: E402

CUTOFFS = (2020, 2022, 2024, 2026)
QUESTIONS = ROOT / "data" / "questions.csv"
GT = ROOT / "data" / "ground_truth.json"


@pytest.fixture(scope="module")
def real():
    cfg = load_config()
    tkh = load(cfg)
    return cfg, tkh, Index(tkh, ROOT / "out", 2026)


def test_snapshot_choice():
    qs = read_questions(QUESTIONS)
    got = {q["id"]: choose_snapshot(q["question"], CUTOFFS) for q in qs}
    assert all(c == 2026 for c, _ in got.values())
    assert got["Q16"] == (2026, "default_latest") and got["Q1"] == (2026, "stated")
    assert choose_snapshot("Which methods (by March 2023) work?", CUTOFFS) == (2022, "stated")
    assert choose_snapshot("What is known as of 2024?", CUTOFFS) == (2024, "stated")
    assert choose_snapshot("Which methods by 2010?", CUTOFFS) == (2020, "before_first_cutoff")


@pytest.mark.parametrize("info", [x for x in LEAF_INFO if x != "name"])
def test_leaf_text_uses_only_snapshot_edges(real, info):
    cfg, tkh, _ = real
    early, late = snapshot(tkh, 2020), snapshot(tkh, 2026)
    t20, t26 = leaf_texts(tkh, early, info), leaf_texts(tkh, late, info)
    name = sm.names(tkh)
    new = late.edges[(late.edges["article_year"] > 2020) & (late.edges["relation_type"] == "extends")]
    pairs = [(t, m[0]) for m in new["members"] for t in m[1:] if t in early.node_ids and name[m[0]] not in t20[t]]
    assert pairs and all(name[h] in t26[t] for t, h in pairs)   # a later method extending an early one


class Toy:
    """Two L0 nodes, one L1 child each, leaves with 2-d vectors."""

    def __init__(self):
        self.vec = {"a": [1, 0], "b": [0.9, 0.1], "c": [0, 1], "d": [0.1, 0.9]}
        self.sn = {"L0.1": {"member_ids": ["a", "b"], "label": "x"}, "L0.2": {"member_ids": ["c", "d"], "label": "y"},
                   "L1.1": {"member_ids": ["a", "b"]}, "L1.2": {"member_ids": ["c", "d"]}}
        self.children = {"L0.1": ["L1.1"], "L0.2": ["L1.2"], "L1.1": [], "L1.2": []}
        self.roots, self.type, self.leaves = ["L0.1", "L0.2"], dict.fromkeys("abcd", "method"), list("abcd")

    def score(self, sid, q, *_):
        return max(float(np.dot(self.vec[v], q)) for v in self.sn[sid]["member_ids"])

    def rank(self, ids, q):
        return sorted(((v, float(np.dot(self.vec[v], q))) for v in ids), key=lambda t: (-t[1], t[0]))


def _ans(ranked, n_super):
    return {"ranked": [v for v, _ in ranked], "n_supernodes_scored": n_super, "trace": [], "claim_nodes": [],
            "citation_articles": []}


def test_steps_hier_flat_and_censoring():
    ix, q = Toy(), np.array([1.0, 0.0])
    ranked, trace = descend(ix, q, ("method",), (1, 1))
    assert [v for v, _ in ranked] == ["a", "b"] and len(trace) == 3          # 2 L0 + 1 L1 scored
    gold = {"claims": [], "citations": []}
    assert score(_ans(ranked, len(trace)), gold, ["b"], ix, 4)["steps"] == 3 + 2
    assert score(_ans(flat(ix, q, ("method",)), 0), gold, ["c"], ix, 4)["steps"] == 4    # global rank
    assert score(_ans(ranked, len(trace)), gold, ["c"], ix, 4)["steps"] == 4 + 1          # not in the pool: N + 1


def test_method_resolution_tiers(real):
    _, _, ix = real
    tier, nodes = resolve_method("GAP", ix, KINDS["A"])
    assert tier == "acronym" and all("(GAP)" in ix.name[v] for v in nodes)
    tier, nodes = resolve_method("Orb", ix, KINDS["A"])
    assert tier == "prefix" and all(ix.name[v].lower().startswith("orb") for v in nodes)
    tier, nodes = resolve_method("ACE", ix, KINDS["A"])
    assert nodes and all("(ACE)" in ix.name[v] or sm.name_key(ix.name[v]).startswith("ace") for v in nodes)
    assert resolve_method("physics-informed", ix, KINDS["A"]) == ("unattainable", [])
    assert resolve_method("MACE", ix, KINDS["A"])[0] == "exact"


def test_citation_resolution(real):
    _, _, ix = real
    assert parse_citation("Li et al. 2022 (DeepH)") == (["li"], 2022, "DeepH")
    assert parse_citation("Chen & Ong 2022") == (["chen", "ong"], 2022, None)
    tier, arts = resolve_citation("Chen & Ong 2022", ix)
    assert tier == "unique" and "Interatomic Potential" in ix.art_title[arts[0]]
    tier, arts = resolve_citation("Li et al. 2022 (DeepH)", ix)
    assert tier == "unique" and "Hamiltonian" in ix.art_title[arts[0]]
    assert resolve_citation("Nobody et al. 2022", ix) == ("unattainable", [])


@pytest.fixture(scope="module")
def run(real):
    cfg, tkh, _ = real
    return retrieval_check(tkh, ROOT / "out", cfg.cutoffs, QUESTIONS, GT, B=200)


def test_answers_have_ground_truth_format(run):
    metrics, answers = run
    for qid, a in answers.items():
        keys = ("expected_methods", "required_citations") if a["type"] == "A" else \
               ("as_of", "required_claims", "sources", "required_citations")
        for h in (a["hier"], a["flat"]):
            assert all(k in h for k in keys) and all(isinstance(c, str) for c in h["required_citations"])
        assert set(a["hier"]["closest"]) == {0, 1, 2, "leaf"}               # closest match at every level
    assert set(metrics["summary"]) == {"A", "B"} and json.dumps(metrics, allow_nan=False)


def test_agent_does_not_see_ground_truth(real, run, tmp_path):
    cfg, tkh, _ = real
    gt = json.loads(GT.read_text())
    for v in gt.values():
        v["expected_methods" if v["type"] == "A" else "required_claims"] = v.get("expected_methods", v.get("required_claims"))[:1]
    (tmp_path / "gt.json").write_text(json.dumps(gt))
    _, other = retrieval_check(tkh, ROOT / "out", cfg.cutoffs, QUESTIONS, tmp_path / "gt.json", B=200)
    assert all(other[q][s] == run[1][q][s] for q in other for s in ("hier", "flat"))


def test_keyword_scorers_rank_by_matching_terms():
    docs = ["graph neural network potential", "graph kernel", "phonon spectra of crystals", "neural network"]
    for scorer in ("bm25", "overlap", "tfidf"):
        sp_ = Space(docs, scorer)
        q = sp_.query("graph neural potential")
        s = sp_.X @ q
        assert int(np.argmax(s)) == 0 and s[2] == 0                       # no shared keyword -> 0
    ov = Space(docs, "overlap")
    assert np.allclose(ov.X @ ov.query("graph neural potential"), [1, 1 / 3, 0, 1 / 3])


def test_relative_threshold_keeps_within_bounds():
    scored = [(1.0, "a"), (0.8, "b"), (0.5, "c"), (0.1, "d")]
    assert _keep(scored, 10, 0.7, 1) == ["a", "b"]
    assert _keep(scored, 1, 0.7, 1) == ["a"]                               # capped by the beam
    assert _keep(scored, 10, 0.95, 3) == ["a", "b", "c"]                   # at least min_keep
    assert _keep(scored, 2, None, 1) == ["a", "b"]


def test_baseline_settings_reproduce_the_first_run(real):
    cfg, tkh, _ = real
    m, _ = retrieval_check(tkh, ROOT / "out", cfg.cutoffs, QUESTIONS, GT, BASELINE, B=200)
    assert m["summary"]["A"]["citations"]["hier"]["mean"] == pytest.approx(0.124433, abs=1e-5)
    assert objective(m["per_question"])[0] == pytest.approx(0.124788, abs=1e-5)
