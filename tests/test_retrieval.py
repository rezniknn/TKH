"""Tests for tkh/retrieve.py (drill-down agent, flat baseline) and eval/retrieval.py (gold resolution, M1-M3)."""

from pathlib import Path
from collections import Counter
import inspect
import json
import re
import sys

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from eval.retrieval import (parse_citation, read_questions, resolve_citation, resolve_gold, resolve_method,  # noqa: E402
                            resolve_source, retrieval_check, score)
from tkh.config import load_config  # noqa: E402
from tkh.io import load  # noqa: E402
from tkh import retrieve, semantic as sm  # noqa: E402
from tkh.retrieve import KINDS, Agent, Facts, Index, choose_snapshot, descend, flat, leaf_texts  # noqa: E402

QUESTIONS = ROOT / "data" / "questions.csv"
GT = ROOT / "data" / "ground_truth.json"


@pytest.fixture(scope="module")
def real():
    cfg = load_config(ROOT / "out" / "run_config.toml")
    tkh = load(cfg)
    return cfg, tkh, Index(tkh, ROOT / "out", 2026)


@pytest.fixture(scope="module")
def run(real):
    cfg, tkh, _ = real
    return retrieval_check(tkh, ROOT / "out", cfg.cutoffs, QUESTIONS, GT)


def test_snapshot_choice():
    cutoffs = (2020, 2022, 2024, 2026)
    got = {q["id"]: choose_snapshot(q["question"], cutoffs) for q in read_questions(QUESTIONS)}
    assert all(c == 2026 for c, _, _ in got.values())
    assert got["Q16"] == (2026, None, "default_latest") and got["Q1"] == (2026, 2026, "stated")
    assert choose_snapshot("Which methods (by March 2023) work?", cutoffs) == (2022, 2023, "stated")
    assert choose_snapshot("Which methods by 2010?", cutoffs) == (None, 2010, "before_first_cutoff")


def test_agent_abstains_before_first_cutoff(real):
    cfg, tkh, _ = real
    assert Agent(tkh, ROOT / "out", cfg.cutoffs).answer("Which methods by 2010?", "A")["abstain"]


def test_leaf_text_and_index_use_only_snapshot_edges(real):
    _, tkh, ix26 = real
    F20, F26 = Facts(tkh, 2020), ix26.F
    t20, t26 = leaf_texts(tkh, F20), leaf_texts(tkh, F26)
    e = F26.snap.edges
    late = e[(e["article_year"] > 2020) & (e["relation_type"] == "extends")]
    pairs = [(t, m[0]) for m in late["members"] for t in m[1:] if t in F20.snap.node_ids and F20.name[m[0]] not in t20[t]]
    assert pairs and all(F26.name[h] in t26[t] for t, h in pairs)   # a later method extending an early one
    ix20 = Index(tkh, ROOT / "out", 2020)
    late_only = {w for _, h in pairs for w in re.findall(r"[a-z][a-z0-9\-]{3,}", F26.name[h].lower())} - \
                {w for x in t20.values() for w in re.findall(r"[a-z][a-z0-9\-]{3,}", x.lower())}
    assert late_only and ix20.encode(" ".join(late_only)).sum() == 0


def test_title_added_once_per_presented_method(real):
    _, tkh, ix = real
    texts, title = leaf_texts(tkh, ix.F), tkh.articles["title"].to_dict()
    e = ix.F.snap.edges
    pres = e[e["relation_type"] == "presents"]
    n_pres = Counter(m[1] for m in pres["members"])
    for m, a in zip(pres["members"], pres["article_id"]):
        if isinstance(title.get(a), str):
            assert texts[m[1]].split(" . ").count(sm.clean(title[a])) == n_pres[m[1]]   # added, and once per edge


class Toy:
    """Two L0 nodes, one L1 child each, leaves with 2-d vectors."""

    def __init__(self):
        self.vec = {"a": [1, 0], "b": [0.9, 0.1], "c": [0, 1], "d": [0.1, 0.9]}
        self.sn = {"L0.1": {"member_ids": ["a", "b"], "label": "x"}, "L0.2": {"member_ids": ["c", "d"], "label": "y"},
                   "L1.1": {"member_ids": ["a", "b"]}, "L1.2": {"member_ids": ["c", "d"]}}
        self.children = {"L0.1": ["L1.1"], "L0.2": ["L1.2"], "L1.1": [], "L1.2": []}
        self.roots, self.leaves = ["L0.1", "L0.2"], list("abcd")
        self.F = type("F", (), {"type": dict.fromkeys("abcd", "claim"), "ids": list("abcd"),
                                "name": {v: v for v in "abcd"}, "articles_of": dict.fromkeys("abcd", [])})()

    def score(self, sid, q):
        return max(float(np.dot(self.vec[v], q)) for v in self.sn[sid]["member_ids"])

    def rank(self, ids, q):
        return sorted(((v, float(np.dot(self.vec[v], q))) for v in ids), key=lambda t: (-t[1], t[0]))


def _ans(ranked, trace):
    return {"ranked": [v for v, _ in ranked], "n_supernodes_scored": len(trace), "trace": trace,
            "node_ids": [], "article_ids": []}


def test_steps_hier_flat_and_censoring():
    ix, q = Toy(), np.array([1.0, 0.0])
    ranked, trace = descend(ix, q, ("claim",), (1, 1))
    assert [v for v, _ in ranked] == ["a", "b"] and len(trace) == 3          # 2 L0 + 1 L1 scored
    gold = lambda items: {"type": "B", "claims": [], "citations": {}, "step_items": items,   # noqa: E731
                          "targets": sorted({v for it in items for v in it})}
    assert score(_ans(ranked, trace), gold([["b"]]), ix.F)["steps_first"] == 3 + 2
    assert score(_ans(*flat(ix, q, ("claim",))), gold([["c"]]), ix.F)["steps_first"] == 4   # global rank
    out = score(_ans(ranked, trace), gold([["c"]]), ix.F, ix.sn)
    assert out["steps_first"] == 4 + 1 and not out["reached"] and out["lost_at_level"] == 0   # censored at N + 1
    assert score(_ans(ranked, trace), gold([["a"], ["b"], ["c"]]), ix.F)["steps_half"] == 3 + 2


def test_method_resolution_rules(real):
    F = real[2].F
    rule, nodes = resolve_method("GAP", F)
    assert rule == "acronym" and all("(GAP)" in F.name[v] for v in nodes)
    assert resolve_method("MACE", F)[0] == "exact"
    assert resolve_method("Orb", F) == ("unattainable", [])                 # no prefix rule
    assert resolve_method("physics-informed", F) == ("unattainable", [])


def test_citation_and_source_resolution(real):
    F = real[2].F
    assert parse_citation("Li et al. 2022 (DeepH)") == (["li"], 2022, "DeepH")
    assert parse_citation("Chen & Ong 2022") == (["chen", "ong"], 2022, None)
    rule, arts = resolve_citation("Chen & Ong 2022", F)
    assert rule == "unique" and "Interatomic Potential" in F.title[arts[0]]
    rule, arts = resolve_citation("Li et al. 2022 (DeepH)", F)
    assert rule == "unique" and "Hamiltonian" in F.title[arts[0]]
    assert resolve_citation("Nobody et al. 2022", F) == ("unattainable", [])
    gt = json.loads(GT.read_text())
    assert resolve_source(gt["Q18"]["sources"]["jacobs2025"], F)[0] == "doi"


def test_evidence_sources_split_on_semicolon(real):
    F = real[2].F
    gt = json.loads(GT.read_text())
    q, m = next((q, m) for q, v in gt.items() if v["type"] == "A" for m, es in v["method_evidence"].items()
                if any(";" in e["source"] for e in es))
    g = resolve_gold(gt[q], F)
    parts = {p.strip() for e in gt[q]["method_evidence"][m] for p in e["source"].split(";")}
    want = {a for p in parts for a in resolve_citation(p, F)[1]}
    assert all(set(c["articles"]) == want for c in g["method_claims"] if c["method"] == m)


def test_tree_covers_answer_kinds_and_full_beam_equals_flat(real):
    _, _, ix = real
    for t in KINDS:
        assert set(ix.leaves) >= {v for v in ix.F.ids if ix.F.type[v] in KINDS[t]}
    sizes = tuple(sum(s["level"] == lv for s in ix.sn.values()) for lv in range(3))
    for question in ("Which methods are best suited for predicting DFT Hamiltonians?", "Give evidence that GNNs generalise"):
        q = ix.encode(question)
        for t in KINDS:
            assert descend(ix, q, KINDS[t], sizes)[0] == flat(ix, q, KINDS[t])[0]


def test_beam_must_match_hierarchy_depth(real):
    cfg, tkh, _ = real
    with pytest.raises(ValueError):
        Agent(tkh, ROOT / "out", cfg.cutoffs, beam=(10, 20)).answer("Which methods are best suited for X?", "A")


def test_run_matches_committed_metrics(run):
    committed = json.loads((ROOT / "out" / "metrics.json").read_text())["retrieval"]
    assert json.loads(json.dumps(run[0])) == committed       # rerun `make retrieval` after a deliberate change


def test_answers_have_ground_truth_format(run):
    metrics, answers = run
    for qid, a in answers.items():
        keys = ("expected_methods", "method_claims", "method_evidence", "required_citations") if a["type"] == "A" else \
               ("as_of", "required_claims", "sources", "required_citations")
        for h in (a["hier"], a["flat"]):
            assert all(k in h for k in keys) and all(isinstance(c, str) for c in h["required_citations"])
        assert set(a["hier"]["closest"]) == {0, 1, 2, "leaf"}
    assert set(metrics["summary"]) == {"A", "B"} and json.dumps(metrics, allow_nan=False)
    assert all(p["snapshot_ok"] for p in metrics["per_question"].values())


def test_agent_does_not_see_ground_truth(real, run, tmp_path):
    src = inspect.getsource(retrieve)
    assert "ground_truth" not in src and "eval" not in re.findall(r"^\s*(?:from|import) (\w+)", src, re.M)
    cfg, tkh, _ = real
    gt = json.loads(GT.read_text())
    for v in gt.values():
        if v["type"] == "A":   # keep one method, consistently across the method-keyed fields
            v["expected_methods"] = v["expected_methods"][:1]
            for f in ("method_claims", "method_evidence"):
                v[f] = {m: x for m, x in v[f].items() if m in v["expected_methods"]}
        else:
            v["required_claims"] = v["required_claims"][:1]
    (tmp_path / "gt.json").write_text(json.dumps(gt))
    _, other = retrieval_check(tkh, ROOT / "out", cfg.cutoffs, QUESTIONS, tmp_path / "gt.json")
    assert all(other[q][s] == run[1][q][s] for q in other for s in ("hier", "flat"))
