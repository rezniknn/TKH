"""Coherence of super-nodes against an independent signal: residual bibliographic coupling (E1a) and ground-truth co-membership (E1b).

E1a (primary). The clustering never sees `cites` edges, so citations are an independent
ruler of whether two papers' concepts belong together.
- Ruler: for every citing paper p of the snapshot, C_p = its cited works MINUS those
  whose normalised name matches a concept-node name of p (residual filter: an
  `extends X` paper usually also cites the X paper, which would copy structure into the
  ruler). c_pq = IDF-weighted Salton cosine of C_p and C_q (idf = log(N / df) over the
  snapshot's citing papers).
- Split: the cited works are split into halves A / B by seed, stratified by citing count
  (`make_split`, committed in data/eval_splits.json). Selection uses A only, reporting B.
- Aggregation at paper-pair level, so that no paper with many concepts dominates: with
  n_S(p) = number of p's single-paper concept nodes in super-node S (multi-paper nodes
  would link papers by construction),  w_pq = sum_S n_S(p) n_S(q) / (n_p n_q),  the
  probability that a random concept of p and one of q share a super-node.
- Lift = sum w c / (sum w * mean c): the w-weighted mean coupling over the plain mean
  (1 = no better than chance; a random partition has expected lift 1).
- Strata: pairs that share a non-hub concept node (direct structural overlap; hubs, as in
  tkh.coarsen.hubs with a fixed evaluation threshold, are shared by almost every pair) and
  pairs that do not. The no-overlap stratum is the clean test. Pooled (Mantel-Haenszel-type
  standardised ratio): sum_s O_s / sum_s E_s with O_s = sum_s w c, E_s = sum_s w * mean_s c.
- Interval: delete-one-paper jackknife over citing papers (everything recomputed).

E1b (secondary, descriptive). Ground-truth questions: co-membership of pairs of the same
question's expected methods vs (expected, wrong_domain) pairs, split into same-paper and
cross-paper pairs; exact counts plus a question bootstrap.

All metrics use concept nodes only and the REAL node->paper map, citations and names,
whatever graph the partition was built from (nulls).
"""

from pathlib import Path
import json
import math
import random

import numpy as np

from tkh.coarsen import hubs, node_papers
from tkh.evaluate.groundtruth import key
from tkh.io import snapshot
from tkh.semantic import CONCEPT_TYPES


# ---------------------------------------------------------------- split and ruler

def citations(tkh, cutoff):
    """{citing article: set(cited_work ids)} for the snapshot."""
    e = tkh.edges
    c = e[(e["relation_type"] == "cites") & (e["article_year"] <= cutoff)]
    out = {}
    for m, a in zip(c["members"], c["article_id"]):
        out.setdefault(a, set()).update(m[1:])
    return out


def make_split(tkh, seed=0):
    """{"seed", "A": [...], "B": [...]}: cited works split in halves, stratified by citing count."""
    rng = random.Random(seed)
    df = {}
    for cited in citations(tkh, 10 ** 9).values():
        for w in cited:
            df[w] = df.get(w, 0) + 1
    halves = {"A": [], "B": []}
    by_df = {}
    for w in sorted(df):
        by_df.setdefault(df[w], []).append(w)
    flip = 0
    for d in sorted(by_df):
        ws = by_df[d][:]
        rng.shuffle(ws)
        for w in ws:
            halves["AB"[flip]].append(w)
            flip ^= 1
    return {"seed": seed, "A": sorted(halves["A"]), "B": sorted(halves["B"])}


def load_split(path):
    d = json.loads(Path(path).read_text())
    return {"seed": d["seed"], "A": set(d["A"]), "B": set(d["B"])}


def _names(tkh):
    al = tkh.nodes["aliases"] if "aliases" in tkh.nodes else None
    out = {}
    for v, sf in tkh.nodes["surface_form"].items():
        extra = al.get(v) if al is not None else None
        out[v] = {key(s) for s in [sf, *(extra if isinstance(extra, list) else [])]} - {""}
    return out


class Ruler:
    """Per-snapshot ingredients of E1a that do not depend on the partition."""

    def __init__(self, tkh, cutoff, works=None, hub_frac=0.2):
        snap = snapshot(tkh, cutoff)
        ntype = tkh.nodes["type"]
        papers = node_papers(tkh, snap)
        self.concept = sorted(v for v in snap.node_ids if ntype.at[v] in CONCEPT_TYPES)
        names = _names(tkh)
        paper_keys = {}
        for v in self.concept:
            for a in papers[v]:
                paper_keys.setdefault(a, set()).update(names[v])
        cites = citations(tkh, cutoff)
        self.dropped = {}
        resid = {}
        for a, ws in cites.items():
            keep = {w for w in ws if not (names[w] & paper_keys.get(a, set()))}
            self.dropped[a] = len(ws) - len(keep)
            if works is not None:
                keep &= works
            if keep:
                resid[a] = keep
        self.cites = resid
        self.single = {v: next(iter(papers[v])) for v in self.concept if len(papers[v]) == 1}
        self.overlap_pairs = set()
        hubset = hubs(tkh, snap, hub_frac)
        for v in self.concept:
            if v in hubset:
                continue
            ps = sorted(papers[v])
            for i in range(len(ps)):
                for j in range(i + 1, len(ps)):
                    self.overlap_pairs.add((ps[i], ps[j]))
        self.papers = sorted(a for a in resid if any(p == a for p in self.single.values()))

    def coupling(self, papers):
        """Coupling matrix c over `papers` (IDF from these papers)."""
        df = {}
        for a in papers:
            for w in self.cites[a]:
                df[w] = df.get(w, 0) + 1
        n = len(papers)
        idx = {w: i for i, w in enumerate(sorted(df))}
        X = np.zeros((n, len(idx)))
        for r, a in enumerate(papers):
            for w in self.cites[a]:
                X[r, idx[w]] = math.log(n / df[w])
        norm = np.sqrt((X ** 2).sum(axis=1))
        G = X @ X.T
        den = np.outer(norm, norm)
        return np.divide(G, den, out=np.zeros_like(G), where=den > 0)


def _lift_parts(ruler, level, papers):
    """Per-stratum (O, E, n_pairs) for one partition level over `papers`."""
    where = {v: g for g, mem in level.items() for v in mem}
    keys = sorted({where[v] for v in ruler.single if v in where}, key=str)
    kidx = {k: i for i, k in enumerate(keys)}
    pidx = {a: i for i, a in enumerate(papers)}
    N = np.zeros((len(papers), len(keys)))
    for v, a in ruler.single.items():
        if a in pidx and v in where:
            N[pidx[a], kidx[where[v]]] += 1
    N = N / N.sum(axis=1, keepdims=True)
    W = N @ N.T
    C = ruler.coupling(papers)
    iu = np.triu_indices(len(papers), 1)
    w, c = W[iu], C[iu]
    ov = np.array([(min(papers[i], papers[j]), max(papers[i], papers[j])) in ruler.overlap_pairs
                   for i, j in zip(*iu)], dtype=bool)
    out = {}
    for name, m in (("overlap", ov), ("no_overlap", ~ov), ("all", np.ones_like(ov))):
        if m.sum() == 0:
            out[name] = (0.0, 0.0, 0)
            continue
        out[name] = (float((w[m] * c[m]).sum()), float(w[m].sum() * c[m].mean()), int(m.sum()))
    return out


def _lifts(parts):
    r = {s: (o / e if e > 0 else float("nan")) for s, (o, e, _) in parts.items()}
    O = parts["overlap"][0] + parts["no_overlap"][0]
    E = parts["overlap"][1] + parts["no_overlap"][1]
    r["pooled"] = O / E if E > 0 else float("nan")
    return r


def coupling_lift(ruler, level, jackknife=True):
    """{stratum: {"value", "se", "lo", "hi", "n_pairs"}} for strata overlap / no_overlap / all / pooled."""
    papers = ruler.papers
    full = _lift_parts(ruler, level, papers)
    val = _lifts(full)
    out = {s: {"value": v, "n_pairs": full[s][2] if s in full else full["all"][2], "n_papers": len(papers)}
           for s, v in val.items()}
    if jackknife and len(papers) > 2:
        reps = [_lifts(_lift_parts(ruler, level, papers[:i] + papers[i + 1:])) for i in range(len(papers))]
        n = len(papers)
        for s in val:
            x = np.array([r[s] for r in reps], dtype=float)
            x = x[np.isfinite(x)]
            if len(x) < 2:
                continue
            se = float(math.sqrt((len(x) - 1) / len(x) * ((x - x.mean()) ** 2).sum()))
            out[s].update(se=se, lo=val[s] - 1.96 * se, hi=val[s] + 1.96 * se)
    return out


def coverage(ruler):
    concept_in = sum(1 for v, a in ruler.single.items() if a in set(ruler.papers))
    return {"n_citing_papers": len(ruler.papers), "n_concept": len(ruler.concept),
            "n_single_paper_concept": len(ruler.single), "n_single_paper_concept_scored": concept_in,
            "cited_works_dropped_by_residual_filter": int(sum(ruler.dropped.values()))}


# ---------------------------------------------------------------- E1b

def gt_comembership(tkh, level, targets, cutoff, n_boot=1000, seed=0):
    """Co-membership rates of (expected, expected) vs (expected, wrong_domain) pairs per question."""
    snap = snapshot(tkh, cutoff)
    papers = node_papers(tkh, snap)
    where = {v: g for g, mem in level.items() for v in mem}
    per_q = {}
    for q, t in targets.items():
        exp = sorted({v for ids in t["expected"].values() for v in ids if v in where})
        wrong = sorted({v for ids in t["wrong_domain"].values() for v in ids if v in where} - set(exp))
        rec = {k: [0, 0] for k in ("exp_same_paper", "exp_cross_paper", "exp_wrong")}
        for i in range(len(exp)):
            for j in range(i + 1, len(exp)):
                u, v = exp[i], exp[j]
                k = "exp_same_paper" if papers[u] & papers[v] else "exp_cross_paper"
                rec[k][0] += where[u] == where[v]
                rec[k][1] += 1
        for u in exp:
            for v in wrong:
                rec["exp_wrong"][0] += where[u] == where[v]
                rec["exp_wrong"][1] += 1
        if any(n for _, n in rec.values()):
            per_q[q] = rec
    sizes = np.array([len(m) for m in level.values()], float)
    n = sizes.sum()
    chance = float((sizes * (sizes - 1)).sum() / (n * (n - 1))) if n > 1 else 0.0

    def pooled(qs):
        out = {}
        for k in ("exp_same_paper", "exp_cross_paper", "exp_wrong"):
            hit = sum(per_q[q][k][0] for q in qs)
            tot = sum(per_q[q][k][1] for q in qs)
            out[k] = (hit, tot, hit / tot if tot else float("nan"))
        return out

    qs = sorted(per_q)
    obs = pooled(qs)
    rng = np.random.default_rng(seed)
    boots = [pooled(list(rng.choice(qs, len(qs)))) for _ in range(n_boot)] if qs else []
    res = {"n_questions": len(qs), "chance": chance}
    for k, (hit, tot, rate) in obs.items():
        vals = np.array([b[k][2] for b in boots], float)
        vals = vals[np.isfinite(vals)]
        res[k] = {"hits": hit, "pairs": tot, "rate": rate,
                  "lo": float(np.quantile(vals, 0.025)) if len(vals) else None,
                  "hi": float(np.quantile(vals, 0.975)) if len(vals) else None}
    return res
