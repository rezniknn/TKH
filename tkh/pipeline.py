"""One SHAC run: snapshots -> hierarchy -> persistent ids and events -> labels -> files.

Writes, under the output directory:
    <cutoff>/hierarchy.json          per snapshot (schema/hierarchy.schema.json)
    <cutoff>/coarse_hyperedges.json  T4 collapse of the clustering hypergraph onto every level
    <cutoff>/label_inputs.json       per labelled super-node: the seen and held-out evidence and the prompt hash (T5)
    temporal_events.json             event log (schema/temporal_events.schema.json)
    run_config.toml                  the resolved inputs, cutoffs, budgets and [method]: `validate.py <out> --config <out>/run_config.toml`
    run_info.json                    parameters, per-snapshot and per-level diagnostics, runtime
"""

from dataclasses import replace
from pathlib import Path
import json
import time

from tkh.coarsen import coarse_edges
from tkh.config import to_toml
from tkh.export import assemble_hierarchies, write_outputs
from tkh.hierarchy import build
from tkh.io import load
from tkh.label import LABELLED_LEVELS, make_labeller, settings
from tkh.temporal import match_and_name


def run(cfg, params, out_dir, tkh=None, hubsets=None, info=None):
    """Build and write one run; `tkh` (e.g. a null model) defaults to the config's graph."""
    out_dir = Path(out_dir)
    (out_dir / "metrics.json").unlink(missing_ok=True)   # a coherence result of an earlier build would be stale
    tkh = tkh if tkh is not None else load(cfg)
    t0 = time.perf_counter()
    parts, graphs, diag = build(tkh, cfg.cutoffs, cfg.budgets, params, hubsets)
    ids, events = match_and_name(parts, list(cfg.cutoffs))
    labeller = make_labeller(tkh, cfg)
    if hasattr(labeller, "prefetch"):
        labeller.prefetch(parts)   # all LLM labels of the run in one parallel batch (cache misses only)
    hier = assemble_hierarchies(parts, ids, labeller, cfg.budgets)
    write_outputs(out_dir, hier, events)
    if hasattr(labeller, "inputs"):
        for c, h in hier.items():
            rec = {s["id"]: labeller.inputs[(c, s["level"], frozenset(s["member_ids"]))]
                   for s in h["supernodes"] if s["level"] in LABELLED_LEVELS}
            (out_dir / str(c) / "label_inputs.json").write_text(json.dumps(rec, indent=1, ensure_ascii=False) + "\n")
    for c, (levels, items, B, w, eids, rels) in graphs.items():
        (out_dir / str(c) / "coarse_hyperedges.json").write_text(
            json.dumps(coarse_edges(levels, items, B, w, eids, rels, ids[c]), indent=1) + "\n")
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "run_config.toml").write_text(to_toml(cfg, params.as_dict(), out_dir, settings(cfg) if cfg.labels else None))
    run_info = {"params": params.as_dict(), "cid": params.cid(), "budgets": list(cfg.budgets), "cutoffs": list(cfg.cutoffs),
                **(info or {}), "runtime_s": round(time.perf_counter() - t0, 1),
                "snapshots": {str(c): d for c, d in diag.items()}}
    (out_dir / "run_info.json").write_text(json.dumps(run_info, indent=1) + "\n")
    return hier, events, run_info


def with_graph(cfg, graph):
    return replace(cfg, graph=Path(graph).resolve())
