"""A deliberately simple, non-SHAC-T coarsening, used to prove the evaluator is method-independent.

    python scripts/baseline_paper_linkage.py --graph G --out DIR [--config CFG]

Per snapshot: concept nodes are clustered by average linkage on 1 - cosine of their IDF-weighted paper-incidence
vectors (nodes of the same papers merge first), and the one dendrogram is cut at the configured budgets, so the
levels are nested. Every non-concept node joins the super-node holding most concept nodes of its earliest paper.
Labels are placeholders. Ids and events are written with the project's generic writers, so the output has the same
artefact format as any method's.
"""

from pathlib import Path
import argparse
import json
import math
import sys

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import numpy as np  # noqa: E402
from scipy.cluster.hierarchy import fcluster, linkage  # noqa: E402
from scipy.sparse import csr_matrix  # noqa: E402
from sklearn.preprocessing import normalize  # noqa: E402

from tkh.config import add_config_args, config_from_args  # noqa: E402
from tkh.export import assemble_hierarchies, write_outputs  # noqa: E402
from tkh.io import load, make_snapshots  # noqa: E402
from tkh.label import placeholder_labeller  # noqa: E402
from tkh.structure import CONCEPT_TYPES, node_papers  # noqa: E402
from tkh.temporal import match_and_name  # noqa: E402


def cluster_snapshot(tkh, snap, budgets):
    papers = node_papers(tkh, snap)
    items = sorted(v for v in snap.node_ids if tkh.nodes.at[v, "type"] in CONCEPT_TYPES)
    arts = sorted(snap.articles, key=str)
    aidx = {a: j for j, a in enumerate(arts)}
    df = np.array([sum(a in papers[v] for v in items) for a in arts], float)
    rows, cols, vals = [], [], []
    for i, v in enumerate(items):
        for a in papers[v]:
            rows.append(i); cols.append(aidx[a]); vals.append(math.log(len(items) / max(df[aidx[a]], 1)) + 1)
    X = normalize(csr_matrix((vals, (rows, cols)), shape=(len(items), len(arts)))).toarray()
    Z = linkage(X, "average", metric="cosine")
    levels = []
    for k in sorted(range(len(budgets)), key=lambda k: budgets[k]):
        lab = fcluster(Z, budgets[k], criterion="maxclust")
        levels.append((k, {f"c{g}": {items[i] for i in np.nonzero(lab == g)[0]} for g in np.unique(lab)}))
    levels = [lv for _, lv in sorted(levels)]
    # nesting: re-derive coarser levels from the finest by majority parent, so the tree is exactly laminar
    for k in range(len(levels) - 2, -1, -1):
        owner = {v: g for g, m in levels[k].items() for v in m}
        merged = {}
        for g, m in levels[k + 1].items():
            parent = max(sorted({owner[v] for v in m}), key=lambda p: sum(owner[v] == p for v in m))
            merged.setdefault(parent, set()).update(m)
        levels[k] = merged
    year = tkh.articles["year"].to_dict()
    for v in sorted(snap.node_ids - set(items)):
        ps = sorted(papers.get(v, ()), key=lambda a: (year[a], str(a)))
        best = None
        if ps:
            members = [u for u in items if ps[0] in papers[u]]
            if members:
                where = {u: g for g, m in levels[-1].items() for u in m}
                best = max(sorted({where[u] for u in members}), key=lambda g: sum(where[u] == g for u in members))
        best = best or sorted(levels[-1], key=lambda g: -len(levels[-1][g]))[0]
        for k in range(len(levels)):
            g = next(g for g, m in levels[k].items() if levels[-1][best] <= m or best in m) if k == len(levels) - 1 else \
                next(g for g, m in levels[k].items() if levels[-1][best] & m)
            levels[k][g].add(v)
    return levels


def main(argv=None):
    p = add_config_args(argparse.ArgumentParser(description=__doc__.split("\n")[0]))
    p.add_argument("--out", type=Path, required=True)
    p.add_argument("--selection", default=None, help="ignored (accepted for build_cmd compatibility)")
    p.add_argument("--placeholder-labels", action="store_true", help="ignored: labels are always placeholders")
    args, _ = p.parse_known_args(argv)
    cfg = config_from_args(args)
    tkh = load(cfg)
    parts = {s.cutoff: cluster_snapshot(tkh, s, cfg.budgets) for s in make_snapshots(tkh, cfg.cutoffs)}
    ids, events = match_and_name(parts, list(cfg.cutoffs))
    write_outputs(args.out, assemble_hierarchies(parts, ids, placeholder_labeller(tkh), cfg.budgets), events)
    (Path(args.out) / "run_info.json").write_text(json.dumps({"method": "baseline_paper_linkage"}, indent=1) + "\n")
    print(f"baseline_paper_linkage -> {args.out}")


if __name__ == "__main__":
    main()
