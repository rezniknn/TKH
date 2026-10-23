"""Loads the TKH export and slices it into cumulative time snapshots (<= cutoff year), using publication years, not ingestion dates.

Snapshot rule (see notebooks/01_describe_graph.ipynb for the justification):
- a hyper-edge belongs to snapshot c iff provenance.article_year <= c;
- a node's entry year is the earliest publication year over its provenance
  articles and the articles of its incident hyper-edges; it belongs to
  snapshot c iff entry year <= c.
The node `year`, `first_seen_year` and edge `year` fields are deliberately
not used: they leak content from later papers into earlier snapshots.

Input paths come from tkh.config; nothing here assumes particular file names.
"""

from dataclasses import dataclass, field
from pathlib import Path
import json

import pandas as pd


@dataclass
class TKH:
    meta: dict
    nodes: pd.DataFrame      # one row per node, indexed by id
    edges: pd.DataFrame      # one row per hyper-edge, indexed by id
    articles: pd.DataFrame   # one row per source article, indexed by article id; column 'year' at least


@dataclass
class Snapshot:
    cutoff: int
    node_ids: set
    edges: pd.DataFrame      # subset of TKH.edges
    articles: set = field(default_factory=set)


def load(cfg):
    """Load the TKH described by a tkh.config.Config."""
    return load_tkh(cfg.graph, cfg.articles)


def load_tkh(graph_path, articles_path=None):
    """Load a TKH export. articles_path is optional: without it, article years come from
    hyper-edge provenance and titles/arxiv ids from article nodes."""
    graph_path = Path(graph_path)
    return from_raw(json.loads(graph_path.read_text()), articles_path, graph_path)


def from_raw(raw, articles_path=None, source="graph"):
    """TKH from an export already parsed into a dict (e.g. a null-model export built in memory)."""
    raw = json.loads(json.dumps(raw))  # private copy: ids are normalised in place below
    missing = {"nodes", "hyperedges"} - set(raw)
    if missing:
        raise ValueError(f"{source}: missing top-level keys {sorted(missing)}")

    for n in raw["nodes"]:  # ids are strings throughout (the output schema requires it)
        n["id"] = str(n["id"])
    for e in raw["hyperedges"]:
        e["id"], e["members"] = str(e["id"]), [str(m) for m in e["members"]]
    nodes = pd.DataFrame(raw["nodes"]).set_index("id")
    nodes["prov_articles"] = nodes["provenance"].map(lambda p: list((p or {}).get("articles", [])))
    nodes["entity_id"] = nodes["provenance"].map(lambda p: (p or {}).get("entity_id"))

    edges = pd.DataFrame(raw["hyperedges"]).set_index("id")
    edges["article_id"] = edges["provenance"].map(lambda p: p["article_id"])
    edges["article_year"] = edges["provenance"].map(lambda p: p["article_year"])
    edges["arity"] = edges["members"].map(lambda m: len(set(m)))

    articles = _articles(nodes, edges, articles_path)
    year_of = articles["year"].to_dict()
    referenced = set(edges["article_id"]) | {a for arts in nodes["prov_articles"] for a in arts}
    unknown = referenced - set(year_of)
    if unknown:
        raise ValueError(f"no publication year for {len(unknown)} article ids, e.g. {sorted(unknown)[:5]}")

    incident = edges[["members", "article_id"]].explode("members").groupby("members")["article_id"].agg(set)
    undated = [nid for nid, prov in nodes["prov_articles"].items() if not set(prov) | incident.get(nid, set())]
    if undated:
        raise ValueError(f"{len(undated)} nodes have no provenance article and no hyper-edge, so no entry year: {undated[:5]}")
    nodes["entry_year"] = [
        min(year_of[a] for a in set(prov) | incident.get(nid, set()))
        for nid, prov in nodes["prov_articles"].items()
    ]
    return TKH(meta=raw.get("meta", {}), nodes=nodes, edges=edges, articles=articles)


def _articles(nodes, edges, articles_path):
    from_edges = edges.groupby("article_id")["article_year"].agg(["min", "max"])
    if (from_edges["min"] != from_edges["max"]).any():
        raise ValueError("an article has inconsistent article_year across its hyper-edges")
    derived = from_edges["min"].rename("year").to_frame()
    art_nodes = nodes[nodes["type"] == "article"]
    if len(art_nodes):
        key = art_nodes["prov_articles"].map(lambda a: a[0] if a else None)
        meta = pd.DataFrame({
            "title": art_nodes["surface_form"].values,
            "arxiv_id": art_nodes["provenance"].map(lambda p: p.get("arxiv_id")).values,
            "node_id": art_nodes.index,
        }, index=key.values)
        derived = derived.join(meta[~meta.index.isna()], how="left")
    derived.index.name = "id"
    if articles_path is None:
        return derived

    csv = pd.read_csv(articles_path, dtype={"arxiv_id": str})
    if not {"id", "year"} <= set(csv.columns):
        raise ValueError(f"{articles_path}: needs columns 'id' and 'year', has {list(csv.columns)}")
    csv = csv.set_index("id")
    both = derived.index.intersection(csv.index)
    clash = both[derived.loc[both, "year"] != csv.loc[both, "year"]]
    if len(clash):
        raise ValueError(f"{articles_path}: year disagrees with hyper-edge provenance for articles {list(clash[:5])}")
    if "node_id" in derived:
        csv = csv.join(derived[["node_id"]], how="left")
    return csv


def snapshot(tkh, cutoff):
    edges = tkh.edges[tkh.edges["article_year"] <= cutoff]
    node_ids = set(tkh.nodes.index[tkh.nodes["entry_year"] <= cutoff])
    articles = set(tkh.articles.index[tkh.articles["year"] <= cutoff])
    return Snapshot(cutoff=cutoff, node_ids=node_ids, edges=edges, articles=articles)


def make_snapshots(tkh, cutoffs):
    return [snapshot(tkh, c) for c in sorted(cutoffs)]
