# Evaluation report: SHAC hierarchy on the TKH graph (run out/, 2026-10-28)

All numbers in this report are read from files in `out/` (mainly `out/metrics.json`) or recomputed from them by read-only scripts. Recomputed values are marked *(derived)*, with a note on how each was obtained. The JSON path of every reported result is listed in the Appendix. Snapshots are written ≤t (cutoff year t) and levels as L0 (15 super-nodes, coarsest), L1 (60) and L2 (240, finest).

## 1. Summary

The three-level hierarchy (budgets 15 / 60 / 240) was evaluated at four snapshots (cutoffs 2020–2026) on three properties: held-out semantic coherence (P3), temporal stability (P5) and label faithfulness (P6). Its extrinsic utility was tested with a drill-down retrieval agent against flat search (brief T6). The main findings are as follows.

- **Coherence.** At ≤2024 and ≤2026 the finer levels group concepts of citation-coupled, concept-disjoint papers more than both nulls do. At ≤2022 this holds only under fuzzy matching (L1) or only under the `year1` scheme (exact). Under the strict criterion (exact matching, all five period schemes), three cells are robust: ≤2026 L1 and L2, and ≤2024 L2. L0 shows no coherence at any snapshot. Under exact matching, every lift rests on 5–58 coupled pairs (fuzzy: 4–51), and every paper-bootstrap CI includes 1, so this is evidence for the corpus at hand, not a population estimate.
- **Stability.** Cross-snapshot persistence is high (HARI 0.80–0.89). It is about as high when new papers attach at random (new-paper null), so it is not due to the real attachment pattern; it comes from what the null keeps (the real ≤t−1 graph, the real t−1 hierarchy and the γ = 0.5 prior), and which of these is responsible is not separated. Per node, touched nodes are reassigned 2.4–7.0× as often as untouched ones (all CI lower bounds ≥ 2.0), but 78–89% of total reassignment falls on untouched nodes. Robustness to a 10% edge perturbation is low at the coarse levels of late snapshots (≤2026 L0 ARI 0.12). There is no γ = 0 control on the current build (§4, §8.2).
- **Retrieval (T6).** On 18 questions (n per metric 4–14), the drill-down is higher than flat search on citations (A 0.657 vs 0.578, B 0.438 vs 0.375) and type-B claims (0.740 vs 0.543), and slightly lower on type-A methods (0.275 vs 0.295) and method claims (0.250 vs 0.306). It costs far more steps: median 206.5 vs 10.5 to the first item (A), because it scores 133–162 super-nodes before any leaf. It misses 2 questions at L1. The evidence is descriptive: there are no CIs or nulls, and the settings were chosen with these questions in view (§6).
- **Labels.** Model labels over-claim in 0.58 of cases: most assert at least one claim that the held-out half of the evidence does not support (0.37 at L0, 0.64 at L1). The judge itself is not validated and there is no chance baseline, so this is a descriptive rate (§5, §8.3).

| Property | Test | Result | Verdict |
|---|---|---|---|
| P1 laminarity, P2 budgets | Read-only check of `out/<t>/hierarchy.json` (§7) | 15 / 60 / 240 super-nodes at every snapshot; each member in exactly one super-node per level; every child a subset of its parent | Holds (by construction; re-checked) |
| P3 coherence | Held-out coupling lift, interval scheme, exact matching, vs 99 configuration-null rebuilds and 999 random-label permutations (§3) | ≤2026 L1 1.31 [0.541, 2.00], L2 1.57 [0.426, 2.63]; ≤2024 L2 1.86 [0.348, 3.17]; p at the floors 0.01 / 0.001 | Robust (exact, 5/5 schemes) at ≤2026 L1–L2 and ≤2024 L2; ≤2024 L1 robust under fuzzy only (exact fails `gap`: lift 1.10, p = 0.10 / 0.152); not at L0; ≤2022 depends on scheme and matching; ≤2020 not evidence (L2 undefined) |
| P3, L0 | Same test | 0.879 (≤2026), 0.825 (≤2024), 0.550 (≤2022); p = 1.0 | No coherence |
| P5 persistence | Cross-snapshot ARI/HARI vs new-paper null, R = 99 (§4.3) | HARI 0.86 / 0.80 / 0.89; all 12 values above the null mean by 0.005–0.055; 1 of 12 outside the null band | High, but no higher than under random attachment; not evidence that the corpus' own evolution is stable |
| P5 localisation | Reassignment of touched vs untouched old nodes (§4.4) | Ratio 2.4–7.0, all CI lower bounds ≥ 2.0; 78–89% of reassignment on untouched nodes | Per node, change concentrated on touched nodes; most total change on untouched nodes; untouched regions held, not frozen |
| Robustness | 10% edge perturbation, 5 seeds (§4.2) | ≤2026 ARI L0 0.12 [0.11, 0.13], L2 0.63 [0.61, 0.65]; HARI 0.17 [0.16, 0.18] | L2 the most robust level (ARI 0.63–0.90), only moderately robust late; L0–L1 at late snapshots are not (0.12–0.30) |
| P6 faithfulness | Over-claim against held-out evidence (§5.2) | 0.58 [0.52, 0.64], n = 296; L0 0.37, L1 0.64; never-tuned cells 0.64 [0.58, 0.71] *(derived)* | Most labels assert at least one unsupported claim (judge not validated; no null baseline) |
| P6 temporal honesty | Deterministic checks (§5.3) | 0 years after the cutoff; 4 `future_entity` flags, all surface-form collisions | No leak found |
| T6 extrinsic utility | Drill-down agent vs flat search on 18 questions, hit-rate and steps-to-target (§6) | Hit-rate A methods 0.275 vs 0.295, A citations 0.657 vs 0.578, B claims 0.740 vs 0.543; median steps to first item A 206.5 vs 10.5, B 143 vs 2; reach 14/16 vs 16/16 | Mixed accuracy at a much higher step cost; descriptive (no CIs, no nulls) |

## 2. Run and protocol

### 2.1 Data and method

| Item | Value | Source |
|---|---|---|
| Inputs | `data/tkh_collection10.json`, `data/collection10_articles.csv` | `out/run_config.toml [inputs]` |
| Cutoffs | 2020, 2022, 2024, 2026 | `[snapshots]` |
| Budgets | [15, 60, 240] (L0 coarsest) | `[hierarchy]` |
| Method | α = 0.5, γ = 0.5, ρ = 2.0, `relation_balanced` edge weights, `hub_frac` = 0.2, `lsa_dim` = 100 | `[method]`; `run_info.cid` = `a0.5_g0.5_r2_relation_balanced_h0.2_d100` |
| Labels | labeller `qwen2.5:7b-instruct`, judge `phi4`, `contrast` = 10, `max_items` = 40, `seed` = 0, `mode` = "offline" | `[labels]` |
| Build runtime | 34.7 s (labeller answers replayed from `data/llm_cache.json`) | `run_info.runtime_s` |

Per snapshot (`out/run_info.json → snapshots.<t>`):

| Snapshot | Concept nodes | Clustering edges | Anchored nodes | Stable set \|U_t\| | Hubs | Super-nodes L0 / L1 / L2 | Max size L0 / L1 / L2 (cap) |
|---|---|---|---|---|---|---|---|
| ≤2020 | 1018 | 141 | 457 | 0 | 5 | 15 / 60 / 240 | 135 (135.73) / 33 (33.93) / 8 (8.48) |
| ≤2022 | 1464 | 230 | 680 | 876 | 8 | 15 / 60 / 240 | 194 (195.2) / 45 (48.8) / 12 (12.2) |
| ≤2024 | 2829 | 406 | 1265 | 1169 | 7 | 15 / 60 / 240 | 359 (377.2) / 93 (94.3) / 23 (23.57) |
| ≤2026 | 3980 | 554 | 1818 | 2629 | 6 | 15 / 60 / 240 | 512 (530.67) / 120 (132.67) / 33 (33.17) |

Max sizes and caps count concept nodes only. ≤2020 has no temporal prior (no earlier snapshot), so its stable set is empty.

### 2.2 What each check uses

| Check | Input | References | Code |
|---|---|---|---|
| Coherence (§3) | Concept co-assignment per level; bibliographic coupling of citing papers, which the clustering never sees | 99 configuration-null rebuilds; 999 random-label permutations | `eval/coherence.py`, `eval/experiments.py` (`coherence_check`); formal statement §8 |
| Stability (§4) | Concept-node partitions of the run, of 5 perturbed rebuilds per snapshot, and of 99 new-paper-null rebuilds per transition; `out/temporal_events.json` | Unperturbed run; new-paper (attachment) null | `eval/stability.py`, `tkh/null.py`, `tkh/temporal.py`; formal statement §9 |
| Labels (§5) | Labels and glosses at L0–L1, all snapshots; seen/held-out evidence in `out/<t>/label_inputs.json` | None (no known-answer controls, no nulls) | `eval/faithfulness.py`, `tkh/label.py`, `configs/prompts/` |
| Retrieval (§6) | `out/<t>/hierarchy.json` and the snapshot's graph; `data/questions.csv`; `data/ground_truth.json` (evaluator only) | Flat search with the same scorer | `tkh/retrieve.py`, `eval/retrieval.py`; design in `notebooks/04_retrieval_design.ipynb` |

### 2.3 Provenance

- **Latest run.** `out/` was rebuilt and every check re-run on 2026-10-28, offline: `make build` (file times 15:42, `runtime_s` 34.7) and then `make metrics` (coherence → stability → faithfulness → retrieval; file times 16:14). `tkh/pipeline.py` deletes `metrics.json` on every build, so all four sections come from this run. No step was re-run for this update of the report.
- **Results unchanged.** The values in `out/metrics.json` are identical, field by field, to those committed at HEAD (23ecf8c); the file differs only in the order of its sections. `out/<t>/hierarchy.json`, `label_inputs.json`, `coarse_hyperedges.json`, `out/temporal_events.json`, `out/faithfulness_judgements.json` (757 records) and `out/retrieval_answers.json` are byte-identical to HEAD, labels and glosses included. `out/run_info.json` differs only in `runtime_s` (476.2 s at HEAD). Method parameters: α = 0.5, γ = 0.5, ρ = 2.0, `relation_balanced`, `hub_frac` = 0.2, `lsa_dim` = 100 (§2.1).
- **Labels.** `faithfulness` is an offline replay of the cached judge answers on the labels of the contrastive labeller (`contrast` = 10). `eval/__main__.py` drops the earlier `labels` section (known-answer controls and nulls), which is no longer in `metrics.json`.
- **Retrieval.** `retrieval` is the last step of `make metrics` and makes no LLM calls.
- **Committed with this report:** the re-run's `out/metrics.json` (it differs from the previous commit in section order only) and `out/run_info.json` (`runtime_s` only). `docs/figures/` still matches, since no metric value changed.

### 2.4 Reproduction

```
make build        # SHAC hierarchy for every snapshot -> out/
make validate     # validate.py against out/run_config.toml
make coherence    # 99 configuration-null rebuilds, 999 random labels
make stability    # perturbation (10%, 5 seeds), cross-snapshot vs new-paper null
make faithfulness # held-out judge on every L0–L1 label (offline cache replay)
make retrieval    # T6: drill-down agent vs flat search (offline, seconds)
make figures      # docs/figures/*.png from out/metrics.json
make test
```

`make all` runs build → validate → metrics → test, where `make metrics` runs coherence → stability → faithfulness → retrieval; each check also has its own target. All LLM calls replay from the response cache `data/llm_cache.json` when `TKH_LLM_MODE` is unset (offline, the default). If `TKH_LLM_MODE=live` is exported, `make build` and `make faithfulness` call a local Ollama server instead; run `unset TKH_LLM_MODE` first. The latest run (2026-10-28) was `make build` followed by `make metrics`, with every LLM answer replayed from the cache (§2.3). `validate.py` and `make test` write nothing to `out/`, so whether they ran is not recorded.

## 3. Coherence: held-out bibliographic coupling (P3)

### 3.1 What is measured and why it is held out

The check asks whether the hierarchy groups concepts from papers that are close in meaning. The proxy for closeness is **bibliographic coupling**: the IDF-weighted Salton cosine c_pq of two citing papers' cited-work sets (`Ruler` in `eval/coherence.py`). The signal is independent of the method's inputs in three ways.

- **The relation is not an input.** The clustering hypergraph uses only the six method-centred relations. `cites`, `claims`, `presents`, `authored_by` and `proposes_future_work` never enter it (`tkh/coarsen.py`, module docstring). In `tkh/hierarchy.py`, citations are used only to anchor non-concept cited-work nodes (formal statement §5). Co-assignment uses concept nodes only (`Ruler.Pn`).
- **A residual filter removes name leakage.** A paper's citations are dropped when the cited work is named like one of that paper's own non-hub concept nodes, so "extends X / cites X" does not count. *Exact* matching requires equal normalised names. *Fuzzy* matching also accepts containment for names of at least 4 characters.
- **Only no-overlap pairs are scored.** These are citing-paper pairs that share no concept node and no concept name. The evaluator's own hub set is excluded, with `EVAL_HUB_FRAC` = 0.4, independent of the method's `hub_frac` = 0.2. On these pairs, shared structure cannot explain co-assignment.

The co-assignment of papers p and q at a level is a_pq = Σ_S n_S(p) n_S(q) / (n_p n_q). The lift is Σ a·c / Σ a·e, where e is the expected coupling. Without adjustment, e is the mean coupling over all no-overlap pairs. With period adjustment (indirect standardisation), e is the mean coupling of no-overlap pairs in the same period stratum. The primary scheme is `interval` (the snapshot cutoff intervals); the sensitivity schemes are `year1`, `year2`, `year3` (year bins) and `gap` (absolute year gap). A lift of 1 means chance.

Each lift is compared with two references:
- **Configuration null:** R = 99 rebuilds of the whole pipeline on type- and period-preserving hypergraph configuration-model graphs.
- **Random labels:** R = 999 permutations of concept ids within (type, entry interval) over the evaluated tree.

p-values are one-sided, p = (1 + #null ≥ obs)/(R + 1), with floors 0.01 and 0.001 (`coherence.p`, `coherence.R`, `coherence.R_labels`). The 95% CIs come from a paper-cluster bootstrap with B = 200 draws (`Ruler.bootstrap`). Draws with no co-assigned pair are dropped, and `bootstrap_defined` reports how many remain.

### 3.2 Verdict criterion

Formal statement §8 calls a cell **robust** only if it beats both nulls under every period scheme. §8 and this report use the same threshold: **p ≤ 0.05 against both nulls** under every period-adjusted scheme. Almost every passing cell is at the floor (p = 0.01 / 0.001). Only two passing cells are off the floor:
- exact, ≤2022, L2, `year1`: p = 0.03 / 0.008;
- fuzzy, ≤2022, L2, `interval`: random-label p = 0.002.

Two failing cells are close to the threshold:
- exact, ≤2024, L1, unadjusted: configuration-null p = 0.04, random-label p = 0.101;
- exact, ≤2024, L1, `gap`: p = 0.10 / 0.152 (`coherence.snapshots.2024.levels[1].exact.gap`). This cell decides the exact verdict for ≤2024 L1.

Because most passing p-values sit at the floors, p cannot rank the strength of passing results. The z-scores in §3.4 (z = (lift − null mean)/null SD, `<null>.z`) are the graded measure in the file; each lift also carries a bootstrap standard error (`se`).

"Every scheme" means the five period-adjusted schemes. The unadjusted lift is shown for reference but is not required: it rewards same-era citation, which both nulls preserve.

### 3.3 Coverage per snapshot

| Snapshot | Citing papers (exact / fuzzy) | No-overlap pairs | Coupled no-overlap pairs | Interval strata | Citations removed by residual filter |
|---|---|---|---|---|---|
| ≤2020 | 9 / 9 | 18 / 18 | 5 / 4 | 1 / 1 | 38 / 56 |
| ≤2022 | 14 / 14 | 34 / 34 | 11 / 10 | 3 / 3 | 73 / 107 |
| ≤2024 | 25 / 24 | 100 / 94 | 21 / 20 | 6 / 6 | 162 / 222 |
| ≤2026 | 37 / 36 | 253 / 239 | 58 / 51 | 10 / 10 | 260 / 342 |

Pairs are unordered (upper triangle of the mask). "Coupled" means c_pq > 0. Under exact matching, every lift rests on 5–58 coupled pairs. At ≤2020 there is a single interval stratum, so the interval-adjusted lift equals the unadjusted one.

### 3.4 Primary result: interval-adjusted, exact matching

Each null column gives the null mean [2.5%, 97.5% quantiles]; p is one-sided; z = (lift − null mean)/null SD (`configuration_null.z`, `random_labels.z`). The ≤2020 |z| values are extreme, but they rest on 5 coupled pairs and are not evidence (§3.7).

![Held-out coherence lift per snapshot and level against both nulls](figures/coherence_lift.png)

*Figure 1 (`docs/figures/coherence_lift.png`). Interval-adjusted lift, exact matching, with both null bands; log y-axis, chance = 1 dashed. Triangles mark intervals clipped at the axis (≤2020 lower bounds at L0 and L1). ≤2020 L2 is shown as undefined.*

| Snapshot | Level (super-nodes) | Lift [95% bootstrap CI] | Defined draws | Configuration null | p | z | Random labels | p | z |
|---|---|---|---|---|---|---|---|---|---|
| ≤2026 | 0 (15) | 0.879 [0.532, 1.25] | 200/200 | 1.00 [0.950, 1.06] | 1.0 | −4.5 | 1.01 [0.964, 1.06] | 1.0 | −5.4 |
| ≤2026 | 1 (60) | 1.31 [0.541, 2.00] | 200/200 | 1.01 [0.945, 1.08] | **0.01** | 8.2 | 1.01 [0.940, 1.07] | **0.001** | 9.3 |
| ≤2026 | 2 (240) | 1.57 [0.426, 2.63] | 200/200 | 1.01 [0.920, 1.13] | **0.01** | 9.8 | 0.993 [0.899, 1.10] | **0.001** | 11 |
| ≤2024 | 0 (15) | 0.825 [0.353, 1.54] | 199/200 | 1.01 [0.953, 1.06] | 1.0 | −6.2 | 1.02 [0.960, 1.07] | 1.0 | −6.8 |
| ≤2024 | 1 (60) | 1.32 [0.377, 2.25] | 199/200 | 1.01 [0.925, 1.11] | **0.01** | 7.4 | 1.00 [0.924, 1.08] | **0.001** | 8.0 |
| ≤2024 | 2 (240) | 1.86 [0.348, 3.17] | 199/200 | 1.02 [0.895, 1.13] | **0.01** | 13 | 0.995 [0.874, 1.12] | **0.001** | 14 |
| ≤2022 | 0 (15) | 0.550 [0.050, 2.18] | 195/200 | 0.986 [0.909, 1.05] | 1.0 | −12 | 1.00 [0.921, 1.08] | 1.0 | −11 |
| ≤2022 | 1 (60) | 1.06 [0.260, 3.20] | 195/200 | 0.999 [0.878, 1.10] | 0.17 | 1.0 | 1.00 [0.894, 1.10] | 0.139 | 1.1 |
| ≤2022 | 2 (240) | 0.987 [0.466, 2.67] | 195/200 | 1.08 [0.894, 1.28] | 0.76 | −0.86 | 1.01 [0.826, 1.20] | 0.60 | −0.27 |
| ≤2020 | 0 (15) | 0.034 [0.002, 4.93] | 165/200 | 0.959 [0.831, 1.10] | 1.0 | −14 | 0.985 [0.888, 1.08] | 1.0 | −19 |
| ≤2020 | 1 (60) | 0.155 [0.000, 6.98] | 129/200 | 0.962 [0.823, 1.08] | 1.0 | −13 | 0.978 [0.846, 1.10] | 1.0 | −13 |
| ≤2020 | 2 (240) | undefined | 0/200 | 1.03 [0.795, 1.33] | – | – | 1.03 [0.811, 1.26] | – | – |

After interval adjustment, both null means are 0.96–1.08 in every cell, so the adjustment does what it is meant to do. Without it, the L2 null means are 1.20 / 1.21 (≤2026) and 1.22 / 1.22 (≤2024), the same-period inflation described in formal statement §8. With it, they fall to 1.01 / 0.993 and 1.02 / 0.995.

### 3.5 Fuzzy matching (interval-adjusted)

| Snapshot | Level | Lift [95% CI] | Defined draws | Configuration null | p | Random labels | p |
|---|---|---|---|---|---|---|---|
| ≤2026 | 0 | 0.972 [0.676, 1.39] | 200/200 | 1.01 [0.959, 1.05] | 0.92 | 1.02 [0.971, 1.06] | 0.971 |
| ≤2026 | 1 | 1.50 [0.856, 2.42] | 200/200 | 1.02 [0.955, 1.10] | **0.01** | 1.02 [0.955, 1.08] | **0.001** |
| ≤2026 | 2 | 1.85 [0.705, 2.89] | 200/200 | 1.02 [0.919, 1.14] | **0.01** | 1.00 [0.905, 1.12] | **0.001** |
| ≤2024 | 0 | 0.919 [0.443, 1.55] | 200/200 | 1.02 [0.949, 1.07] | 1.0 | 1.02 [0.965, 1.08] | 1.0 |
| ≤2024 | 1 | 1.64 [0.448, 2.93] | 200/200 | 1.02 [0.919, 1.11] | **0.01** | 1.00 [0.930, 1.08] | **0.001** |
| ≤2024 | 2 | 2.02 [0.465, 3.51] | 200/200 | 1.03 [0.884, 1.16] | **0.01** | 0.991 [0.863, 1.12] | **0.001** |
| ≤2022 | 0 | 0.811 [0.053, 2.42] | 195/200 | 0.994 [0.911, 1.07] | 1.0 | 1.01 [0.937, 1.10] | 1.0 |
| ≤2022 | 1 | 1.84 [0.262, 3.65] | 195/200 | 1.01 [0.874, 1.16] | **0.01** | 1.02 [0.894, 1.13] | **0.001** |
| ≤2022 | 2 | 1.56 [0.651, 3.20] | 195/200 | 1.09 [0.850, 1.38] | **0.01** | 1.02 [0.772, 1.28] | **0.002** |
| ≤2020 | 0 | 0.038 [0.0001, 4.03] | 165/200 | 0.968 [0.825, 1.07] | 1.0 | 0.985 [0.897, 1.07] | 1.0 |
| ≤2020 | 1 | 0.136 [0.000, 9.05] | 129/200 | 0.983 [0.794, 1.16] | 1.0 | 0.986 [0.854, 1.13] | 1.0 |
| ≤2020 | 2 | undefined | 0/200 | 1.05 [0.740, 1.42] | – | 1.04 [0.761, 1.34] | – |

Fuzzy matching removes more citations (342 against 260 at ≤2026) and leaves slightly fewer coupled pairs (51 against 58). Under the interval scheme it gives higher lifts at L1–L2 at ≤2022–≤2026 (not at ≤2020 L1: 0.136 against 0.155 exact); under some sensitivity schemes it is also lower (≤2024 L2 `year1`: 1.60 against 1.80). At ≤2022 it makes L1 and L2 significant under the primary scheme. At L0 it brings the lift closer to 1 (0.972 at ≤2026, inside both null bands) but never significantly above the nulls.

### 3.6 Period-scheme sensitivity

Lifts per scheme. **Bold** marks a lift that beats both nulls at p ≤ 0.05. The last column counts the period-adjusted schemes passed, out of 5.

![Lift under each period scheme](figures/coherence_period_sensitivity.png)

*Figure 2 (`docs/figures/coherence_period_sensitivity.png`). Lift at ≤2026 for each period scheme and level, exact vs fuzzy matching; the primary scheme is shaded.*

**Exact matching**

| Snapshot | Level | Unadjusted | Interval | Year1 | Year2 | Year3 | Gap | Adjusted schemes passed |
|---|---|---|---|---|---|---|---|---|
| ≤2026 | 0 | 0.839 | 0.879 | 0.859 | 0.877 | 0.889 | 0.818 | 0/5 |
| ≤2026 | 1 | **1.25** | **1.31** | **1.24** | **1.17** | **1.24** | **1.22** | 5/5 |
| ≤2026 | 2 | **1.52** | **1.57** | **1.65** | **1.55** | **1.60** | **1.60** | 5/5 |
| ≤2024 | 0 | 0.741 | 0.825 | 0.824 | 0.900 | 0.887 | 0.730 | 0/5 |
| ≤2024 | 1 | 1.18 | **1.32** | **1.60** | **1.23** | **1.28** | 1.10 | 4/5 |
| ≤2024 | 2 | **1.58** | **1.86** | **1.80** | **1.50** | **1.68** | **1.47** | 5/5 |
| ≤2022 | 0 | 0.526 | 0.550 | 0.657 | 0.649 | 0.556 | 0.471 | 0/5 |
| ≤2022 | 1 | 1.06 | 1.06 | **1.29** | 0.989 | 1.08 | 0.921 | 1/5 |
| ≤2022 | 2 | 1.01 | 0.987 | **1.16** | 0.943 | 0.891 | 0.914 | 1/5 |
| ≤2020 | 0 | 0.034 | 0.034 | 0.366 | 0.507 | 0.074 | 0.086 | 0/5 |
| ≤2020 | 1 | 0.155 | 0.155 | **2.54** | **3.03** | **3.76** | 0.182 | 3/5 |
| ≤2020 | 2 | – | – | – | – | – | – | not evaluable |

**Fuzzy matching**

| Snapshot | Level | Unadjusted | Interval | Year1 | Year2 | Year3 | Gap | Adjusted schemes passed |
|---|---|---|---|---|---|---|---|---|
| ≤2026 | 0 | 0.975 | 0.972 | 0.912 | 0.982 | 0.998 | 0.932 | 0/5 |
| ≤2026 | 1 | **1.42** | **1.50** | **1.39** | **1.37** | **1.41** | **1.41** | 5/5 |
| ≤2026 | 2 | **1.86** | **1.85** | **1.96** | **1.90** | **1.96** | **1.99** | 5/5 |
| ≤2024 | 0 | 0.937 | 0.919 | 0.842 | 1.03 | 1.04 | 0.897 | 0/5 |
| ≤2024 | 1 | **1.48** | **1.64** | **1.59** | **1.45** | **1.54** | **1.32** | 5/5 |
| ≤2024 | 2 | **1.80** | **2.02** | **1.60** | **1.64** | **1.88** | **1.65** | 5/5 |
| ≤2022 | 0 | 0.851 | 0.811 | 0.715 | 0.807 | 0.719 | 0.627 | 0/5 |
| ≤2022 | 1 | **1.82** | **1.84** | **1.33** | **1.47** | **1.60** | **1.38** | 5/5 |
| ≤2022 | 2 | **1.50** | **1.56** | 1.14 | 1.22 | 1.20 | 1.12 | 1/5 |
| ≤2020 | 0 | 0.038 | 0.038 | 0.676 | 0.554 | 0.090 | 0.867 | 0/5 |
| ≤2020 | 1 | 0.136 | 0.136 | **2.75** | **2.51** | **4.25** | **3.78** | 4/5 |
| ≤2020 | 2 | – | – | – | – | – | – | not evaluable |

**Does the conclusion change across schemes?**
- At ≤2026, L1 and L2 pass under all five schemes with both matchings, and the lift varies little (exact: 1.17–1.31 at L1, 1.55–1.65 at L2).
- At ≤2024, L2 passes everywhere. Exact L1 fails only under `gap` (1.10; p = 0.10 / 0.152), and its unadjusted lift (1.18) also fails the random-label null (p = 0.101).
- At ≤2022 the conclusion depends on the scheme under exact matching: only `year1` passes, at both L1 and L2. Under fuzzy matching, L1 passes everywhere and L2 only under `interval`.
- At ≤2020, the year-binned L1 lifts (2.5–4.3) come from a 9-paper snapshot in which only 114 of 200 bootstrap draws are defined under the year-bin schemes. They are not evidence (§8.1).

### 3.7 Verdict per snapshot and level

| Snapshot | L0 (15) | L1 (60) | L2 (240) |
|---|---|---|---|
| ≤2026 | **No coherence**; under exact matching below both null bands under every scheme (0.818–0.889); under fuzzy matching inside or below the bands (0.912–0.998), never significant | **Robust** (exact and fuzzy, 5/5) | **Robust** (exact and fuzzy, 5/5) |
| ≤2024 | **No coherence** (exact 0.73–0.90; fuzzy 0.84–1.04, never significant) | **Robust under fuzzy only**; exact 4/5 (fails `gap`) | **Robust** (exact and fuzzy, 5/5) |
| ≤2022 | **No coherence** (exact 0.47–0.66) | **Not robust under exact** (1/5); robust under fuzzy (5/5) | **Not robust** (exact 1/5, fuzzy 1/5) |
| ≤2020 | Not evidence (9 papers, 1 stratum) | Not evidence (exact: passes only the year bins, 3/5, on 5 coupled pairs; fuzzy: year bins and `gap`, 4/5, on 4 coupled pairs) | **Not evaluable**: no co-assigned no-overlap pair (0/200 defined draws) |

Under the strict criterion (exact matching, all five schemes), three cells are robust: ≤2026 L1 and L2, and ≤2024 L2. With fuzzy matching, ≤2024 L1 and ≤2022 L1 also qualify. At ≤2024 and ≤2026, the finer levels group the concepts of citation-coupled, concept-disjoint papers more than a degree-preserving rebuild or a random relabelling does (≤2024 L1 under exact matching fails `gap`). At ≤2022 this holds only under fuzzy matching at L1 (5/5) and under exact `year1` at L1 and L2; under the primary exact scheme, ≤2022 L1 (1.06, p = 0.17 / 0.139) and L2 (0.987, below the configuration-null mean of 1.08; p = 0.76 / 0.60) do not beat the nulls. The coarsest level does not beat them anywhere. Where the evidence is clearest (≤2026, ≤2024), the lift increases with resolution.

### 3.8 Why L0 behaves differently

Under exact matching, at every snapshot and under every scheme, the L0 lift is below 1 and below the lower edge of both null bands (p = 1.0). At ≤2026 (interval) it is 0.879, against null 2.5% quantiles of 0.950 and 0.964. Conditional on the snapshot's papers, coupled concept-disjoint papers are placed in the same coarse super-node *less* often than under either null. Under fuzzy matching, L0 is never significant but not always below the bands: ≤2026 interval 0.972 lies inside both (configuration-null q2.5 0.959, random-label q2.5 0.971; p = 0.92 / 0.971), and ≤2024 `year2` and `year3` are 1.03 and 1.04 (p = 0.51 / 0.43 and 0.40 / 0.374), so there L0 is at chance rather than below it.

- **Coarse groups are very large.** At ≤2026 the 15 L0 super-nodes have a median of 264 member ids (min 56, max 854; 5798 in total). The median is 90 at L1 and 19 at L2 (`out/2026/hierarchy.json`). With so few, so large groups, we expect a_pq to vary little across pairs and the ratio Σa·c / Σa·e to be driven by a handful of groups. This is a hypothesis, not measured: neither quantity is in `metrics.json` (a per-super-node breakdown would test it, §9.2 item 3).
- **The sub-chance values are not explained by these files.** They suggest that the coarse cut divides along an axis that cuts across citation lineages. Candidates are task or dataset families rather than method lineages, or the γ = 0.5 prior holding coarse groups to their earlier shape. Neither is tested.
- **Not shown by this run.** Whether the temporal prior causes L0's loss is not measured: the only γ = 0 comparison (`out/gamma/gamma.json`) predates the verification fixes and is stale (§9.1).

A direct diagnostic would be a per-super-node breakdown of the coupled pairs, which is not in `metrics.json`. In practice, L0 is a coarse overview whose groupings the citation signal does not support; claims of semantic closeness should be made at L1–L2.

## 4. Stability (P5)

### 4.1 Definitions (as implemented in `eval/stability.py`)

The protocol is `stability.protocol`: frac = 0.1, seeds 0–4, R = 99, n_sub = 200. The parameters in `stability.params` match `out/run_config.toml`.

- **Scope.** All scores use concept nodes only; anchored nodes follow their anchor and would inflate agreement.
- **ARI** is the adjusted Rand index per level: 0 at chance, 1 for identical partitions.
- **HARI** is the level-pooled laminar analogue, Σ_k (I_k − E_k) / Σ_k (M_k − E_k), built from each level's pair-counting index, expectation and maximum. It is 1 for identical trees and has expectation 0 under one node permutation applied at every level. Each level is weighted by its pair mass, so **L0 dominates HARI** (the code docstring puts its weight at about 75% at these budgets). HARI should be read next to the per-level ARIs.
- **Perturbation.** Each seed removes 10% of the hyper-edges in every (publication period × relation) stratum and rebuilds the whole chain 2020 → 2026 with the run's parameters. Each snapshot is scored against the unperturbed run. The interval is a t-interval over the 5 seeds (df = 4).
- **Cross-snapshot.** Per transition t−1 → t, ARI and HARI are computed on the concept nodes present in both snapshots. The 95% interval is the 2.5–97.5 percentile range over 200 random half-subsamples of those nodes.
- **New-paper (attachment) null** (`tkh.null.attachment_null`). Edges up to t−1 stay real. Each clustering edge of a new paper (year in (t−1, t]) keeps its paper, year, arity and head (`members[0]`). Every tail member (`members[1:]`) that is an old node (entry year ≤ t−1) of a type with a pool is redrawn among old nodes of the same type, with probability proportional to their tail degree on clustering edges up to t−1 (nodes that never occur in a tail are never drawn; `tkh/null.py`, `attachment_null`). Non-clustering edges of new papers stay real. Snapshot t is then rebuilt from the real t−1 hierarchy with the prior. R = 99 replicates per transition; z = (obs − null mean)/null SD; p = (1 + #{null ≥ obs})/(R + 1), with floor 0.01.
- **Localisation.** A *touched* node is an old concept node that is a member of any edge of a new paper, of any relation. This is the evaluator's definition, not the method's stable set U_t (`tkh.hierarchy.stable_nodes`), which uses clustering relations only, ignores hub members and also removes nodes affected by hub churn; neither set contains the other. A node's *reassignment* is 1 − Jaccard of its co-members among old nodes before and after the transition. The ratio is the mean reassignment of touched over untouched nodes, with a CI from a 1000-draw node bootstrap stratified by touched/untouched.
- **Events** come from `out/temporal_events.json`, produced by `tkh/temporal.py` by largest-overlap matching on the **full** memberships, anchored nodes included. *Continue* = identical membership, *growth* = strict superset, *change* = any other persisting membership. A *merge* is one event per new super-node formed from several old ones; a *split* is one event per old super-node that divides. Deaths cannot occur, because snapshots only grow.

![Perturbation and cross-snapshot stability per snapshot and level](figures/stability.png)

*Figure 3 (`docs/figures/stability.png`). (a) Perturbation ARI per level and HARI, mean with t-interval. (b) Cross-snapshot ARI per level and HARI with 95% intervals, each next to its new-paper null band (R = 99).*

### 4.2 Perturbation robustness (10% edge removal, 5 seeds)

| Snapshot | ARI L0 (15) | ARI L1 (60) | ARI L2 (240) | HARI | Per-seed HARI min–max |
|---|---|---|---|---|---|
| ≤2020 | 0.53 [0.48, 0.57] | 0.71 [0.65, 0.76] | 0.90 [0.87, 0.92] | 0.58 [0.54, 0.62] | 0.558–0.628 |
| ≤2022 | 0.30 [0.25, 0.35] | 0.50 [0.45, 0.55] | 0.79 [0.77, 0.82] | 0.36 [0.32, 0.40] | 0.307–0.393 |
| ≤2024 | 0.15 [0.12, 0.18] | 0.30 [0.28, 0.33] | 0.67 [0.64, 0.69] | 0.20 [0.18, 0.23] | 0.185–0.231 |
| ≤2026 | 0.12 [0.11, 0.13] | 0.26 [0.24, 0.27] | 0.63 [0.61, 0.65] | 0.17 [0.16, 0.18] | 0.157–0.184 |

Mean over seeds with 95% t-interval (n = 5).

- **Level order.** Robustness rises from coarse to fine at every snapshot. L2 keeps ARI 0.63–0.90, while L0 falls to 0.12 at ≤2026. Because L0 dominates HARI, HARI follows it closely (0.58 → 0.17).
- **Decline over snapshots.** Robustness falls monotonically from ≤2020 to ≤2026 at every level. ≤2020 has no prior, so it measures the static algorithm alone. Later snapshots inherit the perturbed early hierarchy through the prior, so the decline is consistent with the path dependence described in formal statement §9. It is also consistent with a second explanation that this run cannot separate: later graphs are larger (3980 concept nodes at ≤2026 against 1018 at ≤2020; `run_info.snapshots.<t>.n_concept`) under the same fixed budgets. Separating the two needs a γ = 0 perturbation run on the current build.
- **Seed spread.** The per-seed HARI ranges of the four snapshots are disjoint (the closest pair is ≤2024, minimum 0.185, against ≤2026, maximum 0.184), so the decline is not seed noise.
- **Practical meaning.** A 10% edge deletion spread across the history gives a very different 15-group partition at ≤2026 (ARI 0.12). L2 is the most robust level (ARI 0.90 / 0.79 / 0.67 / 0.63 at ≤2020–≤2026), but only moderately robust at late snapshots: at ≤2026 (0.63 [0.61, 0.65]) the deletion also changes a substantial part of the finest partition. L0–L1 are not robust late (L0 0.12, L1 0.26 at ≤2026). Statements about specific coarse super-nodes at late snapshots describe one plausible partition among many.

### 4.3 Cross-snapshot persistence vs the new-paper null

| Transition | Common nodes | Score | Observed [95% half-subsample CI] | Null mean | Null 2.5–97.5% | z | p |
|---|---|---|---|---|---|---|---|
| 2020→2022 | 1018 | ARI L0 | 0.854 [0.818, 0.881] | 0.839 | 0.767–0.892 | 0.42 | 0.37 |
| | | ARI L1 | 0.872 [0.842, 0.896] | 0.859 | 0.826–0.886 | 0.72 | 0.25 |
| | | ARI L2 | 0.915 [0.890, 0.940] | 0.910 | 0.896–0.924 | 0.70 | 0.24 |
| | | HARI | 0.860 [0.830, 0.884] | 0.847 | 0.787–0.889 | 0.49 | 0.33 |
| 2022→2024 | 1464 | ARI L0 | 0.803 [0.773, 0.828] | 0.748 | 0.673–0.811 | 1.49 | 0.07 |
| | | ARI L1 | 0.794 [0.761, 0.820] | 0.774 | 0.730–0.813 | 0.94 | 0.17 |
| | | ARI L2 | 0.794 [0.761, 0.833] | 0.788 | 0.770–0.805 | 0.57 | 0.35 |
| | | HARI | 0.801 [0.773, 0.825] | 0.755 | 0.689–0.809 | 1.51 | 0.06 |
| 2024→2026 | 2829 | ARI L0 | 0.886 [0.871, 0.901] | 0.855 | 0.788–0.908 | 1.12 | 0.13 |
| | | ARI L1 | 0.897 [0.881, 0.911] | 0.880 | 0.846–0.909 | 1.05 | 0.13 |
| | | ARI L2 | 0.916 [0.897, 0.932] | 0.898 | 0.885–0.910 | 2.49 | 0.01 |
| | | HARI | 0.890 [0.875, 0.904] | 0.862 | 0.810–0.903 | 1.23 | 0.12 |

R = 99 for every row.

- **Persistence is high.** ARI is 0.79–0.92 at every level and transition, HARI 0.80–0.89. 2022→2024 is the least stable transition at all levels.
- **The null is almost as stable.** All 12 observed values lie above the null mean, by +0.005 to +0.055 *(derived from the same fields)*. Only 2024→2026 L2 leaves the null's 2.5–97.5% band (0.916 against an upper edge of 0.910; z = 2.49; p = 0.01, the floor, meaning no replicate reached the observed value). The 12 tests are not independent (HARI pools the levels, and all tests at a transition share one real tree), and no multiplicity correction is applied. A Bonferroni threshold of 0.05/12 ≈ 0.004 lies below the p floor at R = 99, so this exceedance cannot be called significant under that correction; it is suggestive at most. The consistent positive sign is not a valid sign test, for the same reason.
- **What not beating the null means.** The null keeps the real old graph, the real t−1 hierarchy and the prior, and randomises only *which* old nodes new papers attach to. Persistence is about as high when new papers attach at random, so it is not due to the real attachment pattern. It comes from what the null keeps: the real ≤t−1 graph, the real t−1 hierarchy and the γ = 0.5 prior. Which of these is responsible is not separated without a γ = 0 control on the current build (§8.2). This is consistent with the by-construction behaviour intended for P5; it is **not** evidence that the corpus' own evolution is stable.
- **Persistence is not robustness.** L0 ARI is 0.89 across 2024→2026 but 0.12 under perturbation at ≤2026. The run is consistent with its own past, not converging to a partition determined by the data.

### 4.4 Change localisation

![Reassignment of touched vs untouched old concept nodes](figures/localisation.png)

*Figure 4 (`docs/figures/localisation.png`). (a) Reassignment rate of touched vs untouched old concept nodes per transition and level. (b) Touched/untouched ratio with node-bootstrap CI; 1 means no localisation.*

| Transition | Touched / untouched (share touched) | Level | Reassignment touched | Reassignment untouched | Ratio [95% bootstrap CI] | Touched share of total reassignment |
|---|---|---|---|---|---|---|
| 2020→2022 | 40 / 978 (3.9%) | 0 | 0.463 | 0.148 | 3.1 [2.2, 4.1] | 11% |
| | | 1 | 0.597 | 0.159 | 3.8 [2.8, 4.7] | 13% |
| | | 2 | 0.684 | 0.101 | 6.8 [5.2, 8.5] | 22% |
| 2022→2024 | 87 / 1377 (5.9%) | 0 | 0.504 | 0.203 | 2.5 [2.0, 2.9] | 14% |
| | | 1 | 0.569 | 0.234 | 2.4 [2.0, 2.9] | 13% |
| | | 2 | 0.607 | 0.170 | 3.6 [3.0, 4.2] | 18% |
| 2024→2026 | 111 / 2718 (3.9%) | 0 | 0.589 | 0.138 | 4.3 [3.6, 4.9] | 15% |
| | | 1 | 0.624 | 0.118 | 5.3 [4.6, 6.1] | 18% |
| | | 2 | 0.642 | 0.092 | 7.0 [6.0, 8.0] | 22% |

Two columns are *derived*: share touched = touched/(touched + untouched); touched share of total reassignment = touched·reassign_touched / (touched·reassign_touched + untouched·reassign_untouched).

- **Per node, change is concentrated on touched nodes.** Touched nodes are reassigned 2.4–7.0 times as often as untouched ones, with every CI lower bound ≥ 2.0. L2 has the highest ratio in every transition; L0 and L1 are about equal at 2022→2024 (2.5, 2.4) and L1 is higher in the other two transitions. Localisation is therefore sharpest where groups are smallest.
- **Untouched regions are held, not frozen.** Untouched reassignment is 0.09–0.23. Touched nodes are few (3.9–5.9% of old nodes), so they account for only 11–22% of all reassignment, and **78–89% of reassignment happens on untouched nodes**. This is expected with γ = 0.5: the prior enters the merge score as s_t = (1 − γ)·s + γ·Π, biasing merges without imposing them. Untouched nodes also move because fixed budgets force regrouping as the node set grows, because their co-member sets change when touched co-members leave or groups merge, and because the evaluator's untouched set includes hub-churn nodes that the method did not treat as stable.
- **Attribution to the prior is not established.** A ratio above 1 could arise partly without any prior, because touched nodes are by definition those whose local structure changed. Attributing it to γ needs a γ = 0 control on the current build.

### 4.5 Lifecycle events

| Transition | Level | birth | continue | growth | change | merge | split | Total events |
|---|---|---|---|---|---|---|---|---|
| 2020→2022 | 0 | 0 | 3 | 6 | 3 | 1 | 1 | 14 |
| | 1 | 7 | 23 | 17 | 6 | 7 | 0 | 60 |
| | 2 | 32 | 144 | 28 | 6 | 24 | 3 | 237 |
| 2022→2024 | 0 | 0 | 1 | 5 | 9 | 0 | 0 | 15 |
| | 1 | 2 | 11 | 21 | 11 | 6 | 4 | 55 |
| | 2 | 27 | 104 | 70 | 21 | 18 | 0 | 240 |
| 2024→2026 | 0 | 0 | 1 | 2 | 9 | 1 | 1 | 14 |
| | 1 | 1 | 8 | 21 | 23 | 3 | 2 | 58 |
| | 2 | 11 | 118 | 52 | 39 | 14 | 3 | 237 |

A missing key is shown as 0. Totals count events, not super-nodes (a merge or split is one event involving several super-nodes).

- **L2 is mostly persistent.** Continue plus growth covers 172/237 (73%), 174/240 (72%) and 170/237 (72%) of events. Births fall from 32 to 27 to 11, and splits are rare (≤ 3).
- **The coarse levels reshuffle more over time.** At L0, continue plus growth falls from 9/14 to 6/15 to 3/14, and *change* rises from 3 to 9 to 9. At L1, change rises from 6 to 11 to 23, and continue plus growth falls from 40/60 to 32/55 to 29/58. Because memberships include anchored nodes and snapshots only add nodes, *continue* requires that no new node joined, which is rare for large L0 groups; *growth* is the normal persisting outcome.
- **Event labels are bookkeeping, not effect sizes.** The matcher is the simplest consistent largest-overlap matcher, and *change* covers any membership that is neither equal nor a superset, however small the loss. Effect size is what ARI and reassignment measure.

## 5. Label faithfulness (P6)

The question is whether the L0 and L1 labels assert things about their super-nodes that evidence the labeller never saw can confirm. Values come from `out/metrics.json → faithfulness` and `out/faithfulness_judgements.json` (`eval/faithfulness.py`, `make faithfulness`).

### 5.1 Protocol

| Component | What the code does |
|---|---|
| Labeller | `qwen2.5:7b-instruct`, prompt `configs/prompts/labeller.txt`. Writes a label of at most 6 words and a one-sentence gloss of at most 30 words, using only the **seen** half of the super-node's evidence. It also sees a contrast list: the 10 same-level groups sharing the most clustering edges with this one, each shown as up to 4 concept names from that neighbour's seen half. The prompt forbids years, outside knowledge and names not in the evidence. |
| Evidence and split | Evidence lines are member concepts (`name [type]`, with aliases), facts from clustering edges with at least one tail member in the group (with `evaluated_on` results), claims, future-work topics and paper titles, all within the snapshot; cited works and authors are excluded. `split_evidence` makes a 50/50 split, seeded by the sorted member ids and stratified by kind; each half is capped at 40 lines. Node lines are ranked by the number of snapshot papers that mention the node, fact lines by the number of group members the edge holds. The seen and held-out lists are stored in `out/<t>/label_inputs.json`. |
| Judge | `phi4`, a different model family. (1) **Decompose** (`claims_split.txt`): exactly 3 claims "The group contains …". A claim is kept only if ≥ 80% of its content words come from the label and gloss and it keeps at least one non-generic word (`_content_ok`); if none survive, the claims fall back to `[label, gloss]`. (2) **Entail** (`claim_entail.txt`): the numbered **held-out** lines, answer `{"line", "verdict"}`. A claim is *supported* only if the verdict is "supported" **and** the cited line exists. A fact whose head method lies outside the group is shown to the judge with "…, which is NOT in this group" (`Evidence.judge_view`). |
| Over-claim | Share of judged labels with at least one unsupported claim; bootstrap 95% CI over labels (B = 2000). `claim_unsupported` is the pooled share of unsupported claims. Both overall and by cutoff, level and cutoff × level. |
| Deterministic checks | No LLM. On label + gloss: (a) a year after the cutoff; (b) `named_non_member`: a proper-name-like method or dataset name (≥ 2 capitals, or letters plus digits, whole-word) whose nodes are all outside the group; (c) `future_entity`: such a name whose nodes all enter after the cutoff. |

The design assumes that a label written from half of a coherent group's evidence should carry over to the other half. The judge is not validated here (no known-answer controls), and there is no chance baseline (no null trees); §8.3. All LLM answers are served from `data/llm_cache.json`, so the run replays offline.

![Label faithfulness: over-claim by cutoff and level](figures/faithfulness.png)

*Figure 5 (`docs/figures/faithfulness.png`). (a) Over-claim with 95% CI by cutoff and level. (b) Overall and per level.*

### 5.2 Over-claim

| Metric | Value |
|---|---|
| Over-claim (labels with ≥ 1 unsupported claim) | **0.58 [0.52, 0.64]**, n = 296 |
| Claim-level unsupported rate | 0.45 (757 claims) |
| `decomposition_ok` | 0.61 |
| `quote_rejected` | 9 label claims |
| `no_held_out` | 4 labels not judged (2020 L1.31, L1.33; 2022 L1.31, L1.33) |

**Decomposition and the quote check.** For 39% of the 300 labels (1 − `faithfulness.decomposition_ok`; the 4 labels without held-out evidence included), at least one decomposed claim was dropped by `_content_ok` (the 80% content-word reuse test or the non-generic-word test), or decomposition returned no claims; those labels were judged on the surviving claims, or on `[label, gloss]` (17 labels have 1 claim and 97 have 2; *derived*). Decomposition can drop part of a label: 2024:L1.33 "E(3)-equivariant GNNs" was judged only on "contains models for phase-space integration". The cited-line check overturns few verdicts (9 of 757 label claims).

### 5.3 Deterministic checks

Names behind the flags were listed by running `eval.faithfulness.NameChecker` offline on the stored labels (deterministic, no LLM).

| Check | Labels flagged (of 300) | Meaning in this run |
|---|---|---|
| `year_after_cutoff` | 0 | No label mentions a year after its snapshot. |
| `named_non_member` | 33 | 36 name hits: "DFT" 22, "GNN" 6, "DeePMD" 3, "Deep Potential MD" 2, "DFT+U" 2, "EquiformerV2" 1. Most are generic acronyms that happen to be method-node surface forms, so the count overstates real naming of non-members. |
| `future_entity` | 4 | "Deep Potential MD" in two 2020 labels (its only node enters in 2021) and "GNN" in two 2024 labels (node enters in 2025). Surface-form collisions, not leaked future items; labels use export-wide names (assumption A4 in the formal statement). |

### 5.4 Breakdowns

From `faithfulness.by_cutoff`, `by_level` and `by_cutoff_level`.

| Cutoff | Judged | Over-claim [95% CI] | Claim-unsupported |
|---|---|---|---|
| 2020 | 73 | 0.62 [0.51, 0.73] | 0.51 |
| 2022 | 73 | 0.62 [0.51, 0.73] | 0.47 |
| 2024 | 75 | 0.60 [0.49, 0.71] | 0.47 |
| 2026 | 75 | 0.49 [0.39, 0.60] | 0.37 |

| Level | Judged | Over-claim [95% CI] | Claim-unsupported |
|---|---|---|---|
| L0 | 60 | 0.37 [0.25, 0.48] | 0.27 |
| L1 | 236 | 0.64 [0.57, 0.69] | 0.50 |

| Cutoff | L0 over-claim [95% CI] (n) | L1 over-claim [95% CI] (n) |
|---|---|---|
| 2020 | 0.40 [0.20, 0.67] (15) | 0.67 [0.55, 0.79] (58) |
| 2022 | 0.33 [0.13, 0.60] (15) | 0.69 [0.55, 0.79] (58) |
| 2024 | 0.47 [0.20, 0.73] (15) | 0.63 [0.52, 0.75] (60) |
| 2026 | 0.27 [0.07, 0.53] (15) | 0.55 [0.42, 0.67] (60) |

**By held-out evidence size** *(derived from `out/faithfulness_judgements.json`; line counts from `out/<t>/label_inputs.json`)*:

| Held-out lines | Labels | Over-claim | Claim-unsupported |
|---|---|---|---|
| 1–5 | 40 | 0.90 | 0.81 |
| 6–10 | 29 | 0.86 | 0.61 |
| 11–20 | 52 | 0.63 | 0.52 |
| 21–39 | 75 | 0.49 | 0.34 |
| 40 (cap) | 100 | 0.41 | 0.30 |

Over-claim falls steeply with the number of held-out lines (0.90 for 1–5 lines, n = 40, to 0.41 at the 40-line cap, n = 100). This gradient is confounded with level and cutoff (41 of the 60 L0 groups sit at the cap, against 59 of the 240 L1 groups; *derived*), and no analysis here adjusts for them. In a small group the defining member often lands in the seen half, and the held-out half cannot support the label: 2020:L1.47 "GAP for silicon" has 5 held-out lines, none mentioning silicon or GAP, while the seen half has one; 2020:L1.42 "Fracture prediction models" has 2 held-out lines. L0 and 2026 groups have larger evidence pools, so their lower over-claim may partly reflect evidence size; this run does not separate evidence size from level or cutoff.

**Examples** (claim, verdict, cited held-out line):
- *Supported*: 2020:L1.5 "SchNet-based models", claim "contains models using SchNet for molecular property prediction", line "SchNet uses component Continuous-filter convolution (cfconv) layer, …".
- *Supported*: 2022:L1.20 "Diffusion Modeling Techniques", claim "…predicting ionic diffusion coefficients in solid electrolytes", line "DeePMD training protocol for diffusion coefficient computation is evaluated on Li10GeP2S12, …".
- *Unsupported, evidence missing*: 2024:L1.6 "Gaussian Approximation Potentials", claim "contains Gaussian Approximation Potentials"; the 4 held-out lines (elastic-constant and slab components) contain neither "Gaussian" nor "GAP".
- *Unsupported, probably a judge miss*: 2024:L0.5 "Graph Neural Networks", claim "contains graph neural networks"; the held-out half includes "Phonax (E(3)-equivariant graph neural network framework …)".

## 6. Extrinsic utility: retrieval (T6)

The brief's extrinsic test: an agent that starts at the coarsest level and drills down to the target nodes, compared
with a flat baseline and scored on hit-rate and steps-to-target. Design, data study and rationale:
`notebooks/04_retrieval_design.ipynb`.

### 6.1 Task and protocol

- **Questions.** The 18 questions of `data/questions.csv`: 14 type A (specific search; the answer is methods and
  citations) and 4 type B (synthesis; the answer is claims and citations). The question type is given as metadata.
  The ground truth, `data/ground_truth.json`, is read only by the evaluator.
- **Snapshot.** The latest cutoff not after the stated year; no date → the latest cutoff. All 18 questions are
  answered from ≤2026. The agent's snapshot equals the one the evaluator derives independently (the GT `as_of` for
  type B, the year written in the question for type A) for every question.
- **Agent** (`tkh/retrieve.py`).
  - Node text comes from the snapshot's own edges only.
  - Scoring is keyword overlap: the share of the question's keywords a text contains.
  - Super-nodes score 0.5 · s(label + gloss) + 0.5 · s(member centroid) at L0–L1, and s(member centroid) at L2.
  - A beam keeps 10 / 20 / 40 super-nodes at
    L0 / L1 / L2, and the answer has k = 10 items.
  - The **flat baseline** ranks every leaf with the same scorer and texts.
- **Gold resolution** (`eval/retrieval.py`).
  - GT method names match nodes by exact name/alias or acronym.
  - Citations match by author set and year (±1).
  - Type-B sources match by DOI, then title.
  - A method claim is attainable when the graph holds a claim from the method's evidence article on the method.
  - Unattainable items are excluded from hit-rates and reported as ceilings.
- **Metrics.**
  - M1 hit-rate @k over attainable items.
  - M2 error rate: the share of answers that are listed `wrong_domain` / `outdated_as_main` methods.
  - M3 steps-to-target: one step = one node inspected, so the drill-down pays for every super-node it scores.
    There is one target per attainable GT item, a miss is censored at N + 1, and steps are summarised by medians.
  - Differences are paired per question (mean; steps: median). There are no CIs (§8.4).

### 6.2 Ceilings

| Item | Attainable / total |
|---|---|
| A methods | 45 / 63 (0.71) |
| A method claims | 54 / 188 (0.29) |
| A citations | 65 / 71 (0.92) |
| B claims | 32 / 36 (0.89) |
| B citations | 14 / 19 (0.74) |

Q5 and Q11 have no attainable method, so methods, steps and reach are over 12 type-A and 4 type-B questions. The
other metrics have their own n (table below): citations over 14 type-A questions, method claims over the 9 with an
attainable method claim, and M2 over the 12 whose GT lists `wrong_domain` / `outdated_as_main` methods (all but Q13
and Q14).

### 6.3 Results (drill-down vs flat)

| Type | Metric | n | Drill-down | Flat | Paired difference |
|---|---|---|---|---|---|
| A | M1 methods | 12 | 0.275 | 0.295 | -0.020 |
| A | M1 method claims | 9 | 0.250 | 0.306 | -0.056 |
| A | M1 citations | 14 | 0.657 | 0.578 | +0.079 |
| A | M2 error rate | 12 | 0.042 | 0.033 | +0.008 |
| A | reach (share of questions) | 12 | 0.833 | 1.000 | -0.167 |
| A | M3 steps to first item (median) | 12 | 206.5 | 10.5 | +150.0 |
| A | M3 steps to 50% of items (median) | 12 | 413.0 | 28.5 | +359.0 |
| B | M1 claims | 4 | 0.740 | 0.543 | +0.196 |
| B | M1 citations | 4 | 0.438 | 0.375 | +0.062 |
| B | reach (share of questions) | 4 | 1.000 | 1.000 | +0.000 |
| B | M3 steps to first item (median) | 4 | 143.0 | 2.0 | +140.5 |
| B | M3 steps to 50% of items (median) | 4 | 152.5 | 6.5 | +146.0 |

**Diagnostics** (`retrieval.diagnostics`):
- Kept / frontier is 0.67 at L0, 0.47 at L1 and 0.46 at L2. The drill-down scores 133–162 super-nodes per question
  before its first leaf.
- The drill-down never reaches Q4 and Q10. In both, the targets lie inside one L0 super-node that the beam keeps;
  they are lost at L1.
- Flat search needs more than 1,000 ranks on Q7 (1266) and Q10 (1252). The drill-down needs 354 steps on Q7 and
  misses Q10 (censored at 2525).
- On average, both systems cite about as many articles per answer (A 13.0 vs 13.2 over the 12 type-A questions with
  step items, B 4.0 vs 4.0), so the mean citation difference is not explained by average breadth. Breadth is not
  controlled per question (Q4: 20 vs 10 articles; §9.2 item 4).

### 6.4 Reading

- **Accuracy is mixed.** The drill-down is higher on type-A citations and on type-B claims and citations, and
  slightly lower on type-A methods and method claims. It reaches an item on 10 of 12 type-A and 4 of 4 type-B
  questions; flat search reaches all 16.
- **Cost favours flat search.** Its median rank to the first item is 10.5 (A) and 2 (B); the drill-down's routing
  overhead alone is 133–162 steps. The only exception is Q7 (354 vs 1266 steps); on Q10 flat search needs 1252 ranks
  and the drill-down misses.
- **The misses are routing errors at L1,** not dispersion: the right L0 node is kept, the right L1 node is not.
- On this corpus the hierarchy acts as a filter that can sharpen the answer list, not as a shortcut to the first
  target. The settings were chosen with these questions in view, and there are no CIs or nulls, so this is
  descriptive evidence on 18 questions (§8.4).

## 7. Overall assessment against the brief

Statuses follow the formal statement's §6 property table, updated with this run's evidence. Properties not tested by this run are marked as such.

| Property (brief §2) | Status | Evidence in this run |
|---|---|---|
| P1 laminar refinement | By construction | Re-checked read-only on `out/<t>/hierarchy.json`: at all 4 snapshots every member id lies in exactly one super-node per level, all levels cover the same ids (1475, 2144, 4094, 5798), and every child's members are a subset of its parent's. Whether `validate.py` ran in the 2026-10-28 run is not recorded (it writes no output). |
| P2 size budget | By construction | `run_info.snapshots.<t>.levels[k].super_nodes` = 15 / 60 / 240 at every snapshot; no empty super-node; max sizes within the ρ-cap (§2.1). |
| P3 semantic coherence | Empirical, partly supported | Robust at L1–L2 for ≤2026 and at L2 for ≤2024 (also L1 under fuzzy matching); not at L0 anywhere; ≤2022 fragile; ≤2020 not evidence (§3.7). The proxy is citation coupling on few pairs, and the evidence is conditional on the corpus. The structure–semantics trade-off itself (α) was not re-evaluated in this run. |
| P4 hyper-edge fidelity | By construction; not tested here | No evaluation in this run speaks to it. |
| P5 temporal stability | By construction (prior, persistent ids, event log); size of effect empirical | Persistence high (HARI 0.80–0.89) but at the level of a null that shares the mechanism; per node, change concentrated on touched nodes (ratio 2.4–7.0), although 78–89% of total reassignment falls on untouched nodes; identity log with birth / continue / growth / change / merge / split; deaths impossible by construction. Attribution to the prior is untested (no γ = 0 control). Robustness to perturbation is low at coarse late levels. |
| P6 interpretable, faithful labels | Empirical, not satisfied | Labels exist for every L0–L1 super-node, but 0.58 of judged labels assert at least one claim the held-out evidence does not support (0.64 on cells never used in development). The judge is not validated and there is no null baseline. Temporal honesty: no post-cutoff years and no real future-entity leaks found. L2 labels were not evaluated. |
| Extrinsic utility (brief T6) | Empirical, mixed | Drill-down vs flat search on 18 questions (§6). Hit-rates are mixed: higher on citations and type-B claims, slightly lower on type-A methods. The step cost is far higher (median 206.5 vs 10.5 to the first item, A), and 2 questions are missed at L1. Descriptive only: no CIs, no nulls, settings chosen with these questions in view. |
| Variant comparison (brief T6) | Not done on the current build | The brief asks to compare method variants and say which to ship. The only γ and parameter comparisons are the stale `out/gamma/` and `out/sweep.json` (§9.1). |
| Label circularity (brief T6) | Controlled by design, partly | The judge checks claims against the held-out half of a seeded 50/50 evidence split (`tkh/label.py`, `split_evidence`) that the labeller never sees. The held-out half uses the same kinds of text as the seen half, including concept surface forms that also drive clustering, so the split controls for the labeller's input, not for shared vocabulary. |

In short: P1, P2 and the structural parts of P5 hold by construction; P3 is supported at the finer levels only; P5's localisation is observed but its cause is not isolated; P6's faithfulness target ("nothing the members do not support") is not met by the current labeller, as measured by this judge. In the extrinsic test, the hierarchy acts as a filter that can sharpen a retrieval answer, not as a shortcut to the first target. The variant comparison is not part of this run.

## 8. Limitations and threats to validity

### 8.1 Coherence
- **Few coupled pairs.** Lifts rest on 5, 11, 21 and 58 coupled no-overlap pairs (exact) at ≤2020–≤2026. The ≤2022 and ≤2024 verdicts can turn on a few pairs, which explains their sensitivity to scheme and matching.
- **Wide bootstrap CIs against tight null bands.** The null tests are conditional on the snapshot's papers (fixed ruler, varying partition), with narrow bands (about ±0.05–0.15 at ≤2026). The paper bootstrap asks how the lift would vary over other paper samples; its CI includes 1 in **every** cell. The evidence is "better than chance for this corpus", not a population estimate.
- **≤2020 is not evaluable.** 9 citing papers, 18 no-overlap pairs, 1 interval stratum; L2 lift undefined; 165 and 129 of 200 draws defined at L0–L1 (114 under the year-bin schemes at L1). Its year-bin passes are small-sample artefacts.
- **Floored p-values.** p = 0.01 (R = 99) and 0.001 (R = 999) mean no null draw reached the observed lift. The 5% threshold is a convention shared with formal statement §8.
- **No multiplicity correction across cells or matchings.** The all-schemes rule is an intersection test within a cell, so it needs no within-cell correction. Across the 9 cells at ≤2022–≤2026, a Bonferroni threshold of 0.05/9 ≈ 0.0056 lies below the configuration-null p floor of 0.01 at R = 99 (`coherence.R`), so no cell could pass such a correction against that null at this R; per-cell significance against the configuration null is uncorrected.
- **Name-based residual filter.** Leakage through paraphrased or unnormalised names is not excluded; the stricter fuzzy filter strengthens rather than weakens the L1–L2 result.
- **Coupling is a proxy.** Papers can cite the same works for unrelated reasons (a shared benchmark or survey), and related work in a sparse citation network may share no citations.

### 8.2 Stability
- **No γ = 0 control on the current build.** That the prior produces persistence and localisation, and that it costs perturbation robustness, is argued by design, not measured on this run. The perturbation decline over snapshots is confounded with graph growth under fixed budgets.
- **Weak null evidence.** p floor 0.01 at R = 99; 12 dependent, uncorrected tests; the null shares the prior and the real t−1 hierarchy, so it tests only the attachment pattern.
- **Interval semantics.** Cross-snapshot intervals come from half-subsamples of nodes on fixed trees (node sampling only, and wider than full-size resampling). Perturbation intervals are t-intervals with n = 5. Localisation CIs treat nodes as independent, although co-members are not.
- **HARI is dominated by L0.**
- **Definitions differ from the method's.** The evaluator's touched set (any relation, hubs included, hub-churn removals not excluded) is not U_t, so the localisation ratio is not a direct check of U_t. Events use full memberships (anchored and new nodes); ARI and reassignment use common concept nodes.

### 8.3 Labels
- **The judge is not validated.** One judge (phi4) and one labeller; no known-answer controls, no human or second-judge agreement. Judge error is unmeasured, and the examples (§5.4) show it is lenient in some cases and strict in others.
- **No chance baseline.** No null trees (configuration-null rebuilds or random labels) are judged, so the over-claim rate is not compared with that of incoherent groups.
- **The held-out half is one sample.** Capped at 40 lines and split by one seed, so "unsupported" often means "not in this half". The strong size gradient (§5.4) shows the metric partly measures evidence size. No repeated split.
- **Selection.** Prompts were tuned on cells that overlap this run (2026 L0/L1, 2022 L0, 2024 L0); the never-tuned cells (2020 L0–L1, 2022 L1, 2024 L1) have over-claim 0.64 [0.58, 0.71], n = 191 *(derived)*.
- **Decomposition.** The content-word filter changes what is judged for 39% of labels and can drop label content.
- **Nondeterminism.** Controlled by the response cache: results replay exactly, but they are one sample of each model's output. A prompt edit invalidates the cache and gives different labels and verdicts.
- **L2 labels are not evaluated** (only levels 0–1 are labelled).

### 8.4 Retrieval
- **Few questions, one snapshot.** n = 18 (12 + 4 with attainable targets), all answered from ≤2026; retrieval on earlier snapshots is untested beyond the ≤2020 leaf-text check in `notebooks/04_retrieval_design.ipynb` §6.
- **No CIs and no nulls.** Differences are paired point estimates; no random-tree null or label ablation was run, so the result is not shown to beat chance.
- **In-sample settings.** Scorer, beam and node content were chosen with these questions in view; the levels are optimistic.
- **Matching.** Claims are matched by source article, not by content; method claims are scored per method; method names match on exact name or acronym only (versioned names such as "Orb" → "Orb-v2" are unattainable); author order is missing from the export.
- **Lexical scorer.** Keyword overlap is weak on paraphrase and partly shares the names used for clustering.

### 8.5 General
- **One corpus, one configuration.** All results are for the shipped parameters on this export; no parameter sensitivity is reported here (the sweep is stale, §9.1).

## 9. Stale or excluded outputs, and open items

### 9.1 Excluded from this report
- **`out/gamma/` (including `gamma.json`) and `out/sweep.json`.** Produced before the verification fixes; not used. They contain the only γ = 0 comparison and parameter sweep in the repo.
- **`out/label_dev/*.json` and `AI_USAGE.md` entry 30.** Quick development runs of the judge and labeller, made with the earlier label check; not used.

### 9.2 Open items
1. Run a γ = 0 control (perturbation, cross-snapshot and localisation) on the current build, and re-run `make gamma` / `make sweep` if those analyses are to be reported.
2. Labels: validate the judge (known-answer controls, a second judge or human agreement on topical claims), add a chance baseline (null trees), and repeat the evidence split.
3. Coherence: add a per-super-node breakdown of coupled pairs to diagnose L0.
4. Retrieval: paired bootstrap CIs, a random-tree null and a label ablation; held-out validation of the settings; a content judge for claims; a per-question citation-breadth control; questions on earlier snapshots (`notebooks/04_retrieval_design.ipynb` §9).

## Appendix A. Metric definitions

| Metric | Definition |
|---|---|
| Coupling c_pq | IDF-weighted Salton cosine of two citing papers' cited-work sets, after the residual name filter |
| Co-assignment a_pq | Σ_S n_S(p) n_S(q) / (n_p n_q) over the super-nodes S of a level, concept nodes only |
| Lift | Σ a·c / Σ a·e over no-overlap pairs; e = mean coupling (unadjusted) or mean coupling in the same period stratum (adjusted); 1 = chance |
| Null p | One-sided (1 + #null ≥ obs)/(R + 1); floors 0.01 (R = 99) and 0.001 (R = 999) |
| Robust (coherence) | p ≤ 0.05 against both nulls under all five period-adjusted schemes |
| ARI | Adjusted Rand index per level on concept nodes |
| HARI | Σ_k (I_k − E_k) / Σ_k (M_k − E_k) over levels; pair-mass weighted, dominated by L0 |
| Reassignment | 1 − Jaccard of a node's old co-members before and after a transition |
| Localisation ratio | Mean reassignment of touched / untouched old concept nodes |
| Over-claim | Share of judged labels with ≥ 1 unsupported claim against held-out evidence |
| Claim-unsupported | Pooled share of unsupported claims |
| Hit-rate (M1) | Share of a question's attainable GT items (methods, method claims, claims, citations) found in the k = 10 answer |
| Error rate (M2) | Share of the k answers that resolve to a `wrong_domain` or `outdated_as_main` name |
| Steps-to-target (M3) | Nodes inspected until the first (or 50% of the) GT items: super-nodes scored + rank in the pool (drill-down), rank among all leaves (flat); a miss is censored at N + 1; medians |
| Reach | Share of questions on which a system finds at least one GT item |

## Appendix B. Result paths

All paths are in `out/metrics.json` unless stated otherwise. `<t>` is a cutoff (2020, 2022, 2024, 2026), `<tr>` a transition (`2020-2022`, `2022-2024`, `2024-2026`), `[k]` a level index (0–2).

| Result | Path |
|---|---|
| Run parameters | `out/run_config.toml`; `out/run_info.json → params, cid, budgets, cutoffs, runtime_s` |
| Snapshot sizes, caps, stable set | `out/run_info.json → snapshots.<t>.{n_concept, n_edges, n_anchored, n_stable, hubs, levels[k].{super_nodes, cap, max_size}}` |
| Laminarity, sizes, labels | `out/<t>/hierarchy.json → supernodes[].{id, level, parent_id, member_ids, label, gloss}` |
| Coherence parameters | `coherence.{params, budgets, primary, periods, R, R_labels, p}` |
| Coherence coverage | `coherence.snapshots.<t>.coverage.<exact\|fuzzy>.{citing_papers, no_overlap_pairs, coupled_no_overlap_pairs, period_strata, filtered_citations}` |
| Coherence lifts and nulls | `coherence.snapshots.<t>.levels[k].<exact\|fuzzy>.<unadjusted\|interval\|year1\|year2\|year3\|gap>.{lift, ci95, bootstrap_defined, configuration_null.{mean, q2.5, q97.5, p}, random_labels.{mean, q2.5, q97.5, p}}` |
| Stability parameters | `stability.{params, budgets, protocol}` |
| Perturbation | `stability.perturbation.<t>.{ari[k].{mean, lo, hi, n}, hari.{mean, lo, hi}, per_seed_hari}` |
| Cross-snapshot | `stability.cross_snapshot.<tr>.{common_nodes, ari[k], hari}.{value, ci95, new_paper_null.{R, mean, q2.5, q97.5, z, p}}` |
| Localisation | `stability.localisation.<tr>[k].{touched, untouched, reassign_touched, reassign_untouched, ratio, ratio_ci95}` |
| Events | `stability.events.<tr>.<k>.<type>`; source `out/temporal_events.json` |
| Label faithfulness | `faithfulness.{protocol.{cutoffs, levels, max_claims}, labeller_model, judge_model, labels, judged, over_claim.{value, ci95, n}, claim_unsupported, decomposition_ok, quote_rejected, no_held_out, deterministic}` |
| Label breakdowns | `faithfulness.{by_cutoff.<t>, by_level.L<k>, by_cutoff_level.<t>:L<k>}.{over_claim, claim_unsupported}` |
| Per-judgement records (derived breakdowns) | `out/faithfulness_judgements.json` (757 records: `supernode` `<t>:L<k>.<i>`, `cutoff`, `level`, `claim`, `verdict`, `line`, `quote_ok`, `supported`) |
| Label evidence (held-out line counts) | `out/<t>/label_inputs.json` |
| Development logs (context only) | `out/label_dev/*.json`; `AI_USAGE.md` entry 30 |
| Retrieval summary | `retrieval.summary.<A\|B>.<metric>.{n, stat, hier, flat, hier_minus_flat}`; `retrieval.summary.<A\|B>.ceilings` |
| Retrieval per question and diagnostics | `retrieval.per_question.<qid>.{snapshot, ceiling, hier, flat}`; `retrieval.diagnostics`; `retrieval.config` |
| Retrieval answers and resolved gold | `out/retrieval_answers.json → <qid>.{hier, flat, gold}` |
| Figures | `docs/figures/{coherence_lift, coherence_period_sensitivity, stability, localisation, faithfulness}.png`, produced by `eval/figures.py` (`make figures`) |
