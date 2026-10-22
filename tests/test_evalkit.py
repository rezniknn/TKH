"""Tests for the method-independent evaluator primitives (tkh/evalkit)."""

from collections import Counter
from pathlib import Path
import random
import re
import sys

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from tkh.config import load_config  # noqa: E402
from tkh.evalkit import degrade, exports, laminar  # noqa: E402
from tkh.evalkit.entailment import Entailment, summarise  # noqa: E402
from tkh.evalkit.queries import known_item_queries  # noqa: E402
from tkh.io import load  # noqa: E402


@pytest.fixture(scope="module")
def real():
    cfg = load_config()
    return cfg, load(cfg), exports.load_raw(cfg.graph)


def tree(n=60, sizes=(3, 12), seed=0):
    rng = random.Random(seed)
    nodes = [f"n{i}" for i in range(n)]
    fine = [nodes[i::sizes[1]] for i in range(sizes[1])]
    top = {g: set().union(*map(set, fine[g::sizes[0]])) for g in range(sizes[0])}
    return [top, {g: set(m) for g, m in enumerate(fine)}], nodes


def test_hari_identity_and_chance():
    lv, nodes = tree()
    assert laminar.hari(lv, lv, nodes) == pytest.approx(1.0)
    vals = []
    for s in range(200):
        perm = dict(zip(nodes, random.Random(s).sample(nodes, len(nodes))))
        pl = [{g: {perm[v] for v in m} for g, m in l.items()} for l in lv]
        vals.append(laminar.hari(lv, pl, nodes))
    assert abs(np.mean(vals)) < 0.03


def test_degradation_keeps_laminarity_and_sizes():
    lv, nodes = tree()
    d = degrade.swap_paths(lv, 0.5, seed=1)
    for a, b in zip(lv, d):
        assert sorted(map(len, a.values())) == sorted(map(len, b.values()))
    owner = {v: g for g, m in d[0].items() for v in m}
    assert all(len({owner[v] for v in m}) == 1 for m in d[1].values())     # each fine group in one parent
    assert laminar.hari(lv, d, nodes) < 1.0


def test_configuration_null_preserves_invariants_on_all_relations(real):
    cfg, tkh, raw = real
    null, diag = exports.configuration_null(raw, 0, cfg.cutoffs)          # check_null runs inside and raises on violation
    assert 0 < diag["retained_incidence"] < 0.9
    rel = Counter(e["relation_type"] for a, e in zip(raw["hyperedges"], null["hyperedges"]) if a["members"] != e["members"])
    assert {"claims", "cites", "authored_by", "addresses", "evaluated_on"} <= set(rel)   # rewired beyond the method's input
    assert "presents" not in rel
    again, _ = exports.configuration_null(raw, 0, cfg.cutoffs)
    other, _ = exports.configuration_null(raw, 1, cfg.cutoffs)
    assert again["hyperedges"] == null["hyperedges"] != other["hyperedges"]


def test_perturb_removes_ten_percent_of_every_period(real):
    cfg, tkh, raw = real
    pert, dropped = exports.perturb(raw, 0.10, 0, cfg.cutoffs)
    per = Counter(exports.period(e["provenance"]["article_year"], cfg.cutoffs) for e in raw["hyperedges"])
    gone = Counter(exports.period(e["provenance"]["article_year"], cfg.cutoffs) for e in raw["hyperedges"] if e["id"] in set(dropped))
    assert all(gone[p] == round(0.10 * n) for p, n in per.items())
    assert len(pert["hyperedges"]) == len(raw["hyperedges"]) - len(dropped)


def test_known_item_queries_mask_the_target(real):
    cfg, tkh, raw = real
    qs = known_item_queries(tkh, 2026)
    sf = tkh.nodes["surface_form"].to_dict()
    for q in qs[:300]:
        nm = sf[q["target"]]
        assert not re.search(r"(?<![\w-])" + re.escape(nm) + r"(?![\w-])", q["text"], flags=re.IGNORECASE)
    assert len(qs) > 300


class FakeLLM:
    def __init__(self, answers):
        self.answers = answers

    def complete(self, prompt):
        for k, v in self.answers.items():
            if k in prompt:
                return v
        return {"verdict": "supported", "quote": "nothing like this exists"}

    def key(self, prompt):
        return "k"


def test_quote_check_rejects_unsupported_quotes_and_decomposition_check(real):
    cfg, tkh, raw = real
    ent = Entailment(tkh, cfg, llm=FakeLLM({"Claim: A": {"verdict": "supported", "quote": "SchNet [method]"},
                                            "Claim: B": {"verdict": "supported", "quote": "invented line"},
                                            "Label: L1": {"claims": ["graph networks"]},
                                            "Label: L2": {"claims": ["something entirely new here"]}}))
    items = ["SchNet [method]", "QM9 [dataset]"]
    assert ent.judge(2026, "A", items)["supported"] is True
    j = ent.judge(2026, "B", items)
    assert j["verdict"] == "supported" and j["supported"] is False          # a quote not in the pack does not count
    assert ent.decompose("L1", "Graph networks for molecules")[1] is True
    claims, ok = ent.decompose("L2", "Graph networks for molecules")
    assert ok is False and claims == ["L2", "Graph networks for molecules"]


def test_rogan_gladen_summary():
    labs = [{"snapshot": 2026, "level": 1, "id": f"s{i}", "n_claims": 2, "decomposition_ok": True,
             "over_claim_held_out": i < 5, "over_claim_all": i < 3} for i in range(20)]
    claims = [{"snapshot": 2026, "level": 1, "id": f"s{i}", "pass": "held_out", "verdict": "x", "quote_ok": True,
               "supported": not (i < 5 and k == 0)} for i in range(20) for k in range(2)]
    ctrls = [{"snapshot": 2026, "level": 1, "id": f"s{i}", "control": "sibling", "truth": False, "supported": i % 5 == 0}
             for i in range(20)] + [{"snapshot": 2026, "level": 1, "id": f"s{i}", "control": "true", "truth": True,
                                     "supported": i % 10 != 0} for i in range(20)]
    s = summarise(labs, claims, ctrls, n_boot=200)
    assert s["Se_sibling"]["value"] == pytest.approx(0.8) and s["Sp"]["value"] == pytest.approx(0.9)
    assert s["valid"] is True                                               # J = 0.7
    u = (5 / 40 + 0.9 - 1) / 0.7                                            # claim-level Rogan-Gladen
    assert s["corrected_over_claim_held_out"]["claim_level"] == pytest.approx(u)
    assert s["raw_over_claim_held_out"]["value"] == pytest.approx(0.25)


def test_validator_flags_label_inputs_outside_the_seen_half(tmp_path):
    import json
    import shutil
    import validate
    cfg = load_config()
    tkh = load(cfg)
    src = ROOT / "out"
    for c in cfg.cutoffs:
        shutil.copytree(src / str(c), tmp_path / str(c))
    shutil.copy(src / "temporal_events.json", tmp_path / "temporal_events.json")
    assert validate.validate(tmp_path, cfg, tkh) == []
    li = json.loads((tmp_path / "2026" / "label_inputs.json").read_text())
    sid = next(k for k, v in li.items() if v["held_out"])
    li[sid]["shown"] = li[sid]["shown"] + [li[sid]["held_out"][0]]          # the labeller "saw" a held-out member
    (tmp_path / "2026" / "label_inputs.json").write_text(json.dumps(li))
    assert any("LABEL_INPUT_LEAK" in line for line in validate.validate(tmp_path, cfg, tkh))
