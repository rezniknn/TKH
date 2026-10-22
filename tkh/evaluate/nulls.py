"""Random-labels null of a finished hierarchy (the brief's "random labels"), so that every metric is compared with chance.

permute_hierarchy(parts, tkh, seed, cutoffs)
    One permutation of the concept nodes, within (type x entry period x paper-count bin), applied to every level and
    snapshot of a hierarchy. Sizes, nesting, the temporal structure and the anchored nodes are kept, so the output
    passes the validator and can be scored on every metric like the evaluated tree. It needs no method re-run.

The graph-level null (the type- and period-preserving hypergraph configuration model, through which any method is
re-run) is tkh/evalkit/exports.configuration_null.
"""

from dataclasses import replace
import random

import numpy as np

from tkh.structure import CONCEPT_RELATIONS as CLUSTER_RELATIONS, CONCEPT_TYPES


def _period(year, cutoffs):
    for i, c in enumerate(sorted(cutoffs)):
        if year <= c:
            return i
    return len(cutoffs)


def _paper_bin(n):
    return 0 if n <= 1 else 1 if n == 2 else 2


def permute_hierarchy(parts, tkh, seed, cutoffs):
    """parts with concept nodes relabelled by one permutation within (type, entry period, paper-count bin)."""
    rng = random.Random(seed)
    nodes = tkh.nodes
    e = tkh.edges
    papers = {}
    for m, a in zip(e["members"], e["article_id"]):
        for v in m:
            papers.setdefault(v, set()).add(a)
    strata = {}
    for v in sorted(nodes.index[nodes["type"].isin(CONCEPT_TYPES)]):
        n_pap = len(set(nodes.at[v, "prov_articles"]) | papers.get(v, set()))
        strata.setdefault((nodes.at[v, "type"], _period(nodes.at[v, "entry_year"], cutoffs), _paper_bin(n_pap)), []).append(v)
    perm = {}
    for ids in strata.values():
        img = ids[:]
        rng.shuffle(img)
        perm.update(zip(ids, img))
    return {c: [{g: {perm.get(v, v) for v in mem} for g, mem in lv.items()} for lv in levels]
            for c, levels in parts.items()}
