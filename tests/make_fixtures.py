"""Builds the validator test fixtures (6a.2): a small synthetic TKH, one valid output, and one broken mutation per rule.

    python tests/make_fixtures.py          # (re)writes tests/fixtures/

tests/fixtures/_input/       synthetic graph.json + config.toml (cutoffs 2020/2022/2024, budgets [3, 5])
tests/fixtures/valid/        hand-made output that satisfies every rule; it sits on the edges on
                             purpose (a level exactly at its budget; birth, growth, continue, split,
                             merge and death events) so that "valid passes" is not a trivial test
tests/fixtures/<mutation>/   the valid output with exactly one defect; validate.py must reject it
                             with exactly the codes listed in MUTATIONS
"""

from copy import deepcopy
from pathlib import Path
import json
import shutil
import sys

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from tkh.export import write_outputs  # noqa: E402

FIXTURES = ROOT / "tests" / "fixtures"
INPUT = FIXTURES / "_input"
CUTOFFS, BUDGETS = (2020, 2022, 2024), (3, 5)

# ---------------------------------------------------------------- synthetic input graph

ARTICLES = {1: 2020, 2: 2022, 3: 2024}
NODES = {  # id: (type, articles)
    "m1": ("method", [1, 2]), "m2": ("method", [1]), "t1": ("task", [1, 3]), "d1": ("dataset", [1]),
    "m3": ("method", [2]), "t2": ("task", [2]), "d2": ("dataset", [2]),
    "m4": ("method", [3]), "t3": ("task", [3]), "d3": ("dataset", [3]),
}
EDGES = [("e1", "uses", ["m1", "m2", "t1", "d1"], 1), ("e2", "extends", ["m3", "m1", "t2", "d2"], 2),
         ("e3", "addresses", ["m4", "t1", "t3", "d3"], 3)]


def graph():
    return {
        "meta": {"note": "synthetic fixture graph for validator tests"},
        "nodes": [{"id": n, "type": t, "surface_form": n, "provenance": {"articles": a}} for n, (t, a) in NODES.items()],
        "hyperedges": [{"id": e, "relation_type": r, "members": m,
                        "provenance": {"article_id": a, "article_year": ARTICLES[a]}} for e, r, m, a in EDGES],
    }


CONFIG = """# Run config for the validator fixtures (relative paths resolve against this directory).
[inputs]
graph = "graph.json"
[snapshots]
cutoffs = [2020, 2022, 2024]
[hierarchy]
budgets = [3, 5]
"""

# ---------------------------------------------------------------- valid output


def sn(sid, level, parent, members, label=None):
    label = label or sid.replace("S_", "").replace("_", " ")
    return {"id": sid, "level": level, "parent_id": parent, "member_ids": members,
            "label": label, "gloss": f"Fixture super-node grouping {', '.join(members)}."}


def valid_output():
    h = {
        2020: [sn("S_models", 0, None, ["m1", "m2"]), sn("S_eval", 0, None, ["t1", "d1"]),
               sn("S_gnn", 1, "S_models", ["m1", "m2"]), sn("S_tasks", 1, "S_eval", ["t1"]),
               sn("S_data", 1, "S_eval", ["d1"])],
        2022: [sn("S_models", 0, None, ["m1", "m2", "m3"]), sn("S_eval", 0, None, ["t1", "d1", "t2", "d2"]),
               sn("S_gnn", 1, "S_models", ["m1", "m3"]), sn("S_kernel", 1, "S_models", ["m2"]),
               sn("S_tasks", 1, "S_eval", ["t1", "t2"]), sn("S_data", 1, "S_eval", ["d1"]),
               sn("S_new", 1, "S_eval", ["d2"])],  # 5 level-1 super-nodes = budget N_1 exactly
        2024: [sn("S_models", 0, None, ["m1", "m2", "m3", "m4"]),
               sn("S_eval", 0, None, ["t1", "d1", "t2", "d2", "t3", "d3"]),
               sn("S_gnn", 1, "S_models", ["m1", "m3", "m4"]), sn("S_kernel", 1, "S_models", ["m2"]),
               sn("S_benchmarks", 1, "S_eval", ["t1", "t2", "t3", "d1", "d2", "d3"])],
    }
    hierarchies = {c: {"cutoff": c, "levels": 2, "budgets": list(BUDGETS), "supernodes": s} for c, s in h.items()}

    def ev(kind, level, src, dst, f, t):
        return {"event": kind, "level": level, "from_snapshot": src, "to_snapshot": dst, "from_ids": f, "to_ids": t}

    events = [ev("birth", 0, None, 2020, [], [x]) for x in ("S_models", "S_eval")]
    events += [ev("birth", 1, None, 2020, [], [x]) for x in ("S_gnn", "S_tasks", "S_data")]
    events += [ev("growth", 0, 2020, 2022, [x], [x]) for x in ("S_models", "S_eval")]
    events += [ev("split", 1, 2020, 2022, ["S_gnn"], ["S_gnn", "S_kernel"]),
               ev("growth", 1, 2020, 2022, ["S_tasks"], ["S_tasks"]),
               ev("continue", 1, 2020, 2022, ["S_data"], ["S_data"]),
               ev("birth", 1, 2020, 2022, [], ["S_new"])]
    events += [ev("growth", 0, 2022, 2024, [x], [x]) for x in ("S_models", "S_eval")]
    events += [ev("growth", 1, 2022, 2024, ["S_gnn"], ["S_gnn"]),
               ev("continue", 1, 2022, 2024, ["S_kernel"], ["S_kernel"]),
               ev("merge", 1, 2022, 2024, ["S_tasks", "S_data"], ["S_benchmarks"]),
               ev("death", 1, 2022, 2024, ["S_new"], [])]
    return hierarchies, events


# ---------------------------------------------------------------- mutations


def node(h, cutoff, sid):
    return next(s for s in h[cutoff]["supernodes"] if s["id"] == sid)


def event(events, kind, src=None, dst=None):
    return next(e for e in events if e["event"] == kind and (src is None or e["from_snapshot"] == src)
                and (dst is None or e["to_snapshot"] == dst))


def m_split_over_budget(h, e):
    gnn = node(h, 2022, "S_gnn")
    gnn["member_ids"] = ["m1"]
    h[2022]["supernodes"].append(sn("S_extra", 1, "S_models", ["m3"]))


def m_level_out_of_range(h, e):
    h[2020]["supernodes"].append(sn("S_deep", 2, "S_gnn", ["m1"]))


def m_empty_level(h, e):
    h[2020]["levels"] = 3
    h[2020]["budgets"] = [3, 5, 9]


# Each mutation: (description, expected violation codes, function(hierarchies, events)).
# File-level mutations (invalid JSON, missing/extra files) are applied after writing; see FILE_MUTATIONS.
MUTATIONS = {
    "node_in_two_clusters": ("P1: m1 is in both S_gnn and S_kernel at level 1 of 2022.", {"NODE_IN_TWO_CLUSTERS"},
                             lambda h, e: node(h, 2022, "S_kernel")["member_ids"].append("m1")),
    "node_not_covered": ("P1: t2 is removed from S_tasks, so no level-1 super-node of 2022 contains it.",
                         {"NODE_NOT_COVERED"}, lambda h, e: node(h, 2022, "S_tasks")["member_ids"].remove("t2")),
    "budget_overflow": ("P2: S_gnn is split in 2022, giving 6 level-1 super-nodes against N_1 = 5.",
                        {"BUDGET_EXCEEDED"}, m_split_over_budget),
    "dangling_parent": ("P1: S_kernel's parent id points to a super-node that does not exist.", {"DANGLING_PARENT"},
                        lambda h, e: node(h, 2022, "S_kernel").update(parent_id="S_ghost")),
    "parent_wrong_level": ("P1: S_kernel (level 1) has a level-1 parent.", {"PARENT_WRONG_LEVEL"},
                           lambda h, e: node(h, 2022, "S_kernel").update(parent_id="S_gnn")),
    "root_has_parent": ("P1: level-0 S_eval has a parent.", {"ROOT_HAS_PARENT"},
                        lambda h, e: node(h, 2022, "S_eval").update(parent_id="S_models")),
    "missing_parent": ("P1: level-1 S_tasks has parent_id null.", {"MISSING_PARENT"},
                       lambda h, e: node(h, 2022, "S_tasks").update(parent_id=None)),
    "not_nested": ("P1: S_kernel = {m2} is attached to S_eval, which does not contain m2.", {"NOT_NESTED"},
                   lambda h, e: node(h, 2022, "S_kernel").update(parent_id="S_eval")),
    "future_member": ("Cutoff: m3 (first published 2022) is a member in the 2020 snapshot at both levels.",
                      {"FUTURE_MEMBER"},
                      lambda h, e: [node(h, 2020, s)["member_ids"].append("m3") for s in ("S_models", "S_gnn")]),
    "unknown_member": ("Cutoff: a member id that is not in the input graph at all.", {"UNKNOWN_MEMBER"},
                       lambda h, e: [node(h, 2020, s)["member_ids"].append("ghost") for s in ("S_models", "S_gnn")]),
    "duplicate_id": ("A second level-1 super-node of 2020 reuses the id S_data (with the same member d1).",
                     {"DUPLICATE_ID", "NODE_IN_TWO_CLUSTERS"},
                     lambda h, e: h[2020]["supernodes"].append(deepcopy(node(h, 2020, "S_data")))),
    "missing_label": ("T5: level-0 S_models of 2022 has an empty label.", {"MISSING_LABEL"},
                      lambda h, e: node(h, 2022, "S_models").update(label="  ")),
    "schema_missing_field": ("Schema: a super-node without the required 'gloss' key.", {"SCHEMA"},
                             lambda h, e: node(h, 2022, "S_kernel").pop("gloss")),
    "schema_wrong_type": ("Schema: member_ids is a string instead of a list.", {"SCHEMA"},
                          lambda h, e: node(h, 2022, "S_kernel").update(member_ids="m2")),
    "cutoff_mismatch": ("The 2022 file declares cutoff 2024.", {"CUTOFF_MISMATCH"},
                        lambda h, e: h[2022].update(cutoff=2024)),
    "budgets_mismatch": ("The output declares budgets other than the run config's.", {"BUDGETS_MISMATCH"},
                         lambda h, e: h[2022].update(budgets=[30, 50])),
    "level_out_of_range": ("A level-2 super-node in a file declaring levels = 2.", {"LEVEL_OUT_OF_RANGE"},
                           m_level_out_of_range),
    "empty_level": ("The 2020 file declares 3 levels but has none at level 2 (budgets also extended), so level 2 also covers no node.",
                    {"EMPTY_LEVEL", "NO_BUDGET", "BUDGETS_MISMATCH", "NODE_NOT_COVERED"}, m_empty_level),
    "bad_event_reference": ("Events: a split names a target id that does not exist in 2022.", {"DANGLING_EVENT_REF"},
                            lambda h, e: event(e, "split")["to_ids"].append("S_ghost")),
    "event_unknown_snapshot": ("Events: an event points to snapshot 2030.", {"UNKNOWN_SNAPSHOT"},
                               lambda h, e: event(e, "merge").update(to_snapshot=2030)),
    "event_non_consecutive": ("Events: a growth event spans 2020 -> 2024.", {"BAD_SNAPSHOT_ORDER"},
                              lambda h, e: event(e, "growth", 2020, 2022).update(to_snapshot=2024)),
    "event_null_source": ("Events: a non-first-snapshot event with from_snapshot null.", {"BAD_SNAPSHOT_ORDER"},
                          lambda h, e: event(e, "birth", 2020, 2022).update(from_snapshot=None)),
    "event_wrong_arity": ("Events: a merge with a single source.", {"BAD_EVENT_ARITY"},
                          lambda h, e: event(e, "merge")["from_ids"].remove("S_data")),
    "event_identity_changed": ("Events: the S_models growth event 2020 -> 2022 ends at S_eval instead.",
                               {"IDENTITY_CHANGED"},
                               lambda h, e: next(x for x in e if x["event"] == "growth" and x["from_ids"] == ["S_models"]
                                                 and x["from_snapshot"] == 2020).update(to_ids=["S_eval"])),
    "event_wrong_level": ("Events: the split is recorded at level 0, but its ids are level-1.",
                          {"EVENT_WRONG_LEVEL"}, lambda h, e: event(e, "split").update(level=0)),
    "birth_of_existing": ("Events: S_kernel is 'born' in 2024 although it exists in 2022.", {"BIRTH_OF_EXISTING"},
                          lambda h, e: e.append({"event": "birth", "level": 1, "from_snapshot": 2022,
                                                 "to_snapshot": 2024, "from_ids": [], "to_ids": ["S_kernel"]})),
    "death_of_survivor": ("Events: S_kernel 'dies' in 2024 although it still exists there.", {"DEATH_OF_SURVIVOR"},
                          lambda h, e: e.append({"event": "death", "level": 1, "from_snapshot": 2022,
                                                 "to_snapshot": 2024, "from_ids": ["S_kernel"], "to_ids": []})),
    "event_schema": ("Schema: an unknown event type.", {"SCHEMA"},
                     lambda h, e: event(e, "merge").update(event="explode")),
}

FILE_MUTATIONS = {  # name: (description, expected codes, function(out_dir))
    "invalid_json": ("The 2022 hierarchy.json is truncated mid-file.", {"INVALID_JSON"},
                     lambda d: (d / "2022" / "hierarchy.json").write_text(
                         (d / "2022" / "hierarchy.json").read_text()[:200])),
    "missing_snapshot": ("The 2024 hierarchy.json is missing.", {"MISSING_SNAPSHOT"},
                         lambda d: shutil.rmtree(d / "2024")),
    "unexpected_snapshot": ("An extra 2023 snapshot that the run config does not define.", {"UNEXPECTED_SNAPSHOT"},
                            lambda d: shutil.copytree(d / "2022", d / "2023")),
    "missing_events": ("temporal_events.json is missing.", {"MISSING_EVENTS"},
                       lambda d: (d / "temporal_events.json").unlink()),
}


def write_fixture(path, hierarchies, events, description, expected):
    if path.exists():
        shutil.rmtree(path)
    write_outputs(path, hierarchies, events)
    exp = ", ".join(sorted(expected)) if expected else "none (must pass)"
    (path / "README.md").write_text(f"<!-- Validator fixture, generated by tests/make_fixtures.py. Do not edit by hand. -->\n"
                                    f"{description}\n\nExpected violation codes: {exp}\n")


def build(fixtures=FIXTURES):
    fixtures = Path(fixtures)
    inp = fixtures / "_input"
    inp.mkdir(parents=True, exist_ok=True)
    (inp / "graph.json").write_text(json.dumps(graph(), indent=1) + "\n")
    (inp / "config.toml").write_text(CONFIG)

    h, e = valid_output()
    write_fixture(fixtures / "valid", h, e, "Valid output: satisfies every rule; validate.py must pass it.", set())
    for name, (desc, expected, mutate) in MUTATIONS.items():
        h, e = valid_output()
        mutate(h, e)
        write_fixture(fixtures / name, h, e, desc, expected)
    for name, (desc, expected, mutate) in FILE_MUTATIONS.items():
        h, e = valid_output()
        write_fixture(fixtures / name, h, e, desc, expected)
        mutate(fixtures / name)
    return fixtures


def expected_codes():
    return {n: x for n, (_, x, _) in {**MUTATIONS, **FILE_MUTATIONS}.items()}


if __name__ == "__main__":
    print(f"wrote fixtures to {build()}")
