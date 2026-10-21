"""Writes the deliverable files: out/<snapshot>/hierarchy.json and out/temporal_events.json.

Layout (checked by validate.py against schema/):
    <out_dir>/<cutoff>/hierarchy.json   one per snapshot, e.g. out/2020/hierarchy.json
    <out_dir>/temporal_events.json      event log across consecutive snapshots
"""

from pathlib import Path
import json


def hierarchy_path(out_dir, cutoff):
    return Path(out_dir) / str(cutoff) / "hierarchy.json"


def events_path(out_dir):
    return Path(out_dir) / "temporal_events.json"


def write_outputs(out_dir, hierarchies, events):
    """hierarchies: {cutoff: hierarchy dict}; events: list of event dicts."""
    out_dir = Path(out_dir)
    for cutoff, h in hierarchies.items():
        p = hierarchy_path(out_dir, cutoff)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(h, indent=1, ensure_ascii=False) + "\n")
    events_path(out_dir).write_text(json.dumps({"events": events}, indent=1, ensure_ascii=False) + "\n")


def assemble_hierarchies(parts, ids, labeller, budgets):
    """hierarchy dicts from partitions. parts: {cutoff: [ {key: set(members)} per level ]} (level 0 coarsest);
    ids: from tkh.temporal.match_and_name; labeller(cutoff, level, members) -> (label, gloss).
    Parents are found by containment, so a non-laminar input raises."""
    out = {}
    for c, levels in parts.items():
        sns = []
        for k, groups in enumerate(levels):
            owner = {}
            if k > 0:
                owner = {v: ids[c][k - 1][key] for key, mem in levels[k - 1].items() for v in mem}
            for key, mem in sorted(groups.items(), key=lambda kv: ids[c][k][kv[0]]):
                members = sorted(mem)
                parents = {owner[v] for v in members} if k > 0 else {None}
                if len(parents) != 1:
                    raise ValueError(f"not laminar: {ids[c][k][key]} at level {k} of {c} has parents {parents}")
                label, gloss = labeller(c, k, members)
                sns.append({"id": ids[c][k][key], "level": k, "parent_id": parents.pop(), "member_ids": members,
                            "label": label, "gloss": gloss})
        out[c] = {"cutoff": c, "levels": len(levels), "budgets": list(budgets), "supernodes": sns}
    return out
