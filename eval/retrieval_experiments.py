"""Retrieval experiments: a staged search over the agent's Settings (tkh/retrieve.py) on the T6 questions, scored by the
unchanged evaluator (eval/retrieval.py). The hierarchy, the snapshot rule and k = 10 are fixed.

Selection objective, fixed before the runs: H = mean over the questions with targets of (item hit-rate + citation
hit-rate) / 2 for the drill-down agent; when two runs are within 0.01 in H, the lower mean steps-to-target wins.
Stages (each starts from the previous winner; every run is recorded):
  E0  baseline reproduction            E1  nodes kept per level (fixed beams, relative thresholds)
  E2  super-node information           E3  leaf information
  E4  scorer x super-node information  E5  question text
  E6  nodes kept per level again, under the E2-E5 winners
Selecting on the evaluation questions is optimistic. `loo` gives a leave-one-question-out estimate of the selection
over every configuration run: each question is scored with the configuration that is best on the other questions.
"""

from dataclasses import asdict, replace
import json

import numpy as np

from eval.retrieval import GT_DEFAULT, Q_DEFAULT, _boot, evaluate, objective, read_questions, summarise
from tkh.retrieve import LEAF_INFO, NODE_INFO, QUERY, SCORERS, Agent, Settings

BEAMS = [(1, 1, 1), (2, 3, 4), (3, 4, 5), (4, 6, 8), (5, 8, 12), (7, 15, 30), (10, 20, 40), (15, 8, 12), (15, 15, 30),
         (15, 30, 60)]   # 15 at L0 = no pruning at L0
RELS = [(0.5, 1), (0.5, 3), (0.7, 1), (0.7, 3), (0.9, 1), (0.9, 3)]   # (rel, min_keep), no cap
NO_CAP = (10 ** 6,) * 3
TIE = 0.01
BASELINE = Settings(beam=(3, 4, 5), node_info="blend", leaf_info="full", scorer="tfidf", query="stripped")


def name(s):
    beam = f"rel{s.rel}/min{s.min_keep}" if s.rel is not None else "beam" + "-".join(map(str, s.beam))
    return f"{beam} {s.node_info} {s.leaf_info} {s.scorer} {s.query}"


class Runner:
    def __init__(self, tkh, run_dir, cutoffs, questions, gt):
        self.tkh, self.run_dir, self.cutoffs, self.questions, self.gt = tkh, run_dir, cutoffs, questions, gt
        self.cache, self.golds, self.runs = {}, {}, {}

    def run(self, s, exp):
        key = name(s)
        if key not in self.runs:
            per_q, _ = evaluate(Agent(self.tkh, self.run_dir, self.cutoffs, s, self.cache), self.questions, self.gt,
                                self.golds)
            rec = {"name": key, "settings": {k: (list(v) if isinstance(v, tuple) else v) for k, v in asdict(s).items()},
                   "experiments": []}
            for system in ("hier", "flat"):
                H, h = objective(per_q, system)
                steps = {q: p[system]["steps"] for q, p in per_q.items() if p[system]["steps"] is not None}
                rec[system] = {"H": H, "h": h, "steps": steps, "mean_steps": float(np.mean(list(steps.values()))),
                               "reached": sum(p[system]["reached"] for p in per_q.values() if p["n_targets"]),
                               # breadth diagnostics: citation hit-rate rises with the number of articles cited
                               "mean_articles": float(np.mean([p[system]["n_articles"] for p in per_q.values()])),
                               "citation_precision": (sum(p[system]["citations"]["hits"] for p in per_q.values()) /
                                                      max(1, sum(p[system]["n_articles"] for p in per_q.values())))}
            rec["hier"]["supernodes_scored"] = float(np.mean([p["n_supernodes_scored"] for p in per_q.values()]))
            sm = summarise(per_q, B=2000, seed=0)
            rec["summary"] = {t: {m: {sy: (v[sy]["mean"] if v.get(sy) else None) for sy in ("hier", "flat")}
                                  for m, v in r.items() if m != "n_questions"} for t, r in sm.items()}
            self.runs[key] = rec
        if exp not in self.runs[key]["experiments"]:
            self.runs[key]["experiments"].append(exp)
        return self.runs[key]

    def stage(self, exp, settings):
        recs = [self.run(s, exp) for s in settings]
        return settings[_best(recs)], [r["name"] for r in recs]


def _best(recs):
    top = max(r["hier"]["H"] for r in recs)
    near = [i for i, r in enumerate(recs) if r["hier"]["H"] >= top - TIE]
    return min(near, key=lambda i: (recs[i]["hier"]["mean_steps"], -recs[i]["hier"]["H"]))


def beam_grid(s):
    return ([replace(s, beam=b, rel=None, min_keep=1) for b in BEAMS] +
            [replace(s, beam=NO_CAP, rel=r, min_keep=m) for r, m in RELS])


def loo(runs):
    """Leave-one-question-out estimate of choosing the best configuration (same rule as `_best`) on the others."""
    qs = sorted(next(iter(runs))["hier"]["h"])
    h, steps, chosen = {}, {}, {}
    for q in qs:
        rest = [{"hier": {"H": float(np.mean([v for k, v in r["hier"]["h"].items() if k != q])),
                          "mean_steps": float(np.mean([v for k, v in r["hier"]["steps"].items() if k != q]))}}
                for r in runs]
        r = runs[_best(rest)]
        h[q], steps[q], chosen[q] = r["hier"]["h"][q], r["hier"]["steps"][q], r["name"]
    return {"H": float(np.mean(list(h.values()))), "mean_steps": float(np.mean(list(steps.values()))),
            "h": h, "steps": steps, "chosen": chosen}


def sweep(tkh, run_dir, cutoffs, questions_path=Q_DEFAULT, gt_path=GT_DEFAULT):
    questions = read_questions(questions_path)
    gt = json.loads(open(gt_path, encoding="utf-8").read())
    R = Runner(tkh, run_dir, cutoffs, questions, gt)
    stages = {}
    s, stages["E0"] = BASELINE, [R.run(BASELINE, "E0")["name"]]
    s, stages["E1"] = R.stage("E1", beam_grid(s))
    s, stages["E2"] = R.stage("E2", [replace(s, node_info=n) for n in NODE_INFO])
    s, stages["E3"] = R.stage("E3", [replace(s, leaf_info=x) for x in LEAF_INFO])
    s, stages["E4"] = R.stage("E4", [replace(s, scorer=sc, node_info=n) for sc in SCORERS for n in NODE_INFO])
    s, stages["E5"] = R.stage("E5", [replace(s, query=x) for x in QUERY])
    s, stages["E6"] = R.stage("E6", beam_grid(s))
    runs = list(R.runs.values())
    base, best = R.runs[name(BASELINE)], R.runs[name(s)]
    qs = sorted(base["hier"]["h"])
    paired = {"H": _boot([best["hier"]["h"][q] - base["hier"]["h"][q] for q in qs], 2000, 0),
              "steps": _boot([best["hier"]["steps"][q] - base["hier"]["steps"][q] for q in qs], 2000, 0),
              "H_vs_flat": _boot([best["hier"]["h"][q] - best["flat"]["h"][q] for q in qs], 2000, 0),
              "steps_vs_flat": _boot([best["hier"]["steps"][q] - best["flat"]["steps"][q] for q in qs], 2000, 0)}
    return {"objective": "H = mean over questions with targets of (item + citation hit-rate) / 2, hierarchical; "
                         f"ties within {TIE} -> lower mean steps",
            "stages": stages, "baseline": base["name"], "best": best["name"],
            "best_settings": best["settings"], "paired_best_minus_baseline": paired, "loo": loo(runs), "runs": runs}


def pareto_figure(res, path):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fig, ax = plt.subplots(figsize=(6, 4))
    runs = res["runs"]
    ax.scatter([r["hier"]["mean_steps"] for r in runs], [r["hier"]["H"] for r in runs], s=14, c="0.6",
               label="drill-down, each run")
    for key, mk, lab in ((res["baseline"], "s", "baseline (E0)"), (res["best"], "*", "selected")):
        r = next(x for x in runs if x["name"] == key)
        ax.scatter(r["hier"]["mean_steps"], r["hier"]["H"], marker=mk, s=110, label=f"{lab}, drill-down", zorder=3)
        ax.scatter(r["flat"]["mean_steps"], r["flat"]["H"], marker=mk, s=110, facecolors="none", edgecolors="k",
                   label=f"{lab}, flat", zorder=3)
    ax.set_xlabel("mean steps-to-target (censored)")
    ax.set_ylabel("H (mean of item and citation hit-rates)")
    ax.legend(fontsize=7, frameon=False)
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)
