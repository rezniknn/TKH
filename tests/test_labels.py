"""Tests for labels and E3: cache behaviour, evidence split (no leakage of held-out members), deterministic checks, swapped control."""

from pathlib import Path
import json
import sys

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from tkh.config import load_config  # noqa: E402
from tkh.evaluate.faithfulness import NameChecker, derangement, deterministic_checks, summarise  # noqa: E402
from tkh.io import load  # noqa: E402
from tkh.label import Evidence, LLMLabeller, split_members  # noqa: E402
from tkh.llm import CacheMiss, CachedLLM  # noqa: E402


class FakeLLM:
    """Records prompts; answers with a fixed label."""
    def __init__(self):
        self.prompts = []

    def complete(self, prompt):
        self.prompts.append(prompt)
        return {"label": "Test label", "gloss": "A test gloss."}

    def key(self, prompt):
        return str(len(self.prompts))


@pytest.fixture(scope="module")
def real():
    cfg = load_config()
    return cfg, load(cfg)


def test_offline_cache_miss_raises_and_hits_replay(tmp_path):
    path = tmp_path / "cache.json"
    with pytest.raises(CacheMiss):
        CachedLLM("m", path, mode="offline")  # no recorded digest for the model
    path.write_text(json.dumps({"models": {"m": "sha256:abc"}, "entries": {}}))
    llm = CachedLLM("m", path, mode="offline")
    with pytest.raises(CacheMiss):
        llm.complete("hello")
    k = llm.key("hello")
    path.write_text(json.dumps({"models": {"m": "sha256:abc"}, "entries": {k: {"model": "m", "response": {"label": "x"}}}}))
    assert CachedLLM("m", path, mode="offline").complete("hello") == {"label": "x"}
    assert CachedLLM("m", path, mode="offline", options={"temperature": 1}).key("hello") != k  # options are in the key


def test_split_is_deterministic_disjoint_and_covers(real):
    ms = [f"n{i}" for i in range(11)]
    seen, held = split_members(ms)
    assert set(seen) | set(held) == set(ms) and not set(seen) & set(held) and len(seen) == 6
    assert split_members(list(reversed(ms))) == (seen, held)
    assert split_members(ms, seed=1) != (seen, held)


def test_labeller_prompt_never_contains_held_out_members(real):
    cfg, tkh = real
    from tkh.evaluate.stability import read_partitions
    parts = read_partitions(ROOT / "out", [2026])
    fake = FakeLLM()
    lab = LLMLabeller(tkh, cfg, llm=fake)
    name = tkh.nodes["surface_form"].to_dict()
    for g, mem in list(parts[2026][1].items())[:20]:
        lab(2026, 1, mem)
        view = lab.ev.labeller_view(2026, 1, mem)
        prompt = fake.prompts[-1]
        lines = set(prompt.splitlines())
        for v in view["held_out"]:
            assert f"- {name[v]} [{tkh.nodes.at[v, 'type']}]" not in lines or name[v] in {name[u] for u in view["shown"]}
        assert all(f"- {name[v]} [{tkh.nodes.at[v, 'type']}]" in lines for v in view["shown"])
    assert lab(2026, 2, mem) == (None, None)  # no labels below level 1


def test_judge_evidence_respects_cutoff(real):
    cfg, tkh = real
    ev = Evidence(tkh, cfg)
    nodes = [v for v in tkh.nodes.index if tkh.nodes.at[v, "type"] == "method"][:200]
    claims, titles = ev.paper_texts(2020, nodes, max_claims=50)
    late = set(tkh.articles.index[tkh.articles["year"] > 2020])
    late_titles = {str(tkh.articles.at[a, "title"]) for a in late}
    assert not set(titles) & late_titles


def test_deterministic_checks_fire(real):
    cfg, tkh = real
    chk = NameChecker(tkh)
    n = tkh.nodes
    late = next(v for v in n.index if n.at[v, "type"] == "method" and n.at[v, "entry_year"] > 2022 and len(str(n.at[v, "surface_form"])) >= 6)
    early = next(v for v in n.index if n.at[v, "type"] == "method" and n.at[v, "entry_year"] <= 2020 and len(str(n.at[v, "surface_form"])) >= 6)
    text = f"Models such as {n.at[late, 'surface_form']} and {n.at[early, 'surface_form']} introduced in 2024."
    r = deterministic_checks(text, [early], 2020, chk)
    assert r["year_after_cutoff"] and late in r["named_non_member"] and late in r["future_entity"]
    assert early not in r["named_non_member"]
    clean = deterministic_checks("Graph models of molecules.", [early], 2020, chk)
    assert not clean["year_after_cutoff"] and not clean["future_entity"]


def test_swapped_glosses_form_a_derangement_and_rates_sum_to_one():
    for n in (2, 3, 15, 60):
        p = derangement(n, seed=n)
        assert sorted(p) == list(range(n)) and all(i != j for i, j in enumerate(p))
    s = summarise(["accurate", "vague", "wrong", "wrong"])
    assert s["wrong"]["share"] == 0.5 and sum(s[k]["k"] for k in ("accurate", "vague", "wrong", "unparsed")) == 4
