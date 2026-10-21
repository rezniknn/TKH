"""Standalone output checker (6a.1). Usage: python validate.py out/. Checks schema, P1 laminarity, P2 budgets, snapshot cutoff of member ids, and temporal_events references. Prints one line per violation; exits 0 on pass, non-zero on fail.

    python validate.py OUT_DIR [--config CFG] [--graph G] [--cutoffs ...] [--budgets ...]

The run config (see tkh/config.py) supplies the input graph, the snapshot cutoffs
and the per-level budgets N_k; the output cannot relax them. For every configured
snapshot c, OUT_DIR/<c>/hierarchy.json is checked against schema/hierarchy.schema.json and:
  - P1: every snapshot node sits in exactly one super-node per level; level 0 has no
    parent; every level-(k+1) super-node has exactly one existing parent at level k
    and its members are a subset of the parent's;
  - P2: level k has at most N_k super-nodes;
  - cutoff: every member id exists in that snapshot's node list (ids that enter in a
    later snapshot are reported separately from unknown ids);
  - labels: levels 0 and 1 carry a non-empty label and gloss (T5).
OUT_DIR/temporal_events.json is checked against schema/temporal_events.schema.json and
must refer only to super-node ids that exist, at the stated level, in the snapshots it
names; event arity and snapshot order must be consistent with the event type.

Each violation line is 'CODE location: message'. Exit 0 = pass, 1 = violations, 2 = usage error.
"""

from collections import Counter, defaultdict
from pathlib import Path
import argparse
import json
import sys

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

import jsonschema  # noqa: E402

from tkh.config import add_config_args, config_from_args  # noqa: E402
from tkh.export import events_path, hierarchy_path  # noqa: E402
from tkh.io import load, snapshot  # noqa: E402

SCHEMAS = ROOT / "schema"
LABELLED_LEVELS = (0, 1)
ARITY = {  # event -> (n from_ids, n to_ids); None = "two or more"
    "birth": (0, 1), "death": (1, 0), "continue": (1, 1), "growth": (1, 1), "merge": (None, 1), "split": (1, None),
}
MAX_EXAMPLES = 5


class Report:
    def __init__(self):
        self.lines = []

    def __call__(self, code, where, msg):
        self.lines.append(f"{code} {where}: {msg}")


def examples(items):
    items = sorted(items)
    more = f", ... (+{len(items) - MAX_EXAMPLES})" if len(items) > MAX_EXAMPLES else ""
    return ", ".join(items[:MAX_EXAMPLES]) + more


def read_json(path, schema, rep, where):
    if not path.is_file():
        return None, False
    try:
        doc = json.loads(path.read_text())
    except (json.JSONDecodeError, UnicodeDecodeError) as e:
        rep("INVALID_JSON", where, f"{path.name}: {e}")
        return None, True
    errors = sorted(jsonschema.Draft202012Validator(schema).iter_errors(doc), key=lambda e: list(e.absolute_path))
    for e in errors:
        loc = "/".join(map(str, e.absolute_path)) or "<root>"
        rep("SCHEMA", where, f"{path.name} at {loc}: {e.message}")
    return (None if errors else doc), True


def check_hierarchy(h, cutoff, snap_nodes, entry_year, budgets, rep):
    """Structural checks for one schema-valid hierarchy. Returns {id: level} for event checks."""
    w = str(cutoff)
    if h["cutoff"] != cutoff:
        rep("CUTOFF_MISMATCH", w, f"file declares cutoff {h['cutoff']}")
    if list(h["budgets"]) != list(budgets):
        rep("BUDGETS_MISMATCH", w, f"file declares budgets {h['budgets']}, run config has {list(budgets)}")

    levels, sns = h["levels"], h["supernodes"]
    ids = Counter(s["id"] for s in sns)
    for sid, n in ids.items():
        if n > 1:
            rep("DUPLICATE_ID", w, f"super-node id {sid!r} occurs {n} times")
    by_id = {s["id"]: s for s in sns}
    by_level = defaultdict(list)
    for s in sns:
        by_level[s["level"]].append(s)

    if levels > len(budgets):
        rep("NO_BUDGET", w, f"{levels} levels but budgets only for {len(budgets)}")
    for k in sorted(by_level):
        if k >= levels:
            rep("LEVEL_OUT_OF_RANGE", w, f"{len(by_level[k])} super-nodes at level {k}, file declares levels={levels}")
    for k in range(levels):
        if not by_level.get(k):
            rep("EMPTY_LEVEL", w, f"level {k} has no super-nodes")
        elif k < len(budgets) and len(by_level[k]) > budgets[k]:
            rep("BUDGET_EXCEEDED", w, f"level {k} has {len(by_level[k])} super-nodes, budget N_{k}={budgets[k]}")

    for s in sns:
        sid, k, pid = s["id"], s["level"], s["parent_id"]
        where = f"{w} {sid}"
        if k == 0:
            if pid is not None:
                rep("ROOT_HAS_PARENT", where, f"level-0 super-node has parent {pid!r}")
        elif pid is None:
            rep("MISSING_PARENT", where, f"level-{k} super-node has no parent")
        elif pid not in by_id:
            rep("DANGLING_PARENT", where, f"parent {pid!r} does not exist")
        elif by_id[pid]["level"] != k - 1:
            rep("PARENT_WRONG_LEVEL", where, f"level-{k} super-node has parent {pid!r} at level {by_id[pid]['level']}")
        elif not set(s["member_ids"]) <= set(by_id[pid]["member_ids"]):
            extra = set(s["member_ids"]) - set(by_id[pid]["member_ids"])
            rep("NOT_NESTED", where, f"{len(extra)} members not in parent {pid!r}: {examples(extra)}")
        if k in LABELLED_LEVELS:
            for field in ("label", "gloss"):
                if not (s[field] or "").strip():
                    rep("MISSING_LABEL", where, f"level-{k} super-node has empty {field}")

    for k in range(levels):
        count = Counter(m for s in by_level.get(k, []) for m in s["member_ids"])
        twice = {m for m, n in count.items() if n > 1}
        if twice:
            rep("NODE_IN_TWO_CLUSTERS", f"{w} level {k}", f"{len(twice)} nodes in more than one super-node: {examples(twice)}")
        present = set(count)
        missing = snap_nodes - present
        if missing:
            rep("NODE_NOT_COVERED", f"{w} level {k}", f"{len(missing)} snapshot nodes in no super-node: {examples(missing)}")
        outside = present - snap_nodes
        future = {m for m in outside if m in entry_year}
        unknown = outside - future
        if future:
            later = examples(f"{m} (enters {entry_year[m]})" for m in future)
            rep("FUTURE_MEMBER", f"{w} level {k}", f"{len(future)} members not yet in snapshot <= {cutoff}: {later}")
        if unknown:
            rep("UNKNOWN_MEMBER", f"{w} level {k}", f"{len(unknown)} member ids not in the input graph: {examples(unknown)}")
    return {sid: by_id[sid]["level"] for sid in by_id}


def check_events(events, levels_of, cutoffs, rep):
    """levels_of: {cutoff: {id: level}} for snapshots whose hierarchy passed the schema."""
    prev = {b: a for a, b in zip(cutoffs, cutoffs[1:])}
    for i, e in enumerate(events):
        where = f"events[{i}] {e['event']}"
        src, dst, kind, k = e["from_snapshot"], e["to_snapshot"], e["event"], e["level"]
        if dst not in cutoffs:
            rep("UNKNOWN_SNAPSHOT", where, f"to_snapshot {dst} is not a configured snapshot")
            continue
        if src is None:
            if not (kind == "birth" and dst == cutoffs[0]):
                rep("BAD_SNAPSHOT_ORDER", where, f"from_snapshot is null; only births in the first snapshot ({cutoffs[0]}) may omit it")
        elif src not in cutoffs:
            rep("UNKNOWN_SNAPSHOT", where, f"from_snapshot {src} is not a configured snapshot")
            continue
        elif prev.get(dst) != src:
            rep("BAD_SNAPSHOT_ORDER", where, f"{src} -> {dst} is not a pair of consecutive snapshots")
            continue

        n_from, n_to = ARITY[kind]
        if (n_from is None and len(e["from_ids"]) < 2) or (n_from is not None and len(e["from_ids"]) != n_from) \
                or (n_to is None and len(e["to_ids"]) < 2) or (n_to is not None and len(e["to_ids"]) != n_to):
            rep("BAD_EVENT_ARITY", where, f"{len(e['from_ids'])} -> {len(e['to_ids'])} ids is not a valid {kind}")
        if kind in ("continue", "growth") and e["from_ids"] != e["to_ids"]:
            rep("IDENTITY_CHANGED", where, f"{kind} must keep the super-node id, got {e['from_ids']} -> {e['to_ids']}")

        for side, snap, refs in (("from", src, e["from_ids"]), ("to", dst, e["to_ids"])):
            if snap is None or snap not in levels_of:
                continue  # missing/invalid hierarchy already reported
            for sid in refs:
                if sid not in levels_of[snap]:
                    rep("DANGLING_EVENT_REF", where, f"{side}_id {sid!r} does not exist in snapshot {snap}")
                elif levels_of[snap][sid] != k:
                    rep("EVENT_WRONG_LEVEL", where, f"{side}_id {sid!r} is at level {levels_of[snap][sid]} in {snap}, event says {k}")
        if kind == "birth" and src in levels_of and any(sid in levels_of[src] for sid in e["to_ids"]):
            rep("BIRTH_OF_EXISTING", where, f"{e['to_ids']} already exists in snapshot {src}")
        if kind == "death" and dst in levels_of and any(sid in levels_of[dst] for sid in e["from_ids"]):
            rep("DEATH_OF_SURVIVOR", where, f"{e['from_ids']} still exists in snapshot {dst}")


def validate(out_dir, cfg):
    rep = Report()
    out_dir = Path(out_dir)
    tkh = load(cfg)
    entry_year = tkh.nodes["entry_year"].to_dict()
    h_schema = json.loads((SCHEMAS / "hierarchy.schema.json").read_text())
    e_schema = json.loads((SCHEMAS / "temporal_events.schema.json").read_text())
    cutoffs = list(cfg.cutoffs)

    for d in sorted(p for p in out_dir.iterdir() if p.is_dir() and (p / "hierarchy.json").exists()):
        if not d.name.isdigit() or int(d.name) not in cutoffs:
            rep("UNEXPECTED_SNAPSHOT", d.name, f"hierarchy for a snapshot not in the run config {cutoffs}")

    levels_of = {}
    for c in cutoffs:
        h, exists = read_json(hierarchy_path(out_dir, c), h_schema, rep, str(c))
        if not exists:
            rep("MISSING_SNAPSHOT", str(c), f"{hierarchy_path(out_dir, c)} not found")
        elif h is not None:
            levels_of[c] = check_hierarchy(h, c, snapshot(tkh, c).node_ids, entry_year, cfg.budgets, rep)

    ev, exists = read_json(events_path(out_dir), e_schema, rep, "events")
    if not exists:
        rep("MISSING_EVENTS", "events", f"{events_path(out_dir)} not found")
    elif ev is not None:
        check_events(ev["events"], levels_of, cutoffs, rep)
    return rep.lines


def main(argv=None):
    parser = add_config_args(argparse.ArgumentParser(description=__doc__.split("\n")[0]))
    parser.add_argument("out_dir", type=Path)
    args = parser.parse_args(argv)
    try:
        cfg = config_from_args(args)
    except (FileNotFoundError, ValueError) as e:
        print(f"USAGE {e}", file=sys.stderr)
        return 2
    if not args.out_dir.is_dir():
        print(f"USAGE output directory not found: {args.out_dir}", file=sys.stderr)
        return 2
    lines = validate(args.out_dir, cfg)
    for line in lines:
        print(line)
    if not lines:
        print(f"OK {args.out_dir}: {len(cfg.cutoffs)} snapshots, budgets {list(cfg.budgets)}", file=sys.stderr)
    return 1 if lines else 0


if __name__ == "__main__":
    sys.exit(main())
