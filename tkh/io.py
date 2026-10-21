"""Loads the TKH export and slices it into cumulative time snapshots (<= cutoff year), using publication years, not ingestion dates.

Snapshot rule (see notebooks/01_describe_graph.ipynb for the justification):
- a hyper-edge belongs to snapshot c iff provenance.article_year <= c;
- a node's entry year is the earliest publication year over its provenance
  articles and the articles of its incident hyper-edges; it belongs to
  snapshot c iff entry year <= c.
The node `year`, `first_seen_year` and edge `year` fields are deliberately
not used: they leak content from later papers into earlier snapshots.
"""

from dataclasses import dataclass, field
from pathlib import Path
import json

import pandas as pd

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
CUTOFFS = (2020, 2022, 2024, 2026)


@dataclass
class TKH:
    meta: dict
    nodes: pd.DataFrame      # one row per node, indexed by id
    edges: pd.DataFrame      # one row per hyper-edge, indexed by id
    articles: pd.DataFrame   # collection10_articles.csv, indexed by MVKG article id


@dataclass
class Snapshot:
    cutoff: int
    node_ids: set
    edges: pd.DataFrame      # subset of TKH.edges
    articles: set = field(default_factory=set)


def load_tkh(data_dir=DATA_DIR):
    data_dir = Path(data_dir)
    raw = json.loads((data_dir / "tkh_collection10.json").read_text())
    articles = pd.read_csv(data_dir / "collection10_articles.csv", dtype={"arxiv_id": str}).set_index("id")

    nodes = pd.DataFrame(raw["nodes"]).set_index("id")
    nodes["prov_articles"] = nodes["provenance"].map(lambda p: list(p.get("articles", [])))
    nodes["entity_id"] = nodes["provenance"].map(lambda p: p.get("entity_id"))

    edges = pd.DataFrame(raw["hyperedges"]).set_index("id")
    edges["article_id"] = edges["provenance"].map(lambda p: p["article_id"])
    edges["article_year"] = edges["provenance"].map(lambda p: p["article_year"])
    edges["arity"] = edges["members"].map(lambda m: len(set(m)))

    year_of = articles["year"].to_dict()
    incident = edges[["members", "article_id"]].explode("members").groupby("members")["article_id"].agg(set)
    nodes["entry_year"] = [
        min(year_of[a] for a in set(prov) | incident.get(nid, set()))
        for nid, prov in nodes["prov_articles"].items()
    ]
    return TKH(meta=raw["meta"], nodes=nodes, edges=edges, articles=articles)


def snapshot(tkh, cutoff):
    edges = tkh.edges[tkh.edges["article_year"] <= cutoff]
    node_ids = set(tkh.nodes.index[tkh.nodes["entry_year"] <= cutoff])
    articles = set(tkh.articles.index[tkh.articles["year"] <= cutoff])
    return Snapshot(cutoff=cutoff, node_ids=node_ids, edges=edges, articles=articles)


def make_snapshots(tkh, cutoffs=CUTOFFS):
    return [snapshot(tkh, c) for c in cutoffs]
