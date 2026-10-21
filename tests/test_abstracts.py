"""Offline tests for tkh/abstracts.py (no network): routes, title matching, and response parsing."""

from pathlib import Path
import sys

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from tkh import abstracts as ab  # noqa: E402
from tkh.config import load_config  # noqa: E402
from tkh.io import load  # noqa: E402

ATOM_SAMPLE = b"""<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <entry>
    <id>http://arxiv.org/abs/1704.01212v1</id>
    <published>2017-04-04T19:06:01Z</published>
    <title>Neural Message Passing for
      Quantum Chemistry</title>
    <summary>  Supervised learning on molecules has incredible potential.  </summary>
  </entry>
  <entry><id>http://arxiv.org/api/errors#bad</id><title>Error</title><summary>bad id</summary></entry>
</feed>"""


def test_parse_arxiv_extracts_fields_and_drops_errors():
    (r,) = ab._parse_arxiv(ATOM_SAMPLE)
    assert r == {"arxiv_id": "1704.01212", "title": "Neural Message Passing for Quantum Chemistry",
                 "abstract": "Supervised learning on molecules has incredible potential.", "published": "2017-04-04"}


def test_inverted_index_reconstruction():
    inv = {"Graph": [0], "networks": [1, 4], "learn": [2], "from": [3]}
    assert ab.inverted_index_to_text(inv) == "Graph networks learn from networks"
    assert ab.inverted_index_to_text(None) == ""


@pytest.mark.parametrize("ours,theirs,ok", [
    ("Matbench Discovery: A framework to evaluate machine learning crystal st",  # truncated in the export
     "Matbench Discovery: A framework to evaluate machine learning crystal stability predictions", True),
    ("E(3)-Equivariant Graph Neural Networks", "E(3)-equivariant graph neural networks", True),
    ("Machine Learning Interatomic Potentials: A Review and Framework for Understanding MLIPs",
     "A practical guide to machine learning interatomic potentials -- Status and future", False),
])
def test_title_similarity(ours, theirs, ok):
    assert (ab.title_similarity(ours, theirs) >= 0.9) is ok


def test_routes_cover_every_article_with_one_route():
    tkh = load(load_config())
    r = ab.routes(tkh)
    assert len(r) == len(tkh.articles) and set(r["route"]) <= {"arxiv id", "doi", "title"}
    assert (r.loc[r["route"] == "arxiv id", "arxiv_id"].map(lambda x: isinstance(x, str) and len(x) > 0)).all()
