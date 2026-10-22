"""Tests for tkh/evaluate/nulls.py: invariants of the structure shuffle, the semantic permutation and random labels."""

from collections import Counter
from pathlib import Path
import sys

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import validate  # noqa: E402
from tkh.coarsen import CLUSTER_RELATIONS, hubs  # noqa: E402
from tkh.config import load_config  # noqa: E402
from tkh.evaluate.nulls import permute_hierarchy  # noqa: E402
from tkh.export import assemble_hierarchies, write_outputs  # noqa: E402
from tkh.hierarchy import Params, build  # noqa: E402
from tkh.io import load, snapshot  # noqa: E402
from tkh.label import placeholder_labeller  # noqa: E402
from tkh.semantic import CONCEPT_TYPES  # noqa: E402
from tkh.temporal import match_and_name  # noqa: E402


def test_permuted_hierarchy_keeps_sizes_and_passes_the_validator(tmp_path):
    cfg = load_config(ROOT / "tests" / "fixtures" / "_input" / "config.toml")
    tkh = load(cfg)
    parts = build(tkh, cfg.cutoffs, cfg.budgets, Params.from_config({**cfg.method, "hub_frac": 1.0}))
    perm = permute_hierarchy(parts, tkh, 0, cfg.cutoffs)
    for c in parts:
        for a, b in zip(parts[c], perm[c]):
            assert sorted(map(len, a.values())) == sorted(map(len, b.values()))
            assert set().union(*a.values()) == set().union(*b.values())
    ids, events = match_and_name(perm, list(cfg.cutoffs))
    write_outputs(tmp_path, assemble_hierarchies(perm, ids, placeholder_labeller(tkh), cfg.budgets), events)
    assert validate.validate(tmp_path, cfg, tkh) == []
