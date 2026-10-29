"""Semantic coherence of the coarsest level (L0) on paper abstracts, rated pairwise by an open-source LLM.

    python -m eval.extra.abstract_coherence [--run out] [--check]

For the latest snapshot of the run, every paper is attributed to the L0 super-node that holds its article node (an
article is anchored to the method it presents, tkh/hierarchy.anchors). Every pair of papers with an abstract is rated
by phi4 for topical closeness on 0-10 (pair_prompt.txt: titles and abstracts only, in id order, no super-node
information). The question is whether pairs in the same L0 super-node are rated closer than pairs in different ones.

  abstracts   eval/extra/abstracts/<article id>.txt and manifest.json; downloaded once with tkh/abstracts.retrieve
              (arXiv v1, OpenAlex; title-verified) when an article of the snapshot has no manifest entry
  rater       tkh.llm.CachedLLM("phi4") with its own cache eval/extra/llm_cache.json: offline when the cache exists,
              live otherwise (TKH_LLM_MODE overrides); temperature 0
  statistics  mean score within and across super-nodes and their difference; a paper-cluster bootstrap CI of the
              difference (papers resampled, pairs weighted by multiplicity); a permutation null that shuffles the
              paper -> super-node assignment with the group sizes fixed (one-sided p); per-super-node means
-> eval/extra/results.json, eval/extra/abstract_coherence.png, and the generated blocks of eval/extra/REPORT.md
(--check exits 1 if they are stale).
"""

from pathlib import Path
import argparse
import json
import re
import sys

import numpy as np

from tkh.config import REPO_ROOT, load_config
from tkh.io import load, snapshot
from tkh.llm import CachedLLM, render

HERE = Path(__file__).resolve().parent
ABS = HERE / "abstracts"
CACHE = HERE / "llm_cache.json"
PROMPT = HERE / "pair_prompt.txt"
RESULTS = HERE / "results.json"
REPORT = HERE / "REPORT.md"
FIGURE = HERE / "abstract_coherence.png"
MODEL, B, R, SEED = "phi4", 2000, 9999, 0
BLOCK = re.compile(r"(<!-- table:(\w+) -->\n)(.*?)(<!-- /table:\2 -->)", re.S)


# ---------------------------------------------------------------- inputs

def papers_of_l0(tkh, run, cutoff):
    """{article id: L0 super-node id} for the snapshot's articles, from the article nodes in L0 member_ids."""
    h = json.loads((Path(run) / str(cutoff) / "hierarchy.json").read_text())
    l0 = {v: s["id"] for s in h["supernodes"] if s["level"] == 0 for v in s["member_ids"]}
    node = {a: nid for a, nid in tkh.articles["node_id"].items() if isinstance(nid, str)}
    snap = snapshot(tkh, cutoff)
    return {a: l0[node[a]] for a in sorted(snap.articles, key=str) if a in node and node[a] in l0}


def abstracts(tkh, ids):
    """{article id: abstract} from eval/extra/abstracts/, downloading once if an article has no manifest entry."""
    man_path = ABS / "manifest.json"
    man = json.loads(man_path.read_text()) if man_path.exists() else {}
    if any(str(a) not in man for a in ids):
        from tkh.abstracts import retrieve   # network: arXiv and OpenAlex
        df = retrieve(tkh)
        ABS.mkdir(parents=True, exist_ok=True)
        for a, r in df.iterrows():
            ok = r["status"] in ("abstract", "retitled")
            if ok:
                (ABS / f"{a}.txt").write_text(r["abstract"].strip() + "\n")
            clean = lambda x: None if x is None or (isinstance(x, float) and x != x) else x   # noqa: E731  NaN -> None
            man[str(a)] = {"title": r["title"], "status": r["status"], "source": clean(r["source"]),
                           "title_similarity": clean(r["title_similarity"]), "returned_title": clean(r["returned_title"]),
                           "file": f"{a}.txt" if ok else None}
        man_path.write_text(json.dumps(man, indent=1, ensure_ascii=False, allow_nan=False) + "\n")
    return {a: (ABS / man[str(a)]["file"]).read_text().strip() for a in ids if man[str(a)]["file"]}, man


# ---------------------------------------------------------------- rating

def rate(tkh, ids, text, endpoint):
    """{(a, b): score or None} for every pair a < b (id order) of papers with an abstract."""
    llm = CachedLLM(MODEL, CACHE, endpoint, "offline" if CACHE.exists() else "live")
    title = tkh.articles["title"].to_dict()
    pairs = [(a, b) for i, a in enumerate(ids) for b in ids[i + 1:]]
    prompts = [render(PROMPT, title_a=title[a], abstract_a=text[a], title_b=title[b], abstract_b=text[b]) for a, b in pairs]
    resp = llm.complete_many(prompts, workers=4)
    out = {}
    for p, r in zip(pairs, resp):
        s = r.get("score") if isinstance(r, dict) else None
        out[p] = int(s) if isinstance(s, (int, float)) and float(s).is_integer() and 0 <= s <= 10 else None
    return out, llm


# ---------------------------------------------------------------- statistics

def _means(M, same, wts=None):
    """(mean within, mean across) over the off-diagonal pairs of M, weighted by wts (n x n) if given."""
    off = ~np.eye(len(M), dtype=bool) & ~np.isnan(M)
    W = np.ones_like(M) if wts is None else wts
    w_in, w_out = W * (off & same), W * (off & ~same)
    Mz = np.nan_to_num(M)
    return (w_in * Mz).sum() / w_in.sum(), (w_out * Mz).sum() / w_out.sum()


def analyse(ids, group, scores):
    n = len(ids)
    idx = {a: i for i, a in enumerate(ids)}
    M = np.full((n, n), np.nan)
    for (a, b), s in scores.items():
        if s is not None:
            M[idx[a], idx[b]] = M[idx[b], idx[a]] = s
    g = np.array([group[a] for a in ids])
    same = g[:, None] == g[None, :]
    mi, mo = _means(M, same)
    rng = np.random.default_rng(SEED)
    null = np.array([np.subtract(*_means(M, (lambda p: p[:, None] == p[None, :])(rng.permutation(g)), None))
                     for _ in range(R)])
    boot = []
    for _ in range(B):
        c = np.bincount(rng.integers(0, n, n), minlength=n).astype(float)
        boot.append(np.subtract(*_means(M, same, np.outer(c, c))))
    tri = np.triu(~np.isnan(M), 1)
    per = []
    for sid in sorted(set(g), key=lambda s: (-int((g == s).sum()), s)):
        m = g == sid
        inner = M[np.ix_(m, m)][np.triu(np.ones((m.sum(), m.sum()), bool), 1)]
        per.append({"super_node": sid, "papers": int(m.sum()), "pairs_within": int(len(inner)),
                    "mean_within": float(np.nanmean(inner)) if len(inner) else None,
                    "mean_to_other_papers": float(np.nanmean(M[np.ix_(m, ~m)]))})
    hist = {k: [int(((M == s) & tri & (same if k == "within" else ~same)).sum()) for s in range(11)]
            for k in ("within", "across")}
    loo = []   # the difference with one super-node's papers removed entirely (its within- and cross-pairs)
    for p in per:
        if p["pairs_within"]:
            keep = g != p["super_node"]
            Mk, sk = M[np.ix_(keep, keep)], same[np.ix_(keep, keep)]
            loo.append({"dropped": p["super_node"], "difference": float(np.subtract(*_means(Mk, sk)))})
    return {"mean_within": float(mi), "mean_across": float(mo), "difference": float(mi - mo),
            "difference_ci95": [float(np.percentile(boot, 2.5)), float(np.percentile(boot, 97.5))],
            "permutation": {"R": R, "null_mean": float(null.mean()), "null_q97.5": float(np.percentile(null, 97.5)),
                            "p": float((1 + (null >= mi - mo).sum()) / (R + 1))},
            "pairs_within": int((tri & same).sum()), "pairs_across": int((tri & ~same).sum()),
            "histogram": hist, "per_super_node": per, "leave_one_super_node_out": loo}


# ---------------------------------------------------------------- outputs

def figure(res):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    s = res["summary"]
    fig, ax = plt.subplots(1, 2, figsize=(10, 3.2), width_ratios=[1, 1.3])
    for k, col in (("within", "#0072B2"), ("across", "#E69F00")):
        h = np.array(s["histogram"][k], float)
        ax[0].bar(np.arange(11) + (-0.2 if k == "within" else 0.2), h / h.sum(), width=0.4, color=col,
                  label=f"{k} super-nodes (mean {s['mean_' + k]:.2f})")
    ax[0].set_xticks(range(11)); ax[0].set_xlabel("LLM closeness score"); ax[0].set_ylabel("share of pairs")
    ax[0].legend(frameon=False, fontsize=8); ax[0].set_title("Pairwise abstract closeness")
    per = [p for p in s["per_super_node"] if p["mean_within"] is not None]
    y = np.arange(len(per))
    ax[1].barh(y + 0.2, [p["mean_within"] for p in per], 0.4, color="#0072B2", label="within the super-node")
    ax[1].barh(y - 0.2, [p["mean_to_other_papers"] for p in per], 0.4, color="#E69F00", label="to papers of other super-nodes")
    ax[1].set_yticks(y, [f"{p['super_node']} ({p['papers']} papers)" for p in per], fontsize=8)
    ax[1].invert_yaxis(); ax[1].set_xlabel("mean score"); ax[1].set_xlim(0, 10); ax[1].legend(frameon=False, fontsize=8, loc="lower right")
    ax[1].set_title("Per L0 super-node with two or more papers")
    fig.tight_layout(); fig.savefig(FIGURE, dpi=200, bbox_inches="tight"); plt.close(fig)


def _md(header, rows):
    return "\n".join(["| " + " | ".join(header) + " |", "|" + "---|" * len(header)]
                     + ["| " + " | ".join(str(c) for c in r) + " |" for r in rows]) + "\n"


def tables(res):
    c, s = res["coverage"], res["summary"]
    f = lambda x: "—" if x is None else f"{x:.2f}"   # noqa: E731
    cov = _md(["Item", "Value"], [
        ["Snapshot; level", f"≤{res['protocol']['cutoff']}; L0 ({c['super_nodes_l0']} super-nodes)"],
        ["Papers in the snapshot; with a verified abstract", f"{c['papers']}; {c['with_abstract']}"],
        ["Abstract sources", "; ".join(f"{k} {v}" for k, v in c["sources"].items())],
        ["L0 super-nodes holding papers with abstracts (papers per super-node)",
         f"{c['super_nodes_with_papers']} ({', '.join(map(str, c['papers_per_super_node']))})"],
        ["Pairs rated; unparsable answers", f"{c['pairs']}; {c['unparsed']}"],
        ["Scores used by the rater (pairs)", "; ".join(f"{v}: {a + b}" for v, (a, b) in
                                                       enumerate(zip(s["histogram"]["within"], s["histogram"]["across"])) if a + b)],
        ["Rater; decoding", f"{res['protocol']['model']}; temperature 0, one order per pair (id order)"]])
    summ = _md(["", "Pairs", "Mean closeness (0–10)"], [
        ["Same L0 super-node", s["pairs_within"], f(s["mean_within"])],
        ["Different L0 super-nodes", s["pairs_across"], f(s["mean_across"])],
        ["Difference [95% paper-bootstrap CI]", "", f"{f(s['difference'])} [{f(s['difference_ci95'][0])}, {f(s['difference_ci95'][1])}]"],
        [f"Permutation null (R = {s['permutation']['R']}): mean; 97.5% quantile", "",
         f"{f(s['permutation']['null_mean'])}; {f(s['permutation']['null_q97.5'])}"],
        ["One-sided permutation p", "", f"{s['permutation']['p']:.4f}"],
        ["Difference with one super-node's papers left out: lowest; highest", "",
         "; ".join(f"{f(x['difference'])} (without {x['dropped']})" for x in
                   (min(s["leave_one_super_node_out"], key=lambda x: x["difference"]),
                    max(s["leave_one_super_node_out"], key=lambda x: x["difference"])))]])
    per = _md(["L0 super-node", "Label", "Papers", "Pairs within", "Mean within", "Mean to other papers"],
              [[p["super_node"], res["labels"][p["super_node"]], p["papers"], p["pairs_within"], f(p["mean_within"]),
                f(p["mean_to_other_papers"])] for p in s["per_super_node"]])
    return {"coverage": cov, "summary": summ, "per_super_node": per}


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--run", type=Path, default=REPO_ROOT / "out")
    ap.add_argument("--check", action="store_true", help="exit 1 if results.json or REPORT.md would change")
    a = ap.parse_args(argv)
    cfg = load_config(a.run / "run_config.toml")
    tkh = load(cfg)
    cutoff = max(cfg.cutoffs)
    group = papers_of_l0(tkh, a.run, cutoff)
    text, man = abstracts(tkh, list(group))
    ids = [x for x in group if x in text]
    scores, llm = rate(tkh, ids, text, cfg.labels["endpoint"])
    h = json.loads((a.run / str(cutoff) / "hierarchy.json").read_text())
    labels = {s["id"]: s["label"] for s in h["supernodes"] if s["level"] == 0}
    from collections import Counter
    sizes = Counter(group[x] for x in ids)
    res = {"protocol": {"run": str(a.run.relative_to(REPO_ROOT)) if a.run.is_relative_to(REPO_ROOT) else str(a.run),
                        "alpha": cfg.method["alpha"], "cutoff": cutoff, "level": 0, "model": MODEL,
                        "prompt": PROMPT.name, "bootstrap_B": B, "permutation_R": R, "seed": SEED},
           "coverage": {"papers": len(group), "with_abstract": len(ids),
                        "sources": dict(Counter(man[str(x)]["source"] for x in ids)),
                        "super_nodes_l0": len(labels), "super_nodes_with_papers": len(sizes),
                        "papers_per_super_node": sorted(sizes.values(), reverse=True),
                        "pairs": len(scores), "unparsed": sum(v is None for v in scores.values())},
           "summary": analyse(ids, group, scores),
           "labels": labels,
           "pairs": [{"a": str(x), "b": str(y), "same_super_node": group[x] == group[y], "score": v}
                     for (x, y), v in scores.items()]}
    new_json = json.dumps(res, indent=1, ensure_ascii=False) + "\n"
    tb = tables(res)
    report = REPORT.read_text()
    new_report = BLOCK.sub(lambda m: m.group(1) + tb[m.group(2)] + m.group(4), report)
    if a.check:
        stale = [p.name for p, new in ((RESULTS, new_json), (REPORT, new_report)) if not p.exists() or p.read_text() != new]
        if stale:
            sys.exit(f"stale: {stale}; run python -m eval.extra.abstract_coherence")
        print(f"up to date ({llm.hits} cached ratings, {llm.calls} live calls)")
        return
    RESULTS.write_text(new_json)
    REPORT.write_text(new_report)
    figure(res)
    print(f"{len(ids)} papers, {len(scores)} pairs ({llm.calls} live calls) -> {RESULTS.name}, {REPORT.name}, {FIGURE.name}")


if __name__ == "__main__":
    main()
