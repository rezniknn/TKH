"""Evaluator-owned seen / held-out split of a super-node's members (the E3/M3 circularity control).

A labeller under evaluation may only see the `seen` half; the judge's primary evidence is the `held_out` half.
validate.py checks out/<cutoff>/label_inputs.json against this split. The split is a deterministic function of
the member set and a seed, so any method can reproduce it.
"""

import hashlib
import random


def split_members(members, seed=0):
    """(seen, held_out): a deterministic half split of the sorted members, seeded by the member set."""
    ms = sorted(members)
    h = hashlib.sha256(("|".join(ms) + f"#{seed}").encode()).hexdigest()
    rng = random.Random(int(h[:16], 16))
    rng.shuffle(ms)
    k = (len(ms) + 1) // 2
    return sorted(ms[:k]), sorted(ms[k:])
