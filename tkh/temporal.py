"""T3: temporal coupling across snapshots: persistent super-node identity and the birth/growth/merge/split/death event log.

match_and_name assigns persistent ids, by member overlap, to the per-snapshot clusters of the chained build (each
snapshot is built with the localised temporal prior of tkh/hierarchy.py; independent only when gamma = 0), and emits an event log that satisfies validate.py's lineage rules (one
fate per super-node per transition; ids global and never reused).

Per level and transition, every old cluster A points to its successor succ(A), the new
cluster with the largest overlap, and every new cluster B to its predecessor pred(B).
Components of the bipartite graph formed by these pointers are resolved as:
  - one old A whose successors all point back to A: persist (1 new) or split (>= 2 new;
    A's id goes to the child with the largest overlap);
  - anything else: each old A follows succ(A); a new cluster reached by one old cluster
    persists it, one reached by several is a merge (it takes the id of the
    largest-overlap source); new clusters reached by none are births;
  - an old cluster with no overlap at all dies; a new one with no predecessor is born.
Persisting events are continue / growth / change by membership. This is the simplest
consistent matcher: it only does identity bookkeeping and adds no regularisation of its own; stability comes from
the temporal prior in tkh/hierarchy.py.
"""

from collections import defaultdict


def _persist_kind(a, b):
    return "continue" if a == b else "growth" if a < b else "change"


def match_and_name(clusters, cutoffs):
    """clusters: {cutoff: [ {key: set(members)} per level ]}.
    Returns (ids, events): ids[cutoff][level][key] = persistent id."""
    counter = defaultdict(int)

    def fresh(k):
        counter[k] += 1
        return f"L{k}.{counter[k]}"

    ids, events = {}, []
    prev = None
    for c in cutoffs:
        ids[c] = []
        for k, groups in enumerate(clusters[c]):
            if prev is None or k >= len(clusters[prev]):
                ids[c].append({key: fresh(k) for key in sorted(groups)})
                events += [{"event": "birth", "level": k, "from_snapshot": prev, "to_snapshot": c,
                            "from_ids": [], "to_ids": [i]} for i in ids[c][k].values()]
                continue
            old = {ids[prev][k][key]: m for key, m in clusters[prev][k].items()}
            new = groups
            where = {n: a for a, m in old.items() for n in m}
            ov = defaultdict(int)  # (old id, new key) -> overlap
            for b, m in new.items():
                for n in m:
                    if n in where:
                        ov[(where[n], b)] += 1
            succ, pred = {}, {}
            for (a, b), x in sorted(ov.items(), key=lambda t: (-t[1], str(t[0]))):
                succ.setdefault(a, b)
                pred.setdefault(b, a)
            name, evs = {}, []

            # components of the pointer graph
            adj = defaultdict(set)
            for a, b in succ.items():
                adj[("o", a)].add(("n", b)); adj[("n", b)].add(("o", a))
            for b, a in pred.items():
                adj[("o", a)].add(("n", b)); adj[("n", b)].add(("o", a))
            seen = set()
            for start in sorted(adj, key=str):
                if start in seen:
                    continue
                comp, stack = set(), [start]
                while stack:
                    x = stack.pop()
                    if x not in comp:
                        comp.add(x)
                        stack += adj[x] - comp
                seen |= comp
                olds = sorted(x[1] for x in comp if x[0] == "o")
                news = sorted((x[1] for x in comp if x[0] == "n"), key=str)
                if len(olds) == 1 and all(pred.get(b) == olds[0] for b in news) and succ[olds[0]] in news:
                    a = olds[0]
                    if len(news) == 1:
                        name[news[0]] = a
                        evs.append((_persist_kind(old[a], new[news[0]]), [a], [news[0]]))
                    else:
                        heir = max(news, key=lambda b: (ov[(a, b)], str(b)))
                        for b in news:
                            name[b] = a if b == heir else fresh(k)
                        evs.append(("split", [a], news))
                    continue
                into = defaultdict(list)
                for a in olds:
                    into[succ[a]].append(a)
                for b in news:
                    srcs = into.get(b, [])
                    if not srcs:
                        name[b] = fresh(k)
                        evs.append(("birth", [], [b]))
                    elif len(srcs) == 1:
                        name[b] = srcs[0]
                        evs.append((_persist_kind(old[srcs[0]], new[b]), srcs, [b]))
                    else:
                        name[b] = max(srcs, key=lambda a: (ov[(a, b)], a))
                        evs.append(("merge", sorted(srcs), [b]))
            for a in sorted(set(old) - set(succ)):
                evs.append(("death", [a], []))
            for b in sorted(set(new) - set(name), key=str):
                name[b] = fresh(k)
                evs.append(("birth", [], [b]))

            ids[c].append({b: name[b] for b in new})
            for kind, f, t in evs:
                events.append({"event": kind, "level": k, "from_snapshot": prev, "to_snapshot": c,
                               "from_ids": list(f), "to_ids": [name[b] for b in t]})
        prev = c
    return ids, events
