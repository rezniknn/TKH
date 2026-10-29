"""Deterministic mock of the algorithm's output for any TKH input, used to test validate.py at real-data scale.

It is NOT a method. Level 0 groups nodes by type, level 1 by (type, entry period) and
level 2 by (type, entry year), so the hierarchy is laminar by construction and ids are
stable across snapshots. Events are derived by id: birth for new ids, growth/continue for
persisting ones (snapshots are cumulative, so nothing dies).

    python tests/mock_output.py OUT_DIR [--config CFG]
"""

from pathlib import Path
import argparse
import sys

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from tkh.config import add_config_args, config_from_args  # noqa: E402
from tkh.export import write_outputs  # noqa: E402
from tkh.io import load  # noqa: E402


def mock_outputs(tkh, cutoffs, budgets):
    cutoffs = sorted(cutoffs)

    def period(year):
        i = next(i for i, c in enumerate(cutoffs) if year <= c)
        return f"le{cutoffs[0]}" if i == 0 else f"{cutoffs[i - 1] + 1}-{cutoffs[i]}"

    keys = [  # level -> function(type, entry_year) -> key
        lambda t, y: t,
        lambda t, y: f"{t}|{period(y)}",
        lambda t, y: f"{t}|{period(y)}|{y}",
    ][:len(budgets)]

    hierarchies, members_by = {}, {}
    for c in cutoffs:
        nodes = tkh.nodes[tkh.nodes["entry_year"] <= c]
        groups = [{} for _ in keys]
        for nid, t, y in zip(nodes.index, nodes["type"], nodes["entry_year"]):
            for k, key in enumerate(keys):
                groups[k].setdefault(key(t, y), []).append(nid)
        sns = []
        for k, g in enumerate(groups):
            if len(g) > budgets[k]:
                raise ValueError(f"mock exceeds budget at level {k} for <= {c}: {len(g)} > {budgets[k]}")
            for key, members in sorted(g.items()):
                parent = None if k == 0 else f"L{k - 1}:{key.rsplit('|', 1)[0]}"
                sns.append({"id": f"L{k}:{key}", "level": k, "parent_id": parent, "member_ids": sorted(members),
                            "label": f"[mock] {key.replace('|', ', ')}",
                            "gloss": f"[mock] {len(members)} nodes grouped by {('type', 'type and period', 'type and year')[k]}."})
        hierarchies[c] = {"cutoff": c, "levels": len(keys), "budgets": list(budgets), "supernodes": sns}
        members_by[c] = {(s["id"], s["level"]): set(s["member_ids"]) for s in sns}

    events, prev = [], None
    for c in cutoffs:
        for (sid, k), mem in sorted(members_by[c].items()):
            if prev is None or (sid, k) not in members_by[prev]:
                events.append({"event": "birth", "level": k, "from_snapshot": prev, "to_snapshot": c,
                               "from_ids": [], "to_ids": [sid]})
            else:
                kind = "growth" if mem != members_by[prev][(sid, k)] else "continue"
                events.append({"event": kind, "level": k, "from_snapshot": prev, "to_snapshot": c,
                               "from_ids": [sid], "to_ids": [sid]})
        prev = c
    return hierarchies, events


def main(argv=None):
    parser = add_config_args(argparse.ArgumentParser(description="write a mock output for validator tests"))
    parser.add_argument("out_dir", type=Path)
    args = parser.parse_args(argv)
    cfg = config_from_args(args)
    h, e = mock_outputs(load(cfg), cfg.cutoffs, cfg.budgets)
    write_outputs(args.out_dir, h, e)
    print(f"mock output for {len(h)} snapshots, {len(e)} events -> {args.out_dir}")


if __name__ == "__main__":
    main()
