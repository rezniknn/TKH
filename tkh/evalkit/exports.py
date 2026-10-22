"""Graph exports for method re-runs: perturbed exports (M2) and configuration-model null exports (M5).

Both are written in the export's own JSON format, so ANY method that reads the export can be re-run on them through
the [eval] build_cmd hook, and every method sees exactly the same files (common random numbers).

perturb(raw, frac, seed, cutoffs)
    Remove round(frac * n) hyper-edges of EVERY relation in every publication period (the brief's "remove 10% of
    hyper-edges"), so each cumulative snapshot loses about frac of its edges.
configuration_null(raw, seed, cutoffs)
    The hypergraph configuration model (degree- and hyperedge-size-preserving random hypergraph; Chodrow, J.
    Complex Networks 2020; the null behind hypergraph modularity), in its type- and period-preserving form: Curveball
    trades (Strona et al. 2014) between two edges of the same relation and publication period, within one member
    type. Preserved: every node's number of edges per (relation, period), every edge's arity and member-type
    composition, members[0] of every edge, and the `presents` edges (they define each paper's hub). Destroyed:
    which nodes occur together. Defined on the data, not on any method's input.
"""

from collections import Counter
import copy
import hashlib
import json
import random
from pathlib import Path


def load_raw(path):
    return json.loads(Path(path).read_text())


def write(raw, path):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(raw, ensure_ascii=False))
    return path


def file_hash(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()[:16]


def period(year, cutoffs):
    for i, c in enumerate(sorted(cutoffs)):
        if year <= c:
            return i
    return len(cutoffs)


def perturb(raw, frac, seed, cutoffs):
    rng = random.Random(seed)
    edges = raw["hyperedges"]
    strata = {}
    for i, e in enumerate(edges):
        strata.setdefault(period(e["provenance"]["article_year"], cutoffs), []).append(i)
    drop = {i for idx in strata.values() for i in rng.sample(idx, round(frac * len(idx)))}
    out = dict(raw)
    out["hyperedges"] = [e for i, e in enumerate(edges) if i not in drop]
    return out, sorted(edges[i]["id"] for i in drop)


def configuration_null(raw, seed, cutoffs, sweeps=10, fixed_relations=("presents",)):
    rng = random.Random(seed)
    ntype = {n["id"]: n["type"] for n in raw["nodes"]}
    edges = copy.deepcopy(raw["hyperedges"])
    strata = {}
    for i, e in enumerate(edges):
        if e["relation_type"] in fixed_relations:
            continue
        strata.setdefault((e["relation_type"], period(e["provenance"]["article_year"], cutoffs)), []).append(i)
    trades = 0
    for ids in strata.values():
        if len(ids) < 2:
            continue
        n_slots = sum(len(edges[i]["members"]) - 1 for i in ids)
        for _ in range(sweeps * n_slots):
            i, j = rng.sample(ids, 2)
            mi, mj = edges[i]["members"], edges[j]["members"]
            types = sorted({ntype[v] for v in mi[1:]})
            if not types:
                continue
            t = rng.choice(types)
            si, sj = set(mi), set(mj)
            pi = [p for p in range(1, len(mi)) if ntype[mi[p]] == t and mi[p] not in sj]
            pj = [p for p in range(1, len(mj)) if ntype[mj[p]] == t and mj[p] not in si]
            if not pi or not pj:
                continue
            pool = sorted({mi[p] for p in pi} | {mj[p] for p in pj})
            rng.shuffle(pool)
            for k, p in enumerate(pi):
                mi[p] = pool[k]
            for k, p in enumerate(pj):
                mj[p] = pool[len(pi) + k]
            trades += 1
    out = dict(raw)
    out["hyperedges"] = edges
    check_null(raw, out, cutoffs, fixed_relations)
    kept = sum(len(set(a["members"][1:]) & set(b["members"][1:])) for a, b in zip(raw["hyperedges"], edges))
    total = sum(len(a["members"]) - 1 for a in raw["hyperedges"])
    return out, {"seed": seed, "trades": trades, "retained_incidence": kept / total}


def _degrees(edges, cutoffs):
    return Counter((v, e["relation_type"], period(e["provenance"]["article_year"], cutoffs))
                   for e in edges for v in e["members"])


def check_null(raw, null, cutoffs, fixed_relations=("presents",)):
    ntype = {n["id"]: n["type"] for n in raw["nodes"]}
    for a, b in zip(raw["hyperedges"], null["hyperedges"]):
        ma, mb = a["members"], b["members"]
        if a["id"] != b["id"] or len(ma) != len(mb) or len(set(mb)) != len(mb) or ma[0] != mb[0]:
            raise AssertionError(f"edge {a['id']}: id, arity, duplicate or members[0] invariant broken")
        if Counter(ntype[v] for v in ma) != Counter(ntype[v] for v in mb):
            raise AssertionError(f"edge {a['id']}: member-type composition changed")
        if a["relation_type"] in fixed_relations and ma != mb:
            raise AssertionError(f"edge {a['id']}: a fixed relation changed")
    if _degrees(raw["hyperedges"], cutoffs) != _degrees(null["hyperedges"], cutoffs):
        raise AssertionError("per (relation, period) degrees changed")
