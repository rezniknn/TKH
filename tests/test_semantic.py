"""Tests for tkh/semantic.py (node text and lexical vectors) and tkh/evaluate/groundtruth.py (name matching)."""

from pathlib import Path
import sys

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from tkh import semantic as sm  # noqa: E402
from tkh.config import load_config  # noqa: E402
from tkh.evaluate.groundtruth import key, load_ground_truth, name_index, question_targets  # noqa: E402
from tkh.io import load  # noqa: E402


@pytest.mark.parametrize("raw,clean", [
    ("Self‑attention", "Self-attention"),   # NFKC maps U+2011 to U+2010, which must still become '-'
    ("a–b—c−d", "a-b-c-d"),
    ("x y z", "x y z"),
    ("  many   spaces ", "many spaces"),
])
def test_clean(raw, clean):
    assert sm.clean(raw) == clean


@pytest.mark.parametrize("a,b", [("MACE (general)", "MACE"), ("Matbench-Discovery", "Matbench Discovery"),
                                 ("Tensor‑Field Networks", "tensor field networks")])
def test_groundtruth_key_normalises_variants(a, b):
    assert key(a) == key(b)


@pytest.fixture(scope="module")
def real():
    cfg = load_config()
    return cfg, load(cfg)


def test_names_include_aliases(real):
    _, tkh = real
    nm = sm.names(tkh)
    with_alias = [v for v, a in tkh.nodes["aliases"].items() if isinstance(a, list) and a]
    assert with_alias and all(tkh.nodes.at[v, "aliases"][0] in nm[v] for v in with_alias)


def test_alias_matching_resolves_names_absent_from_surface_forms(real):
    _, tkh = real
    idx = name_index(tkh)
    alias_only = [a for v, al in tkh.nodes["aliases"].items() if isinstance(al, list)
                  for a in al if key(a) not in {key(s) for s in tkh.nodes["surface_form"]}]
    assert alias_only and all(key(a) in idx for a in alias_only)


def test_question_targets_restrict_to_requested_types(real):
    cfg, tkh = real
    qt = question_targets(tkh, load_ground_truth(cfg.ground_truth), types=sm.CONCEPT_TYPES)
    assert qt and all(tkh.nodes.at[i, "type"] in sm.CONCEPT_TYPES
                      for q in qt.values() for part in q.values() for ids in part.values() for i in ids)


def test_vectors_are_normalised_and_cosine_is_self_one(real):
    _, tkh = real
    nodes = sorted(tkh.nodes.index[tkh.nodes["type"] == "metric"])
    for kind in ("word", "char"):
        X, _ = sm.vectorize(sm.node_texts(tkh, nodes, "name"), kind)
        S = sm.cosine(X)
        nonempty = X.getnnz(axis=1) > 0
        assert np.allclose(np.diag(S)[nonempty], 1.0)
    Z = sm.lsa(X, 20)
    assert Z.shape == (len(nodes), 20) and np.allclose(np.linalg.norm(Z, axis=1), 1.0)


def test_context_text_extends_name_text(real):
    _, tkh = real
    nodes = sorted(tkh.nodes.index[tkh.nodes["type"].isin(["dataset", "metric"])])[:50]
    names, ctx = sm.node_texts(tkh, nodes, "name"), sm.node_texts(tkh, nodes, "context")
    assert all(c.startswith(n) for n, c in zip(names, ctx)) and sum(len(c) > len(n) for n, c in zip(names, ctx)) > 0
