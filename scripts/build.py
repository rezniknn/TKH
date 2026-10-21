"""Pipeline step 'build': load data -> snapshots -> hierarchy -> temporal coupling -> labels -> write out/.

    python scripts/build.py [--config CFG] [--out DIR] [--param alpha=0.25 ...]

Parameters come from the config's [method] section (tkh/hierarchy.py Params), then from
<out>/selection.json written by scripts/sweep.py (the selected alpha), then from --param. Writes, per snapshot, hierarchy.json and coarse_hyperedges.json
(the T4 collapse of the clustering hypergraph onto each level), plus temporal_events.json
and run_info.json (parameters, hub sets, sizes, runtime).
"""

from pathlib import Path
import argparse
import json
import sys
import time

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import numpy as np  # noqa: E402

from tkh.coarsen import coarse_edge_records, collapse, concept_nodes, hubs, incidence  # noqa: E402
from tkh.config import add_config_args, config_from_args  # noqa: E402
from tkh.export import assemble_hierarchies, write_outputs  # noqa: E402
from tkh.hierarchy import Params, build  # noqa: E402
from tkh.io import load, snapshot  # noqa: E402
from tkh.label import placeholder_labeller  # noqa: E402
from tkh.temporal import match_and_name  # noqa: E402


def parse_overrides(pairs):
    out = {}
    for p in pairs or []:
        k, v = p.split("=", 1)
        try:
            v = json.loads(v)
        except json.JSONDecodeError:
            pass
        out[k] = v
    return out


def coarse_edges(tkh, cutoff, hierarchy, params):
    """T4 collapse of the snapshot's clustering hypergraph onto every level's super-nodes."""
    snap = snapshot(tkh, cutoff)
    items = concept_nodes(tkh, snap)
    B, w, eids, rels = incidence(tkh, snap, items, hubs(tkh, snap, params.hub_frac))
    out = {}
    for k in range(hierarchy["levels"]):
        sns = [s for s in hierarchy["supernodes"] if s["level"] == k]
        where = {v: i for i, s in enumerate(sns) for v in s["member_ids"]}
        coll = collapse(np.array([where[v] for v in items]), B)
        out[k] = {"summary": {c: int((coll["cls"] == c).sum()) for c in ("internal", "partial", "uncollapsed")}
                  | {"multiway": int(coll["multiway"].sum()), "edges": len(eids)},
                  "edges": coarse_edge_records(coll, w, eids, rels, [s["id"] for s in sns])}
    return out


def run(cfg, params, out_dir, labeller=None):
    tkh = load(cfg)
    t0 = time.perf_counter()
    parts, diag = build(tkh, cfg.cutoffs, cfg.budgets, params, return_diag=True)
    ids, events = match_and_name(parts, list(cfg.cutoffs))
    hier = assemble_hierarchies(parts, ids, labeller or placeholder_labeller(tkh), cfg.budgets)
    write_outputs(out_dir, hier, events)
    for c, h in hier.items():
        (Path(out_dir) / str(c) / "coarse_hyperedges.json").write_text(json.dumps(coarse_edges(tkh, c, h, params), indent=1) + "\n")
    info = {"params": params.as_dict(), "cid": params.cid(), "runtime_s": round(time.perf_counter() - t0, 1),
            "snapshots": {str(c): d for c, d in diag.items()}}
    (Path(out_dir) / "run_info.json").write_text(json.dumps(info, indent=1) + "\n")
    return hier, events, info


def main(argv=None):
    p = add_config_args(argparse.ArgumentParser(description=__doc__.split("\n")[0]))
    p.add_argument("--out", type=Path, help="output directory (default: the config's out_dir)")
    p.add_argument("--param", nargs="+", action="extend", default=[],
                   help="override [method] parameters, e.g. alpha=0.25 structure=projection (repeatable)")
    p.add_argument("--selection", type=Path, default=None,
                   help="selection.json from scripts/sweep.py: use its selected parameters (default: <out>/selection.json if present)")
    args = p.parse_args(argv)
    cfg = config_from_args(args)
    out = args.out or cfg.out_dir
    sel_path = args.selection or Path(out) / "selection.json"
    selected = {}
    if sel_path.exists():
        selected = json.loads(sel_path.read_text())["selected_params"]
        print(f"using selected parameters from {sel_path}: {selected}")
    params = Params.from_config({**cfg.method, **selected, **parse_overrides(args.param)})
    _, events, info = run(cfg, params, out)
    print(f"{params.cid()}: {len(events)} events, {info['runtime_s']}s -> {out}")


if __name__ == "__main__":
    main()
