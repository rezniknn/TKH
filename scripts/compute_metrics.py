"""Pipeline step 'metrics' (SHAC-T wrapper around the method-independent evaluator) -> out/metrics.json.

    python scripts/compute_metrics.py [--config CFG] [--eval configs/eval.toml] [--out DIR]
    TKH_LLM_MODE=live python scripts/compute_metrics.py        # fill the LLM cache for M3

1. The shipped run (<out>/, the selected configuration with LLM labels) is evaluated in full by scripts/evaluate.py:
   M1-M4, the M5 configuration-model nulls, the MDE degradations and M3 (claim-level entailment).
2. Every swept configuration and ablation (out/selection.json, runs under eval_cache/variants/) and a foreign,
   non-SHAC-T baseline (scripts/baseline_paper_linkage.py) are evaluated on M1, M2 and M4 (light mode).
3. Each variant is compared with the shipped run by scripts/compare_runs.py (paired deltas on dev evidence).
4. All rows and tests are merged into <out>/metrics.json (schema/metrics.schema.json) for make_tables.py.
"""

from pathlib import Path
import argparse
import json
import sys

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from scripts import compare_runs, evaluate  # noqa: E402
from tkh.config import add_config_args, config_from_args  # noqa: E402
from tkh.evalkit import runner  # noqa: E402

BASELINE_CMD = "{python} scripts/baseline_paper_linkage.py --graph {graph} --out {out} {extra}"


def data_rows(cfg):
    """Descriptive counts of the export used by the report (evaluator-side definitions, tkh/structure.py)."""
    from tkh.evaluate.extrinsic import load_questions
    from tkh.evaluate.groundtruth import load_ground_truth, question_targets
    from tkh.io import load, snapshot
    from tkh import structure as st
    import numpy as np
    tkh = load(cfg)
    out = []
    for c in cfg.cutoffs:
        s = snapshot(tkh, c)
        items, B, _, _ = st.concept_incidence(tkh, s, max_paper_share=0.2)
        concept = [v for v in s.node_ids if tkh.nodes.at[v, "type"] in st.CONCEPT_TYPES]
        X = B @ B.T
        n = len(items)
        linked = ((X > 0).sum() - n) / 2
        vals = {"papers": len(s.articles), "nodes": len(s.node_ids), "concept_nodes": len(concept), "hyperedges": len(s.edges),
                "clustering_edges": B.shape[1], "clustering_edges_per_paper": B.shape[1] / len(s.articles),
                "max_clustering_arity": int(B.sum(axis=0).max()), "hubs": len(concept) - n,
                "share_concept_in_at_most_one_edge": float((B.sum(axis=1) <= 1).mean()),
                "share_pairs_H_zero_singletons": float(1 - linked / (n * (n - 1) / 2))}
        out += [evaluate.row("data", k, "graph", v, snapshot=c) for k, v in vals.items()]
    qs = load_questions(cfg.questions)
    targets = question_targets(tkh, load_ground_truth(cfg.ground_truth), st.CONCEPT_TYPES)
    usable = sum(1 for q, t in targets.items() if q in qs and any(t["expected"].values()))
    out.append(evaluate.row("data", "usable_questions", "ground-truth", usable, n=len(targets)))
    return out


def main(argv=None):
    p = add_config_args(argparse.ArgumentParser(description=__doc__.split("\n")[0]))
    p.add_argument("--eval", type=Path, default=ROOT / "configs" / "eval.toml")
    p.add_argument("--out", type=Path, help="output directory (default: the config's out_dir)")
    p.add_argument("--skip-m3", action="store_true", help="skip the M3 LLM judge even if [m3] enabled")
    p.add_argument("--merge-only", action="store_true", help="re-merge existing per-run eval/metrics.json files")
    args = p.parse_args(argv)
    cfg = config_from_args(args)
    out = Path(args.out or cfg.out_dir)
    ev = evaluate.load_eval(args.eval)
    sel = json.loads((out / "selection.json").read_text())
    stages = "m1,m2,nulls,m4,mde,m3det" + (",m3" if ev["m3"].get("enabled") and not args.skip_m3 else "")
    if not args.merge_only:
        evaluate.main(["--run", str(out), "--name", "model", "--extra", sel["winner_extra"], "--stages", stages, "--eval", str(args.eval)])

    variants = {cid: g for cid, g in sel["configs"].items() if cid != sel["winner"]}
    variants.update({a["cid"]: a for a in sel["ablations"].values()})
    for cid, g in ([] if args.merge_only else variants.items()):
        evaluate.main(["--run", g["dir"], "--name", cid, "--extra", g["extra"], "--stages", "m1,m2,m4,m3det", "--light", "--eval", str(args.eval)])
    bdir = Path(ev["eval"]["cache_dir"]) / "variants" / "baseline-paper-linkage"
    if not args.merge_only:
        runner.build(BASELINE_CMD, cfg.graph, bdir, cwd=ROOT)
    if not args.merge_only:
        evaluate.main(["--run", str(bdir), "--name", "baseline-paper-linkage", "--build-cmd", BASELINE_CMD,
                   "--stages", "m1,m2,m4", "--light", "--eval", str(args.eval)])

    model = json.loads((out / "eval" / "metrics.json").read_text())
    rows, tests = list(model["rows"]), list(model["tests"])
    names = {"model": sel["winner"]}
    for cid, g in {**variants, "baseline-paper-linkage": {"dir": str(bdir)}}.items():
        m = json.loads((Path(g["dir"]) / "eval" / "metrics.json").read_text())
        rows += [r for r in m["rows"] if r["variant"] == cid]   # the run's own rows (baselines and nulls come from the model run)
        names[cid] = cid
    comp = {}
    for cid, g in {**variants, "baseline-paper-linkage": {"dir": str(bdir)}}.items():
        base_u, other_u = compare_runs.load_units(out), compare_runs.load_units(g["dir"])
        key = f"M1|{ev['eval']['primary_snapshot']}|{ev['eval']['primary_level']}|{ev['m1']['primary_stratum']}|A"
        d = {"M1": compare_runs.m1_delta(base_u, other_u, key), "M2": compare_runs.m2_delta(base_u, other_u),
             "M4": compare_runs.m4_delta(base_u, other_u)}
        comp[cid] = d
        for fam, x in d.items():
            rows.append(evaluate.row("compare", f"delta_{fam}", cid, x["delta"], ci_lo=x["lo"], ci_hi=x["hi"], n=x["n"]))
    for r in sel["table"]:
        rows.append(evaluate.row("selection", "coupling_lift_dev", r["cid"], r["value"], sel["protocol"]["snapshot"], sel["protocol"]["level"],
                                 sel["protocol"]["stratum"], "A", ci_lo=r.get("ci_lo"), ci_hi=r.get("ci_hi"),
                                 alpha=r["alpha"], se=r["se"], eligible=r["eligible"], within_1se=r["within_1se"], giant_share=r["giant_share"]))
    rows.append(evaluate.row("selection", "winner_agreement", sel["winner"], sel["stability"]["agreement"], n=len(sel["stability"]["winners"])))
    rows += data_rows(cfg)
    meta = {**model["meta"], "selected": sel["winner"], "selected_params": sel["selected_params"],
            "configs": {cid: g["params"]["alpha"] for cid, g in sel["configs"].items()},
            "ablations": {k: a["cid"] for k, a in sel["ablations"].items()}, "baseline": "baseline-paper-linkage",
            "labels": {k: cfg.labels.get(k) for k in ("labeller_model", "judge_model")}}
    (out / "metrics.json").write_text(json.dumps({"meta": meta, "rows": rows, "tests": tests}, indent=1, default=float) + "\n")
    print(f"{len(rows)} rows, {len(tests)} tests -> {out / 'metrics.json'}")


if __name__ == "__main__":
    main()
