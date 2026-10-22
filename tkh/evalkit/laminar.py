"""Hierarchy-level agreement: the level-pooled adjusted Rand index (HARI), a laminar analogue of ARI.

For two hierarchies over the same nodes with levels k = 0..K-1, with per-level pair-counting terms (index I_k,
expected E_k, maximum M_k, as in Hubert & Arabie's ARI):

    HARI = sum_k (I_k - E_k) / sum_k (M_k - E_k)

A pair of nodes counts once for every level at which both trees keep it together, so agreement deep in the tree
weighs more than agreement only at the top. HARI = 1 for identical trees and has expectation 0 when one tree's
node labels are permuted (the same permutation at every level), by linearity of the per-level terms.
"""

import numpy as np


def _terms(a, b):
    _, ai = np.unique(np.asarray(a), return_inverse=True)
    _, bi = np.unique(np.asarray(b), return_inverse=True)
    n = len(ai)
    cont = np.bincount(ai * (bi.max() + 1) + bi, minlength=(ai.max() + 1) * (bi.max() + 1)).astype(float)
    c2 = lambda x: x * (x - 1) / 2.0  # noqa: E731
    index = c2(cont).sum()
    sa = c2(np.bincount(ai).astype(float)).sum()
    sb = c2(np.bincount(bi).astype(float)).sum()
    total = c2(n)
    expected = sa * sb / total if total else 0.0
    return index, expected, (sa + sb) / 2.0


def hari(levels_a, levels_b, nodes):
    """levels_*: [ {key: set(members)} per level ]; nodes: the nodes to score (present in both)."""
    num = den = 0.0
    for ga, gb in zip(levels_a, levels_b):
        wa = {v: k for k, m in ga.items() for v in m}
        wb = {v: k for k, m in gb.items() for v in m}
        i, e, mx = _terms([wa[v] for v in nodes], [wb[v] for v in nodes])
        num += i - e
        den += mx - e
    return float(num / den) if den else 1.0
