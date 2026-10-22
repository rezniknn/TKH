"""Tests for tkh/structure.py (notebook 03) on a hand-built three-paper graph."""

from pathlib import Path
from types import SimpleNamespace
import math
import sys

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from tkh import structure as st  # noqa: E402


@pytest.fixture()
def toy():
    # papers 1 (2018), 2 (2020), 3 (2022); method M1 presented by 1, extended by 2 and 3; task T shared by all
    nodes = pd.DataFrame({
        "type": ["article", "article", "article", "method", "method", "method", "task", "task", "author", "cited_work"],
        "surface_form": ["P1", "P2", "P3", "SchNet", "MethodB", "MethodC", "generic task", "rare task", "Ann", "SchNet"],
        "prov_articles": [[1], [2], [3], [1, 2, 3], [2], [3], [1, 2, 3], [2, 3], [1, 2], [2]],
        "aliases": [None] * 10,
    }, index=["a1", "a2", "a3", "M1", "M2", "M3", "T", "R", "au", "cw"])
    edges = pd.DataFrame({
        "relation_type": ["presents", "presents", "presents", "extends", "extends", "addresses", "addresses", "addresses",
                          "authored_by", "authored_by", "cites"],
        "members": [["a1", "M1"], ["a2", "M2"], ["a3", "M3"], ["M2", "M1"], ["M3", "M1"], ["M1", "T"], ["M2", "T", "R"],
                    ["M3", "T", "R"], ["a1", "au"], ["a2", "au"], ["a2", "cw"]],
        "article_id": [1, 2, 3, 2, 3, 1, 2, 3, 1, 2, 2],
    }, index=[f"h{i}" for i in range(11)])
    edges["article_year"] = edges["article_id"].map({1: 2018, 2: 2020, 3: 2022})
    articles = pd.DataFrame({"year": [2018, 2020, 2022], "title": ["P1", "P2", "P3"]}, index=[1, 2, 3])
    return SimpleNamespace(nodes=nodes, edges=edges, articles=articles)


def test_sharing_and_lineage(toy):
    sh = st.sharing_by_type(toy)
    assert sh.loc["method", "in >= 2 papers"] == 1 and sh.loc["task", "paper pairs linked"] == 3
    assert sh.loc["article", "in >= 2 papers"] == 0 and sh.loc["author", "paper pairs linked"] == 1
    assert st.lineage_pairs(toy) == [(2, 1), (3, 1)]          # later paper extends the earlier paper's presented method
    assert (2, 1) in st.citation_name_pairs(toy)               # paper 2 cites a work named like paper 1's method


def test_typed_links_label_lineage_and_hubs(toy):
    tl = st.typed_links(toy, max_paper_share=0.7)               # T (3 of 3 papers) is a hub, R (2 of 3) is not
    lin = tl[tl["link"] == "extends -> presents (lineage)"]
    assert set(zip(lin["earlier"], lin["later"])) == {(1, 2), (1, 3)}
    assert tl.loc[tl["node"] == "T", "hub"].all() and not tl.loc[tl["node"] == "R", "hub"].any()
    assert set(tl.loc[tl["node"] == "M1", "link"]) >= {"extends ~ extends"}


def test_pair_matrix_idf_and_hub_exclusion(toy):
    M, via = st.pair_matrix(toy, ("task",), weight="idf")
    assert M.loc[2, 3] == pytest.approx(math.log(3 / 2) + math.log(3 / 3))   # R adds log(3/2); T (all papers) adds 0
    M2, _ = st.pair_matrix(toy, ("task",), weight="count", max_paper_share=0.7)
    assert M2.loc[2, 3] == 1 and M2.loc[1, 2] == 0                          # only R survives the hub filter
    s = st.link_summary(M2)
    assert s["linked pairs"] == 1 and s["components"] == 2 and s["isolated papers"] == 1


def test_two_papers_presenting_the_same_node_are_not_lineage(toy):
    e = toy.edges.copy()
    e.at["h2", "members"] = ["a3", "M1"]           # paper 3 now presents M1 too, and nobody else extends it
    e = e.drop(index=["h3", "h4"])
    t = SimpleNamespace(nodes=toy.nodes, edges=e, articles=toy.articles)
    tl = st.typed_links(t, max_paper_share=None)
    assert not (tl["link"] == "extends -> presents (lineage)").any()


def test_matrix_agreement_aligns_and_detects_association(toy):
    A, _ = st.pair_matrix(toy, ("task",), weight="count")
    shuffled = A.loc[A.index[::-1], A.index[::-1]]
    r = st.matrix_agreement(A, shuffled, n_perm=19)
    assert r["pairs in both"] == r["pairs in A"] and r["spearman"] == pytest.approx(1.0)
