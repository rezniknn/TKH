"""Tests for tkh/llm.py, tkh/label.py (evidence, 50/50 split, LLM labeller) and eval/labels.py, offline with a stub LLM."""

from collections import Counter
from dataclasses import replace
from pathlib import Path
import json
import re
import sys

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import validate  # noqa: E402
from eval.labels import Judge, NameChecker, judge_trees  # noqa: E402
from tkh import pipeline  # noqa: E402
from tkh.config import load_config  # noqa: E402
from tkh.hierarchy import Params  # noqa: E402
from tkh.io import load, snapshot  # noqa: E402
from tkh.label import Evidence, LLMLabeller, split_evidence  # noqa: E402
from tkh.llm import CacheMiss, CachedLLM  # noqa: E402

FIXTURE_CONFIG = ROOT / "tests" / "fixtures" / "_input" / "config.toml"


class StubLLM:
    """Deterministic answers by prompt type; the entail answer supports a claim iff its words occur in one evidence line."""

    def __init__(self, lie=False):
        self.prompts, self.lie = [], lie

    def complete(self, prompt):
        self.prompts.append(prompt)
        if "Write a short, specific label" in prompt:
            return {"label": "Stub label", "gloss": "Stub gloss about the group."}
        if "atomic claims" in prompt:
            gloss = re.search(r"Gloss: (.*)", prompt).group(1)
            return {"claims": [gloss]}
        claim = re.search(r"Claim: (.*)", prompt).group(1)
        lines = [re.sub(r"^\d+\. ", "", ln) for ln in prompt.split("\n") if re.match(r"^\d+\. ", ln)]
        target = re.sub(r'^The group has a member named "(.*)"\.$', r"\1", claim)
        hit = next((ln for ln in lines if target and ln.startswith(target)), None)
        if self.lie:
            return {"verdict": "supported", "line": 999, "phrase": "line one"}
        return ({"verdict": "supported", "line": lines.index(hit) + 1, "phrase": hit} if hit
                else {"verdict": "unsupported", "line": 0, "phrase": ""})

    def complete_many(self, prompts, workers=1):
        return [self.complete(p) for p in prompts]


@pytest.fixture(scope="module")
def real():
    cfg = load_config()
    return cfg, load(cfg)


def _supernode(real, cutoff=2026, level=1, i=3):
    h = json.loads((ROOT / "out" / str(cutoff) / "hierarchy.json").read_text())
    return [s for s in h["supernodes"] if s["level"] == level][i]["member_ids"]


def test_split_is_deterministic_disjoint_stratified_and_seeded(real):
    cfg, tkh = real
    members = _supernode(real)
    items = Evidence(tkh).items(2026, members)
    seen, held = split_evidence(items, members, seed=0, cap=10 ** 6)
    assert (seen, held) == split_evidence(items, members, seed=0, cap=10 ** 6)
    assert not set(seen) & set(held) and set(seen) | set(held) == {t for _, t, _ in items}
    kind = {t: k for k, t, _ in items}
    cs, ch = Counter(kind[t] for t in seen), Counter(kind[t] for t in held)
    assert all(abs(cs[k] - ch[k]) <= 1 for k in set(cs) | set(ch))          # stratified by kind
    assert split_evidence(items, members, seed=1, cap=10 ** 6) != (seen, held)


def test_labeller_never_sees_held_out_evidence_and_records_its_input(real):
    cfg, tkh = real
    stub = StubLLM()
    lab = LLMLabeller(tkh, cfg, llm=stub)
    members = _supernode(real)
    assert lab(2026, 1, members) == ("Stub label", "Stub gloss about the group.")
    rec = lab.inputs[(2026, 1, frozenset(members))]
    prompt = stub.prompts[-1]
    assert rec["held_out"] and all(f"- {t}\n" not in prompt + "\n" for t in rec["held_out"])
    assert all(f"- {t}" in prompt for t in rec["seen"])
    assert lab(2026, 2, members) == (None, None)


def test_evidence_uses_only_the_snapshot(real):
    cfg, tkh = real
    ev = Evidence(tkh)
    _, e, _ = ev._snapshot(2020)
    assert (e["article_year"] <= 2020).all()
    members = sorted(snapshot(tkh, 2020).node_ids)[:400]
    assert all(v in snapshot(tkh, 2020).node_ids for v in members)


def test_offline_cache_miss_raises(tmp_path):
    with pytest.raises(CacheMiss):
        CachedLLM("phi4", tmp_path / "none.json", mode="offline")
    (tmp_path / "c.json").write_text(json.dumps({"models": {"phi4": "d"}, "entries": {}}))
    with pytest.raises(CacheMiss):
        CachedLLM("phi4", tmp_path / "c.json", mode="offline").complete("hello")


def test_line_check_rejects_citations_of_missing_lines():
    cfg = load_config()
    j = Judge(cfg, llm=StubLLM(lie=True))
    v = j.entail_many([(2026, "Some claim.", ["line one about something", "line two"])])[0]
    assert v["verdict"] == "supported" and not v["quote_ok"] and not v["supported"]


def _tree(n=6):
    rows = []
    for i in range(n):
        held = [f"concept{i} [method]", f"fact {i} about the group"]
        rows.append((2026, 1, f"s{i}", "p0", [f"m{i}"], f"label {i}", f"fact {i} about the group", ["seen"], held))
    return rows


def test_controls_give_sensitivity_specificity_and_corrected_rate():
    cfg, tkh = load_config(), None
    j = Judge(cfg, llm=StubLLM())

    class NoNames:
        def checks(self, text, members, cutoff):
            return {"year_after_cutoff": False, "named_non_member": [], "future_entity": []}
    summary, recs = judge_trees({"model": _tree()}, j, NoNames(), "standard")
    s = summary["model"]
    assert s["over_claim"]["value"] == 0.0 and s["claim_unsupported"] == 0.0     # each gloss is a held-out line
    assert s["Sp"] == 1.0 and s["Se"] == 1.0 and s["J"] == 1.0 and s["valid"]
    assert s["corrected_over_claim"] == pytest.approx(0.0)
    assert {r["kind"] for r in recs} == {"label", "true", "false", "cross", "sibling"}


def test_fixture_pipeline_with_llm_labeller_validates(tmp_path, monkeypatch):
    cfg = load_config(FIXTURE_CONFIG)
    cfg = replace(cfg, labels={"labeller": "llm"})
    tkh = load(cfg)
    monkeypatch.setattr(pipeline, "make_labeller", lambda t, c: LLMLabeller(t, c, llm=StubLLM()))
    pipeline.run(cfg, Params.from_config({"hub_frac": 1.0}), tmp_path)
    assert validate.validate(tmp_path, load_config(tmp_path / "run_config.toml"), tkh) == []
    inp = json.loads((tmp_path / "2024" / "label_inputs.json").read_text())
    h = json.loads((tmp_path / "2024" / "hierarchy.json").read_text())
    assert set(inp) == {s["id"] for s in h["supernodes"] if s["level"] in (0, 1)}
    assert all(s["label"] == "Stub label" for s in h["supernodes"] if s["level"] in (0, 1))


def test_name_checker_flags_non_members_and_future_entities(real):
    cfg, tkh = real
    nc = NameChecker(tkh)
    name, nodes = next((s, vs) for s, vs in nc.nodes_of.items() if all(nc.entry[v] > 2020 for v in vs))
    d = nc.checks(f"A label about {name} in 2027", [], 2020)
    assert d["year_after_cutoff"] and name in d["named_non_member"] and name in d["future_entity"]
    assert np.isfinite(len(nodes))
