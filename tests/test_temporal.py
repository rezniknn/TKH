"""Property test for tkh/temporal.py: the id/event matcher must always produce a lineage the validator accepts."""

from pathlib import Path
import random
import sys

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import validate  # noqa: E402
from tkh.temporal import match_and_name  # noqa: E402


def _random_nested(nodes, rng, depth):
    """Random laminar partition of nodes into `depth` levels (coarse to fine)."""
    levels, current = [], [list(nodes)]
    for _ in range(depth):
        nxt = []
        for block in current:
            rng.shuffle(block)
            cuts = sorted(rng.sample(range(1, len(block)), min(len(block) - 1, rng.randint(0, 3)))) if len(block) > 1 else []
            parts = [block[i:j] for i, j in zip([0] + cuts, cuts + [len(block)])]
            nxt += [p for p in parts if p]
        levels.append(nxt)
        current = [list(p) for p in nxt]
    return [{i: set(b) for i, b in enumerate(lv)} for lv in levels]


@pytest.mark.parametrize("trial", range(300))
def test_matcher_always_produces_a_valid_lineage(trial):
    rng = random.Random(trial)
    cutoffs = [2020, 2022, 2024, 2026]
    universe = [f"n{i}" for i in range(rng.randint(5, 40))]
    sizes = sorted(rng.sample(range(2, len(universe) + 1), 4)) if len(universe) >= 5 else [len(universe)] * 4
    clusters = {c: _random_nested(universe[:n], rng, 2) for c, n in zip(cutoffs, sizes)}
    ids, events = match_and_name(clusters, cutoffs)
    index = {c: {ids[c][k][key]: k for k, g in enumerate(clusters[c]) for key in g} for c in cutoffs}
    members = {c: {ids[c][k][key]: m for k, g in enumerate(clusters[c]) for key, m in g.items()} for c in cutoffs}
    rep = validate.Report()
    validate.check_events(events, index, members, cutoffs, rep)
    validate.check_id_namespace(index, cutoffs, rep)
    assert rep.lines == [], rep.lines[:5]
