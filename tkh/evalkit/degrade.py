"""Controlled degradations of a hierarchy, for the minimum detectable effect of each metric.

swap_paths(parts, frac, seed): pick frac of the concept nodes, pair them at random, and exchange the two nodes'
entire ancestor paths (their super-node at every level). Laminarity, every super-node's size and the tree shape are
kept; only membership is degraded, by a known amount.
"""

import random


def swap_paths(levels, frac, seed=0, nodes=None):
    """levels: [ {key: set(members)} per level ]; returns degraded levels (same keys)."""
    rng = random.Random(seed)
    where = [{v: g for g, m in lv.items() for v in m} for lv in levels]
    pool = sorted(nodes if nodes is not None else where[-1])
    pick = rng.sample(pool, 2 * (int(frac * len(pool)) // 2))
    out = [{g: set(m) for g, m in lv.items()} for lv in levels]
    for a, b in zip(pick[0::2], pick[1::2]):
        for k, w in enumerate(where):
            ga, gb = w[a], w[b]
            if ga != gb:
                out[k][ga].discard(a); out[k][ga].add(b)
                out[k][gb].discard(b); out[k][gb].add(a)
    return out
