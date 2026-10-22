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
OUT_DIR/temporal_events.json is checked against schema/temporal_events.schema.json and:
  - refers only to super-node ids that exist, at the stated level, in the snapshots it names;
  - links consecutive snapshots only, with arity matching the event type;
  - is a complete, consistent lineage (P5 identity tracking): per transition and level,
    every super-node of the earlier snapshot has exactly one outgoing event and every
    super-node of the later one exactly one incoming event; every super-node of the first
    snapshot is born there; continue/growth keep the id, continue keeps the members,
    growth only adds members; split children and merge sources other than the
    persisting id must be new / gone.

Each violation line is 'CODE location: message'. Exit 0 = pass, 1 = violations,
2 = usage or input error, 3 = internal validator error (never reported as a pass or a plain fail).
"""

from collections import Counter, defaultdict
from pathlib import Path
import argparse
import json
import sys
import traceback

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

import jsonschema  # noqa: E402

from tkh.config import add_config_args, config_from_args  # noqa: E402
from tkh.export import events_path, hierarchy_path  # noqa: E402
from tkh.io import load, snapshot  # noqa: E402

SCHEMAS = ROOT / "schema"
LABELLED_LEVELS = (0, 1)
ARITY = {  # event -> (n from_ids, n to_ids); None = "two or more"
    "birth": (0, 1), "death": (1, 0), "continue": (1, 1), "growth": (1, 1), "change": (1, 1),
    "merge": (None, 1), "split": (1, None),
}
PERSIST = ("continue", "growth", "change")  # same id in both snapshots
MAX_EXAMPLES = 5

# JSON Schema counts 2.0 as an integer; Python's range() does not. Make "integer" strict.
_types = jsonschema.Draft202012Validator.TYPE_CHECKER.redefine(
    "integer", lambda _, x: isinstance(x, int) and not isinstance(x, bool))
StrictValidator = jsonschema.validators.extend(jsonschema.Draft202012Validator, type_checker=_types)


class Report:
    def __init__(self):
        self.lines = []

    def __call__(self, code, where, msg):
        self.lines.append(f"{code} {where}: {msg}")


def examples(items):
    items = sorted(map(repr, items))  # repr: ids differing only by whitespace/homoglyphs stay distinguishable
    more = f", ... (+{len(items) - MAX_EXAMPLES})" if len(items) > MAX_EXAMPLES else ""
    return ", ".join(items[:MAX_EXAMPLES]) + more


def read_json(path, schema, rep, where):
    """Returns (schema-valid doc or None, raw doc or None, file exists)."""
    try:
        if not path.is_file():
            return None, None, False
        doc = json.loads(path.read_text(encoding="utf-8"))
    except OSError as e:
        rep("UNREADABLE", where, f"{path.name}: {e.strerror or e}")
        return None, None, True
    except (ValueError, UnicodeDecodeError, RecursionError) as e:  # JSONDecodeError is a ValueError
        rep("INVALID_JSON", where, f"{path.name}: {type(e).__name__}: {str(e)[:200]}")
        return None, None, True
    errors = sorted(StrictValidator(schema).iter_errors(doc), key=lambda e: list(e.absolute_path))
    for e in errors[:50]:
        loc = "/".join(map(str, e.absolute_path)) or "<root>"
        rep("SCHEMA", where, f"{path.name} at {loc}: {e.message[:200]}")
    if len(errors) > 50:
        rep("SCHEMA", where, f"{path.name}: {len(errors) - 50} further schema errors not shown")
    return (None if errors else doc), doc, True


def best_effort_index(raw):
    """{id: level} from a schema-invalid hierarchy, so event references into it are still checked."""
    sns = raw.get("supernodes") if isinstance(raw, dict) else None
    if not isinstance(sns, list):
        return None
    def level(s):
        lv = s.get("level")
        return lv if isinstance(lv, int) and not isinstance(lv, bool) else None  # None: exists, level unknown

    return {s["id"]: level(s) for s in sns if isinstance(s, dict) and isinstance(s.get("id"), str)}


def check_hierarchy(h, cutoff, snap_nodes, entry_year, budgets, rep):
    """Structural checks for one schema-valid hierarchy."""
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

    if levels < 2:
        rep("TOO_FEW_LEVELS", w, f"file declares {levels} super-node level(s); levels 0 and 1 are required (T5)")
    if levels > len(budgets):
        rep("NO_BUDGET", w, f"file declares {levels} levels, the run config has budgets for {len(budgets)}")
    checked = min(levels, len(budgets))  # never loop over an unbounded declared level count
    for k in sorted(by_level):
        if k >= levels:
            rep("LEVEL_OUT_OF_RANGE", w, f"{len(by_level[k])} super-nodes at level {k}, file declares levels={levels}")
    for k in range(checked):
        if not by_level.get(k):
            rep("EMPTY_LEVEL", w, f"level {k} has no super-nodes")
        elif len(by_level[k]) > budgets[k]:
            rep("BUDGET_EXCEEDED", w, f"level {k} has {len(by_level[k])} super-nodes, budget N_{k}={budgets[k]}")

    for s in sns:
        sid, k, pid = s["id"], s["level"], s["parent_id"]
        where = f"{w} {sid!r}"
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

    for k in range(checked):
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


def check_events(events, index, members, cutoffs, rep):
    """index: {cutoff: {id: level}} (best effort, also for schema-invalid files);
    members: {cutoff: {id: set(member_ids)}} for schema-valid files only."""
    prev = {b: a for a, b in zip(cutoffs, cutoffs[1:])}
    outgoing, incoming = defaultdict(Counter), defaultdict(Counter)  # (src, dst, level) -> Counter(id)

    for i, e in enumerate(events):
        where = f"events[{i}] {e['event']}"
        src, dst, kind, k = e["from_snapshot"], e["to_snapshot"], e["event"], e["level"]
        if dst not in cutoffs:
            rep("UNKNOWN_SNAPSHOT", where, f"to_snapshot {dst} is not a configured snapshot")
            continue
        if src is None:
            if not (kind == "birth" and dst == cutoffs[0]):
                rep("BAD_SNAPSHOT_ORDER", where, f"from_snapshot is null; only births in the first snapshot ({cutoffs[0]}) may omit it")
                continue
        elif src not in cutoffs:
            rep("UNKNOWN_SNAPSHOT", where, f"from_snapshot {src} is not a configured snapshot")
            continue
        elif prev.get(dst) != src:
            rep("BAD_SNAPSHOT_ORDER", where, f"{src} -> {dst} is not a pair of consecutive snapshots")
            continue

        f_ids, t_ids = e["from_ids"], e["to_ids"]
        n_from, n_to = ARITY[kind]
        if (n_from is None and len(f_ids) < 2) or (n_from is not None and len(f_ids) != n_from) \
                or (n_to is None and len(t_ids) < 2) or (n_to is not None and len(t_ids) != n_to):
            rep("BAD_EVENT_ARITY", where, f"{len(f_ids)} -> {len(t_ids)} ids is not a valid {kind}")
        if kind in PERSIST and f_ids != t_ids:
            rep("IDENTITY_CHANGED", where, f"{kind} must keep the super-node id, got {f_ids} -> {t_ids}")
        outgoing[(src, dst, k)].update(f_ids)
        incoming[(src, dst, k)].update(t_ids)

        for side, snap, refs in (("from", src, f_ids), ("to", dst, t_ids)):
            if snap is None or snap not in index:
                continue  # missing/unparseable hierarchy already reported
            for sid in refs:
                if sid not in index[snap]:
                    rep("DANGLING_EVENT_REF", where, f"{side}_id {sid!r} does not exist in snapshot {snap}")
                elif index[snap][sid] is not None and index[snap][sid] != k:
                    rep("EVENT_WRONG_LEVEL", where, f"{side}_id {sid!r} is at level {index[snap][sid]} in {snap}, event says {k}")

        old, new = index.get(src, {}), index.get(dst, {})
        if kind == "birth" and src in index and any(x in old for x in t_ids):
            rep("BIRTH_OF_EXISTING", where, f"{t_ids} already exists in snapshot {src}")
        if kind == "death" and dst in index and any(x in new for x in f_ids):
            rep("DEATH_OF_SURVIVOR", where, f"{f_ids} still exists in snapshot {dst}")
        if kind == "split" and src in index:
            existing = [x for x in t_ids if x in old and x not in f_ids]
            if existing:
                rep("SPLIT_INTO_EXISTING", where, f"split children {existing} already exist in snapshot {src}")
        if kind == "split" and dst in index and any(x in new and x not in t_ids for x in f_ids):
            rep("SPLIT_SOURCE_SURVIVES", where, f"split source {f_ids} still exists in {dst} but is not one of its children")
        if kind == "merge" and dst in index:
            surviving = [x for x in f_ids if x in new and x not in t_ids]
            if surviving:
                rep("MERGE_SOURCE_SURVIVES", where, f"merge sources {surviving} still exist in snapshot {dst}")
        if kind == "merge" and src in index and any(x in old and x not in f_ids for x in t_ids):
            rep("MERGE_INTO_EXISTING", where, f"merge target {t_ids} already exists in {src} but is not one of the sources")
        if kind in ("split", "merge") and src in members and dst in members:
            pairs = [(f_ids[0], c) for c in t_ids] if kind == "split" else [(x, t_ids[0]) for x in f_ids]
            for a_id, b_id in pairs:
                a, b = members[src].get(a_id), members[dst].get(b_id)
                if a is not None and b is not None and not a & b:
                    rep("EVENT_MEMBERSHIP_MISMATCH", where, f"{a_id!r} ({src}) and {b_id!r} ({dst}) share no members")
        if kind in PERSIST and src in members and dst in members and f_ids == t_ids:
            sid = f_ids[0]
            a, b = members[src].get(sid), members[dst].get(sid)
            if a is not None and b is not None:
                if kind == "continue" and a != b:
                    rep("EVENT_MEMBERSHIP_MISMATCH", where, f"{sid!r} changes members ({len(a)} -> {len(b)}); not a continue")
                if kind == "growth" and not (a < b):
                    rep("EVENT_MEMBERSHIP_MISMATCH", where, f"{sid!r} members are not a strict superset ({len(a)} -> {len(b)}); not a growth")
                if kind == "change" and (a == b or a < b):
                    rep("EVENT_MEMBERSHIP_MISMATCH", where, f"{sid!r} membership is {'unchanged' if a == b else 'pure growth'}; use continue/growth")
                if kind == "change" and not a & b:
                    rep("EVENT_MEMBERSHIP_MISMATCH", where, f"{sid!r} keeps no member ({len(a)} -> {len(b)}); this is a different super-node")

    # Completeness and consistency of the lineage, per transition and level.
    transitions = [(None, cutoffs[0])] + list(zip(cutoffs, cutoffs[1:]))
    for src, dst in transitions:
        if dst not in index or (src is not None and src not in index):
            continue
        levels = (set(index[dst].values()) | (set(index[src].values()) if src is not None else set())) - {None}
        for k in sorted(levels):
            label = f"{src} -> {dst} level {k}" if src is not None else f"first snapshot {dst} level {k}"
            out, inc = outgoing[(src, dst, k)], incoming[(src, dst, k)]
            if src is not None:
                ids_src = {x for x, lv in index[src].items() if lv == k}
                if lost := ids_src - set(out):
                    rep("UNTRACKED_SUPERNODE", label, f"{len(lost)} super-nodes of {src} have no outgoing event: {examples(lost)}")
                if multi := {x for x, n in out.items() if n > 1}:
                    rep("LINEAGE_CONFLICT", label, f"super-nodes with more than one outgoing event: {examples(multi)}")
            ids_dst = {x for x, lv in index[dst].items() if lv == k}
            if orphan := ids_dst - set(inc):
                rep("UNTRACKED_SUPERNODE", label, f"{len(orphan)} super-nodes of {dst} have no incoming event: {examples(orphan)}")
            if multi := {x for x, n in inc.items() if n > 1}:
                rep("LINEAGE_CONFLICT", label, f"super-nodes with more than one incoming event: {examples(multi)}")


def check_id_namespace(index, cutoffs, rep):
    """Super-node ids are global: constant level, contiguous run of snapshots."""
    seen = defaultdict(dict)  # id -> {cutoff: level}
    for c in cutoffs:
        for sid, lv in index.get(c, {}).items():
            seen[sid][c] = lv
    known = [c for c in cutoffs if c in index]
    for sid, at in sorted(seen.items()):
        levels = {lv for lv in at.values() if lv is not None}
        if len(levels) > 1:
            rep("ID_LEVEL_CHANGED", repr(sid), f"appears at levels {sorted(levels)} across snapshots {sorted(at)}")
        pos = [known.index(c) for c in at]
        if max(pos) - min(pos) + 1 != len(pos):
            gap = [c for c in known[min(pos):max(pos) + 1] if c not in at]
            rep("ID_REUSED", repr(sid), f"exists in {sorted(at)} but not in {gap}; a gone id must not come back")


def check_label_inputs(out_dir, cutoffs, members, ntype, seed, rep):
    """If a run ships <cutoff>/label_inputs.json, every super-node's labeller input ('shown') must lie inside the
    evaluator's seen half (tkh.evalkit.split), and its recorded held-out half must equal the evaluator's."""
    from tkh.evalkit.split import split_members
    from tkh.structure import CONCEPT_TYPES
    for c in cutoffs:
        p = Path(out_dir) / str(c) / "label_inputs.json"
        if not p.is_file() or c not in members:
            continue
        try:
            li = json.loads(p.read_text(encoding="utf-8"))
        except (OSError, ValueError) as e:
            rep("UNREADABLE", f"{c}/label_inputs.json", str(e))
            continue
        for sid, rec in li.items():
            if sid not in members[c]:
                rep("LABEL_INPUT_UNKNOWN_SUPERNODE", f"{c}/{sid}", "label input for a super-node not in the hierarchy")
                continue
            seen, held = split_members([v for v in members[c][sid] if ntype.get(v) in CONCEPT_TYPES], seed)
            leak = set(rec.get("shown", [])) - set(seen)
            if leak:
                rep("LABEL_INPUT_LEAK", f"{c}/{sid}", f"labeller saw {len(leak)} member(s) outside the evaluator's seen half, e.g. {examples(sorted(leak))}")
            if "held_out" in rec and sorted(rec["held_out"]) != held:
                rep("LABEL_INPUT_SPLIT_MISMATCH", f"{c}/{sid}", "recorded held-out half differs from the evaluator's split")


def validate(out_dir, cfg, tkh=None):
    rep = Report()
    out_dir = Path(out_dir)
    tkh = tkh if tkh is not None else load(cfg)
    entry_year = tkh.nodes["entry_year"].to_dict()
    h_schema = json.loads((SCHEMAS / "hierarchy.schema.json").read_text(encoding="utf-8"))
    e_schema = json.loads((SCHEMAS / "temporal_events.schema.json").read_text(encoding="utf-8"))
    cutoffs = sorted(cfg.cutoffs)
    names = {str(c) for c in cutoffs}

    for d in sorted(out_dir.iterdir()):
        try:
            has_h = d.is_dir() and (d / "hierarchy.json").exists()
        except OSError as e:
            rep("UNREADABLE", repr(d.name), f"cannot inspect directory: {e.strerror or e}")
            continue
        if has_h and d.name not in names:  # exact string match: '02020' or non-ASCII digits are not '2020'
            rep("UNEXPECTED_SNAPSHOT", repr(d.name), f"hierarchy for a snapshot not in the run config {cutoffs}")

    index, members = {}, {}
    for c in cutoffs:
        h, raw, exists = read_json(hierarchy_path(out_dir, c), h_schema, rep, str(c))
        if not exists:
            rep("MISSING_SNAPSHOT", str(c), f"{hierarchy_path(out_dir, c)} not found (or not a regular file)")
        elif h is not None:
            check_hierarchy(h, c, snapshot(tkh, c).node_ids, entry_year, cfg.budgets, rep)
            index[c] = {s["id"]: s["level"] for s in h["supernodes"]}
            members[c] = {s["id"]: set(s["member_ids"]) for s in h["supernodes"]}
        elif (idx := best_effort_index(raw)) is not None:
            index[c] = idx

    check_id_namespace(index, cutoffs, rep)
    check_label_inputs(out_dir, cutoffs, members, tkh.nodes["type"].to_dict(), int(cfg.labels.get("seed", 0)), rep)
    ev, _, exists = read_json(events_path(out_dir), e_schema, rep, "events")
    if not exists:
        rep("MISSING_EVENTS", "events", f"{events_path(out_dir)} not found")
    elif ev is not None:
        check_events(ev["events"], index, members, cutoffs, rep)
    return rep.lines


def main(argv=None):
    parser = add_config_args(argparse.ArgumentParser(description=__doc__.split("\n")[0]))
    parser.add_argument("out_dir", type=Path)
    args = parser.parse_args(argv)
    try:
        cfg = config_from_args(args)
    except (FileNotFoundError, ValueError) as e:
        print(f"USAGE config: {e}", file=sys.stderr)
        return 2
    if not args.out_dir.is_dir():
        print(f"USAGE output directory not found: {args.out_dir}", file=sys.stderr)
        return 2
    try:
        tkh = load(cfg)
    except (OSError, ValueError, KeyError, TypeError) as e:
        print(f"USAGE input graph {cfg.graph}: {type(e).__name__}: {e}", file=sys.stderr)
        return 2
    try:
        lines = validate(args.out_dir, cfg, tkh)
    except Exception as e:  # noqa: BLE001 - a crash must never look like a pass or an ordinary fail
        print(f"INTERNAL {type(e).__name__}: {e}", file=sys.stderr)
        traceback.print_exc()
        return 3
    for line in lines:
        print(line)
    if not lines:
        print(f"OK {args.out_dir}: {len(cfg.cutoffs)} snapshots, budgets {list(cfg.budgets)}", file=sys.stderr)
    return 1 if lines else 0


if __name__ == "__main__":
    sys.exit(main())
