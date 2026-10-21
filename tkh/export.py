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
