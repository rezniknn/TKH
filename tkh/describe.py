"""T1: per-snapshot statistics: node/edge counts, node types, hyper-edge arity distribution, time span, growth between snapshots, data-quality issues."""

import re
import unicodedata

import pandas as pd


# ---------------------------------------------------------------- per snapshot

def snapshot_summary(tkh, snaps):
    rows = []
    for s in snaps:
        years = tkh.articles.loc[sorted(s.articles), "year"]
        rows.append({
            "snapshot": f"<={s.cutoff}",
            "articles": len(s.articles),
            "nodes": len(s.node_ids),
            "hyperedges": len(s.edges),
            "incidences": int(s.edges["arity"].sum()),
            "first_year": int(years.min()),
            "last_year": int(years.max()),
            "components": len(components(s)),
            "largest_component_share": max(map(len, components(s))) / len(s.node_ids),
        })
    return pd.DataFrame(rows).set_index("snapshot")


def node_type_counts(tkh, snaps):
    return pd.DataFrame({
        f"<={s.cutoff}": tkh.nodes.loc[sorted(s.node_ids), "type"].value_counts() for s in snaps
    }).fillna(0).astype(int).sort_values(f"<={snaps[-1].cutoff}", ascending=False)


def relation_type_counts(snaps):
    return pd.DataFrame({
        f"<={s.cutoff}": s.edges["relation_type"].value_counts() for s in snaps
    }).fillna(0).astype(int).sort_values(f"<={snaps[-1].cutoff}", ascending=False)


def arity_summary(snaps):
    rows = []
    for s in snaps:
        a = s.edges["arity"]
        rows.append({
            "snapshot": f"<={s.cutoff}", "mean": a.mean(), "median": a.median(), "max": a.max(),
            "share_2": (a == 2).mean(), "share_3": (a == 3).mean(), "share_ge_10": (a >= 10).mean(),
        })
    return pd.DataFrame(rows).set_index("snapshot")


def arity_by_relation(edges):
    g = edges.groupby("relation_type")["arity"]
    return pd.DataFrame({
        "edges": g.size(), "min": g.min(), "median": g.median(), "max": g.max(),
    }).sort_values("median", ascending=False)


def hub_positions(tkh, edges):
    """Type of members[0] per relation type: shows that every edge is a hub-rooted star."""
    first_type = edges["members"].map(lambda m: tkh.nodes.at[m[0], "type"])
    return pd.crosstab(edges["relation_type"], first_type)


def clique_vs_star_pairs(edges):
    """Distinct node pairs under a clique expansion vs hub-to-member star pairs."""
    clique, star = set(), set()
    for m in edges["members"]:
        u = sorted(set(m))
        clique.update((a, b) for i, a in enumerate(u) for b in u[i + 1:])
        star.update(tuple(sorted((m[0], b))) for b in set(m[1:]))
    return {"clique_pairs": len(clique), "star_pairs": len(star), "incidences": int(edges["arity"].sum())}


def components(s):
    """Connected components of the hypergraph (union-find over members)."""
    parent = {n: n for n in s.node_ids}

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    for m in s.edges["members"]:
        r = find(m[0])
        for v in m[1:]:
            parent[find(v)] = r
    groups = {}
    for n in s.node_ids:
        groups.setdefault(find(n), []).append(n)
    return list(groups.values())


def articles_per_node(tkh, s):
    """Number of distinct articles (provenance or incident edges) a node appears in, within a snapshot."""
    edge_arts = s.edges[["members", "article_id"]].explode("members").groupby("members")["article_id"].agg(set)
    in_snap = s.articles
    return pd.Series({
        n: len((set(tkh.nodes.at[n, "prov_articles"]) | edge_arts.get(n, set())) & in_snap)
        for n in s.node_ids
    })


# ---------------------------------------------------------------- between snapshots

def growth(tkh, snaps):
    rows = []
    for old, new in zip(snaps, snaps[1:]):
        new_nodes = new.node_ids - old.node_ids
        new_edges = new.edges.loc[new.edges.index.difference(old.edges.index)]
        touches_old = new_edges["members"].map(lambda m: any(v in old.node_ids for v in m))
        old_reused = {v for m in new_edges["members"] for v in m} & old.node_ids
        rows.append({
            "transition": f"<={old.cutoff} -> <={new.cutoff}",
            "new_articles": len(new.articles - old.articles),
            "new_nodes": len(new_nodes),
            "node_growth": len(new_nodes) / len(old.node_ids),
            "new_edges": len(new_edges),
            "edge_growth": len(new_edges) / len(old.edges),
            "node_jaccard": len(old.node_ids) / len(new.node_ids),
            "new_edges_touching_old_nodes": touches_old.mean(),
            "old_nodes_mentioned_again": len(old_reused) / len(old.node_ids),
            "removed_nodes": len(old.node_ids - new.node_ids),
        })
    return pd.DataFrame(rows).set_index("transition")


def key_leakage(tkh, cutoffs):
    """Snapshot sizes under the chosen rule vs the year fields the export also offers."""
    n, e = tkh.nodes, tkh.edges
    rows = []
    for c in cutoffs:
        chosen_nodes = set(n.index[n["entry_year"] <= c])
        chosen_edges = set(e.index[e["article_year"] <= c])
        alt = {
            "first_seen_year": set(n.index[n["first_seen_year"] <= c]),
            "node.year": set(n.index[n["year"] <= c]),
        }
        alt_edges = set(e.index[e["year"] <= c])
        rows.append({
            "cutoff": c,
            "nodes (chosen)": len(chosen_nodes),
            "extra nodes via first_seen_year": len(alt["first_seen_year"] - chosen_nodes),
            "extra nodes via node.year": len(alt["node.year"] - chosen_nodes),
            "edges (chosen)": len(chosen_edges),
            "extra edges via edge.year": len(alt_edges - chosen_edges),
        })
    return pd.DataFrame(rows).set_index("cutoff")


# ---------------------------------------------------------------- data quality

def normalise(s):
    s = unicodedata.normalize("NFKC", s).replace("‑", "-").lower()
    return re.sub(r"[^0-9a-z]+", " ", s).strip()


def quality_report(tkh):
    """One row per check: count and up to three example ids. Counts are computed, not curated."""
    n, e, art = tkh.nodes, tkh.edges, tkh.articles
    year_of = art["year"].to_dict()
    rows = []

    def add(check, items, note=""):
        items = list(items)
        rows.append({"check": check, "count": len(items), "examples": ", ".join(map(str, items[:3])), "note": note})

    ids = set(n.index)
    members = e["members"].explode()
    add("dangling member ids", sorted(set(members) - ids))
    add("edges with repeated members", e.index[e["members"].map(lambda m: len(m) != len(set(m)))])
    add("nodes in no hyper-edge", sorted(ids - set(members)))

    prov_min = n["prov_articles"].map(lambda a: min(year_of[x] for x in a))
    add("first_seen_year != earliest provenance year", n.index[n["first_seen_year"] != prov_min],
        "documented as 'earliest corpus paper'; not used for snapshots")
    add("edge.year != article_year", e.index[e["year"] != e["article_year"]],
        "edge.year is the year of the result/claim row")
    add("edge.year > article_year", e.index[e["year"] > e["article_year"]])

    gaps = [(eid, v) for eid, m, a in zip(e.index, e["members"], e["article_id"])
            for v in m if a not in n.at[v, "prov_articles"]]
    add("member missing the edge's article in provenance", [f"{eid}:{v}" for eid, v in gaps],
        f"{len({v for _, v in gaps})} distinct nodes; fixed by the entry-year rule")

    key = n["surface_form"].map(normalise)
    dup = n.assign(key=key).groupby(["type", "key"]).filter(lambda g: len(g) > 1)
    groups = dup.groupby(["type", "key"]).size()
    add("near-duplicate names within a type (groups)", [f"{t}:{k}" for t, k in groups.index],
        f"{int(groups.sum() - len(groups))} redundant ids after NFKC/case/punctuation normalisation")
    cross = n.assign(key=key).groupby("key")["type"].nunique()
    add("same normalised name under >=2 types", cross.index[cross > 1], "mostly cited_work vs method")

    add("surface forms with non-ASCII characters", n.index[n["surface_form"].map(lambda s: not s.isascii())],
        "e.g. U+2011 non-breaking hyphen, U+202F narrow space")
    add("dataset nodes that are bare element symbols",
        n.index[(n["type"] == "dataset") & n["surface_form"].str.fullmatch(r"[A-Z][a-z]?")])
    add("nodes without entity_id", n.index[n["entity_id"].isna()],
        "absent by design on article/cited_work/claim/future_topic/metric")
    add("origin_year before first corpus year", n.index[n["origin_year"] < art["year"].min()],
        "genuine historical dates (e.g. PCA 1901), not noise")

    rels = e.groupby("article_id")["relation_type"].agg(set)
    for r in ["cites", "evaluated_on", "proposes_future_work", "addresses"]:
        add(f"articles without a '{r}' edge", sorted(set(art.index) - set(rels.index[rels.map(lambda x: r in x)])))
    return pd.DataFrame(rows).set_index("check")
