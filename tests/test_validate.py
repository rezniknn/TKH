"""Proof the validator bites (6a.2): validate.py must pass the valid fixture and reject every broken fixture in tests/fixtures/.

Each broken fixture must fail with exactly its expected violation codes (see
tests/make_fixtures.py), so a fixture that fails for an unrelated reason does not count
as a pass. Run: .venv/bin/python -m pytest tests/
"""

from pathlib import Path
import copy
import filecmp
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests"))

import make_fixtures  # noqa: E402
import mock_output  # noqa: E402
from tkh.config import load_config  # noqa: E402
from tkh.export import write_outputs  # noqa: E402
from tkh.io import load  # noqa: E402

FIXTURES = ROOT / "tests" / "fixtures"
FIXTURE_CONFIG = FIXTURES / "_input" / "config.toml"
EXPECTED = make_fixtures.expected_codes()


def run_validator(out_dir, config=FIXTURE_CONFIG, *extra):
    p = subprocess.run([sys.executable, str(ROOT / "validate.py"), str(out_dir), "--config", str(config), *extra],
                       capture_output=True, text=True)
    codes = {line.split()[0] for line in p.stdout.splitlines() if line.strip()}
    return p.returncode, codes, p.stdout + p.stderr


def test_valid_fixture_passes():
    rc, codes, out = run_validator(FIXTURES / "valid")
    assert rc == 0 and not codes, out


@pytest.mark.parametrize("name", sorted(EXPECTED))
def test_broken_fixture_is_rejected_for_the_right_reason(name):
    rc, codes, out = run_validator(FIXTURES / name)
    assert rc == 1, f"{name}: validator did not fail\n{out}"
    assert codes == EXPECTED[name], f"{name}: expected {sorted(EXPECTED[name])}, got {sorted(codes)}\n{out}"


def test_every_mutation_has_a_committed_fixture_and_vice_versa():
    on_disk = {p.name for p in FIXTURES.iterdir() if p.is_dir() and not p.name.startswith("_")} - {"valid"}
    assert on_disk == set(EXPECTED)


def test_committed_fixtures_are_up_to_date(tmp_path):
    fresh = make_fixtures.build(tmp_path)
    for d in sorted(p for p in FIXTURES.iterdir() if p.is_dir()):
        cmp = filecmp.dircmp(d, fresh / d.name)
        stack, diffs = [cmp], []
        while stack:
            c = stack.pop()
            diffs += c.left_only + c.right_only + c.diff_files
            stack += c.subdirs.values()
        assert not diffs, f"{d.name} is stale ({diffs}); run: python tests/make_fixtures.py"


def test_usage_errors_exit_2(tmp_path):
    assert run_validator(tmp_path / "does_not_exist")[0] == 2
    assert run_validator(FIXTURES / "valid", tmp_path / "missing.toml")[0] == 2


def test_budget_override_on_command_line_is_enforced():
    rc, codes, _ = run_validator(FIXTURES / "valid", FIXTURE_CONFIG, "--budgets", "3", "4")
    assert rc == 1 and {"BUDGET_EXCEEDED", "BUDGETS_MISMATCH"} <= codes


# ---------------------------------------------------------------- real-data scale

@pytest.fixture(scope="module")
def real_mock():
    cfg = load_config()
    return cfg, mock_output.mock_outputs(load(cfg), cfg.cutoffs, cfg.budgets)


def test_mock_of_real_data_passes(real_mock, tmp_path):
    cfg, (h, e) = real_mock
    write_outputs(tmp_path, h, e)
    rc, codes, out = run_validator(tmp_path, cfg.source)
    assert rc == 0, out[:2000]


@pytest.mark.parametrize("mutation,code", [
    ("future", "FUTURE_MEMBER"), ("duplicate", "NODE_IN_TWO_CLUSTERS"), ("drop", "NODE_NOT_COVERED"),
    ("overflow", "BUDGET_EXCEEDED"),
])
def test_mutations_of_real_mock_are_caught(real_mock, tmp_path, mutation, code):
    cfg, (h, e) = real_mock
    h, e = copy.deepcopy(h), copy.deepcopy(e)
    first, last = min(h), max(h)
    lvl1 = [s for s in h[first]["supernodes"] if s["level"] == 1]
    if mutation == "future":  # a node that only enters in the last snapshot, put into the first one
        early = {m for s in h[first]["supernodes"] for m in s["member_ids"]}
        late = next(m for s in h[last]["supernodes"] for m in s["member_ids"] if m not in early)
        lvl1[0]["member_ids"].append(late)
    elif mutation == "duplicate":
        lvl1[1]["member_ids"].append(lvl1[0]["member_ids"][0])
    elif mutation == "drop":
        lvl1[0]["member_ids"].pop()
    elif mutation == "overflow":
        level0 = [s for s in h[first]["supernodes"] if s["level"] == 0]
        for i in range(cfg.budgets[0] + 1 - len(level0)):
            victim = next(s for s in level0 if len(s["member_ids"]) > 1)
            m = victim["member_ids"].pop()
            h[first]["supernodes"].append({**victim, "id": f"extra{i}", "member_ids": [m]})
    write_outputs(tmp_path, h, e)
    rc, codes, out = run_validator(tmp_path, cfg.source)
    assert rc == 1 and code in codes, out[:2000]
