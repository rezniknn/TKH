"""Storage of sweep, null and perturbation partitions under out/runs/ (git-ignored; rebuilt by `make sweep`).

Layout: out/runs/<group>/<name>.json, one file per build, holding concept-node partitions as
label arrays over the sorted node list of each snapshot:
    {"meta": {...}, "parts": {cutoff: {"nodes": [...], "levels": [[label per node] per level]}}}
Groups: config/<cid>, null/<kind>/<seed>, perturb/<cid>/<seed>, perturb_null/<kind>/<null seed>/<seed>.
"""

from pathlib import Path
import json


def save(path, parts, meta=None):
    out = {}
    for c, levels in parts.items():
        nodes = sorted(set().union(*levels[0].values()))
        lab = []
        for lv in levels:
            where = {v: i for i, (_, mem) in enumerate(sorted(lv.items(), key=lambda kv: min(kv[1]))) for v in mem}
            lab.append([where[v] for v in nodes])
        out[str(c)] = {"nodes": nodes, "levels": lab}
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"meta": meta or {}, "parts": out}, separators=(",", ":")))


def load(path):
    """(parts, meta) with parts = {cutoff: [ {label: set(members)} per level ]}."""
    d = json.loads(Path(path).read_text())
    parts = {}
    for c, rec in d["parts"].items():
        levels = []
        for lab in rec["levels"]:
            groups = {}
            for v, g in zip(rec["nodes"], lab):
                groups.setdefault(g, set()).add(v)
            levels.append(groups)
        parts[int(c)] = levels
    return parts, d["meta"]


def run_path(root, *names):
    return Path(root, "runs", *map(str, names[:-1]), f"{names[-1]}.json")
