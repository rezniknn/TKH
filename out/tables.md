## data

| snapshot (cumulative) | ≤2020 | ≤2022 | ≤2024 | ≤2026 |
|---|---|---|---|---|
| papers | 16 | 22 | 38 | 52 |
| nodes (all types) | 1475 | 2144 | 4094 | 5798 |
| concept nodes (clustered) | 1018 | 1464 | 2829 | 3980 |
| hyper-edges (all relations) | 374 | 554 | 983 | 1429 |
| clustering edges (concept relations, hubs removed) | 141 | 230 | 406 | 554 |
| clustering edges per paper | 8.8 | 10.5 | 10.7 | 10.7 |
| max clustering-edge arity | 43 | 42 | 48 | 48 |
| hubs removed (> 20% of papers) | 5 | 8 | 7 | 6 |
| concept nodes in ≤ 1 clustering edge | 0.91 | 0.89 | 0.89 | 0.88 |
| node pairs sharing no clustering edge | 0.980 | 0.987 | 0.992 | 0.994 |
| papers with citations (E1a ruler) | 9 | 14 | 25 | 37 |

Ground-truth questions usable for E1b/E4 (≥ 1 expected method matches a node): 12 of 14.

## selection

| α | E1a lift (half A) | SE | level-0 giant share | eligible | within 1 SE |  |
|---|---|---|---|---|---|---|
| 0 | 0.99 | 0.51 | 0.13 | yes | yes |  |
| 0.25 | 1.50 | 0.98 | 0.12 | yes | yes |  |
| 0.5 | 1.41 | 0.62 | 0.13 | yes | yes | **selected** |
| 0.75 | 1.25 | 0.25 | 0.13 | yes | yes |  |
| 1 | 1.08 | 0.06 | 0.13 | yes | yes |  |

Same winner under 50 other cited-work splits: 0.56.

## e1

| variant (E1a lift, ≤2026, split B, pooled) | level 0 (15) | level 1 (60) | level 2 (240) |
|---|---|---|---|
| **SHAC-T (selected, α=0.5)** | 0.98 [0.77, 1.25] | 0.99 [0.74, 1.32] | 1.24 [0.80, 1.92] |
| struct-null | 1.02 [1.00, 1.05] | 1.06 [1.03, 1.11] | 1.20 [1.15, 1.24] |
| sem-null | 1.01 [0.89, 1.12] | 1.08 [0.95, 1.23] | 1.17 [0.82, 1.39] |
| full-null | 1.01 [0.99, 1.05] | 1.04 [1.01, 1.08] | 1.17 [1.11, 1.22] |
| random-labels | 1.01 [0.98, 1.04] | 1.05 [1.02, 1.09] | 1.19 [1.13, 1.24] |

## e1_strata

| level 1, ≤2026, split B | overlap pairs | no-overlap pairs | pooled | unstratified |
|---|---|---|---|---|
| **SHAC-T (selected, α=0.5)** | 0.98 [0.68, 1.42] | 0.99 [0.54, 1.81] | 0.99 [0.74, 1.32] | 1.09 [0.84, 1.41] |
| full-null | 1.02 [0.99, 1.05] | 1.09 [1.05, 1.16] | 1.04 [1.01, 1.08] | 1.06 [1.02, 1.12] |

Paper pairs: 253 with a shared non-hub concept, 342 without.

## e1_strict

| E1a lift, ≤2026, level 1, split B, pooled | pre-registered filter (exact name) | strict filter (substring), sensitivity |
|---|---|---|
| **SHAC-T (selected, α=0.5)** | 0.99 [0.74, 1.32] | 0.94 [0.69, 1.28] |
| full-null | 1.04 [1.01, 1.08] | 1.07 [1.02, 1.11] |
| random-labels | 1.05 [1.02, 1.09] | 1.08 [1.04, 1.12] |

Citation incidences removed by the residual filter at ≤2026 (counted before the A/B split): 260 (exact); 342 (strict).

## configs

| configuration (≤2026, level 1) | E1a lift (B) | perturbation ARI | cross-snapshot ARI 2024→26 | change localisation | E4 median cost | E4 recall@200 | level-0 giant share |
|---|---|---|---|---|---|---|---|
| **SHAC-T (selected, α=0.5)** | 0.99 [0.74, 1.32] | 0.26 [0.23, 0.29] | 0.96 | 1.54 | 1043 [178, 2493] | 0.01 | 0.13 |
| α = 0 | 0.90 [0.52, 1.57] | 0.35 [0.31, 0.39] | 0.85 | 1.52 | 398 [71, 1445] | 0.27 | 0.13 |
| α = 0.25 | 1.11 [0.69, 1.78] | 0.26 [0.22, 0.29] | 0.96 | 2.27 | 703 [282, 2711] | 0.13 | 0.12 |
| α = 0.75 | 1.17 [0.89, 1.54] | 0.24 [0.21, 0.27] | 0.94 | 0.94 | 1497 [130, 3207] | 0.03 | 0.13 |
| α = 1 | 1.12 [0.92, 1.36] | 1.00 [1.00, 1.00] | 0.98 | 0.79 | 2287 [329, 2549] | 0.02 | 0.13 |
| ablation: gamma0 | 1.41 [0.92, 2.16] | 0.37 [0.30, 0.44] | 0.37 | 1.08 | 859 [342, 2310] | 0.03 | 0.13 |
| ablation: rho_inf | 1.14 [0.92, 1.42] | 0.18 [0.08, 0.28] | 1.00 | – | 447 [308, 1491] | 0.08 | 0.93 |
| ablation: projection | 1.75 [1.15, 2.65] | 0.26 [0.24, 0.29] | 0.93 | 1.07 | 1471 [222, 2910] | 0.02 | 0.13 |
| ablation: freeze | 1.22 [0.61, 2.45] | 0.35 [0.25, 0.44] | 1.00 | – | 240 [181, 1164] | 0.09 | 0.22 |
| full-null | 1.04 [1.01, 1.08] | 0.19 [0.16, 0.22] | 0.89 | 1.25 | 1331 [883, 1816] | 0.02 | – |
| struct-null | 1.06 [1.03, 1.11] | 0.20 [0.16, 0.23] | 0.90 | 1.19 | 1758 [903, 2285] | 0.01 | – |
| sem-null | 1.08 [0.95, 1.23] | 0.20 [0.18, 0.23] | 0.89 | 1.26 | 795 [399, 1442] | 0.09 | – |

α = 1 ignores edges, so its perturbation ARI is 1 by construction (not a stability result). Change localisation is undefined (–) when no untouched old node is reassigned.

## e2_levels

| variant (≤2026) | pert. ARI L0 | pert. ARI L1 | pert. ARI L2 | 2024→26 ARI L0 | L1 | L2 |
|---|---|---|---|---|---|---|
| **SHAC-T (selected, α=0.5)** | 0.12 [0.10, 0.14] | 0.26 [0.23, 0.29] | 0.58 [0.53, 0.63] | 0.98 | 0.96 | 0.96 |
| ablation: gamma0 | 0.21 [0.18, 0.24] | 0.37 [0.30, 0.44] | 0.64 [0.57, 0.72] | 0.19 | 0.37 | 0.57 |
| ablation: freeze | 0.18 [0.15, 0.21] | 0.35 [0.25, 0.44] | 0.47 [0.37, 0.58] | 1.00 | 1.00 | 1.00 |
| full-null | 0.10 [0.09, 0.11] | 0.19 [0.16, 0.22] | 0.49 [0.44, 0.54] | 0.87 | 0.89 | 0.94 |

## e2_localisation

| variant | 20→22 L0 | 20→22 L1 | 20→22 L2 | 22→24 L0 | 22→24 L1 | 22→24 L2 | 24→26 L0 | 24→26 L1 | 24→26 L2 |
|---|---|---|---|---|---|---|---|---|---|
| **SHAC-T (selected, α=0.5)** | 1.62 | 1.36 | 2.22 | 1.27 | 1.49 | 1.23 | 0.59 | 1.54 | 1.33 |
| ablation: gamma0 | 1.15 | 1.06 | 1.36 | 1.04 | 1.11 | 1.27 | 0.94 | 1.08 | 1.34 |
| full-null | 1.36 | 1.77 | 2.05 | 1.08 | 1.23 | 1.78 | 1.15 | 1.25 | 2.00 |
| struct-null | 1.47 | 1.83 | 2.41 | 1.11 | 1.35 | 1.53 | 1.09 | 1.19 | 1.89 |
| sem-null | 1.21 | 1.67 | 2.29 | 1.08 | 1.28 | 1.75 | 1.13 | 1.26 | 1.93 |

## e3

| judge | labels (≤2026, levels 0–1) | n | identified among 4 (chance 0.25) | over-claim = not identified | most-chosen position share |
|---|---|---|---|---|---|
| llama3.1:8b (primary) | **SHAC-T (selected, α=0.5)** | 75 | 0.49 [0.38, 0.60] | 0.51 [0.40, 0.62] | 0.42 |
| llama3.1:8b (primary) | random-clusters | 75 | 0.45 [0.35, 0.57] | 0.55 [0.43, 0.65] | 0.48 |
| gemma2:9b | **SHAC-T (selected, α=0.5)** | 75 | 0.64 [0.53, 0.74] | 0.36 [0.26, 0.47] | 0.31 |
| gemma2:9b | random-clusters | 75 | 0.55 [0.43, 0.65] | 0.45 [0.35, 0.57] | 0.37 |
| phi4 | **SHAC-T (selected, α=0.5)** | 75 | 0.63 [0.51, 0.73] | 0.37 [0.27, 0.49] | 0.27 |
| phi4 | random-clusters | 75 | 0.52 [0.41, 0.63] | 0.48 [0.37, 0.59] | 0.33 |

Primary judge over all four snapshots: 0.53 [0.48, 0.59] identified (n = 300). 'random-clusters' = the model's tree with concept nodes permuted, relabelled by the same labeller and judged on its own held-out half. 8 of 300 labelled super-nodes have a single concept; their judge sees only paper texts.

Absolute rating by the primary judge (failed its negative control):

| labels judged against own held-out evidence (≤2026) | n | accurate | vague | wrong |
|---|---|---|---|---|
| model | 75 | 1.00 [0.95, 1.00] | 0.00 [0.00, 0.05] | 0.00 [0.00, 0.05] |
| swapped-gloss | 75 | 1.00 [0.95, 1.00] | 0.00 [0.00, 0.05] | 0.00 [0.00, 0.05] |
| random-clusters | 75 | 1.00 [0.95, 1.00] | 0.00 [0.00, 0.05] | 0.00 [0.00, 0.05] |

Deterministic checks (all snapshots, levels 0–1): year after cutoff 0/300, named non member 12/300, future entity 1/300.

## e4

| method (≤2026, 12 questions) | median cost to first target | recall@50 | recall@200 | wrong-domain@200 |
|---|---|---|---|---|
| **SHAC-T (selected, α=0.5)** | 1043 [178, 2493] | 0.00 [0.00, 0.01] | 0.01 [0.00, 0.03] | 0.00 [0.00, 0.00] |
| flat-lexical | 1400 [128, 2031] | 0.01 [0.00, 0.02] | 0.05 [0.03, 0.08] | 0.05 [0.02, 0.08] |
| ppr | 4 [2, 174] | 0.33 [0.13, 0.54] | 0.44 [0.23, 0.66] | 1.08 [0.50, 1.67] |
| degree-popularity | 11 [1, 40] | 0.47 [0.28, 0.67] | 0.64 [0.44, 0.82] | 2.62 [1.67, 3.58] |
| full-null | 1331 [883, 1816] | 0.00 [0.00, 0.02] | 0.02 [0.00, 0.07] | 0.03 [0.00, 0.08] |
| struct-null | 1758 [903, 2285] | 0.00 [0.00, 0.01] | 0.01 [0.00, 0.04] | 0.04 [0.00, 0.21] |
| sem-null | 795 [399, 1442] | 0.01 [0.00, 0.09] | 0.09 [0.00, 0.21] | 0.04 [0.00, 0.17] |
| random-labels | 1416 [748, 2470] | 0.00 [0.00, 0.01] | 0.01 [0.00, 0.08] | 0.04 [0.00, 0.21] |

Ranked baselines are scored by their expected value under random tie-breaking. 'degree-popularity' ignores the question.

## tests

| family | pre-registered primary test | model | null / baseline | p | p (Holm) |
|---|---|---|---|---|---|
| E1 | E1a model vs full | 0.985 | 1.044 | 1.000 | 1.000 |
| E2 | E2 perturbation ARI model vs full | 0.259 | 0.193 | 0.031 | 0.125 |
| E3 | E3 absolute over-claim (wrong share) model vs random-clusters — pre-registered; the instrument failed its swapped-gloss control | 0.000 | 0.000 | 1.000 | 1.000 |
| E4 | E4 cost hierarchy vs flat-lexical | 1042.600 | 1400.333 | 0.830 | 1.000 |

## tests_secondary

| family | secondary / post-hoc test (descriptive, no correction) | model | null / baseline | p |
|---|---|---|---|---|
| E3 | E3 absolute rating discriminates: accurate share true vs swapped glosses | 1.000 | 1.000 | 1.000 |
| E3 | E3 forced-choice identification model vs random-clusters (llama3.1:8b) — post hoc, added after the absolute rating failed | 0.493 | 0.453 | 0.372 |
| E3 | E3 forced-choice identification model vs chance (llama3.1:8b) — post hoc | 0.493 | 0.250 | <0.001 |
| E3 | E3 forced-choice identification model vs random-clusters (gemma2:9b) — post hoc, added after the absolute rating failed | 0.640 | 0.547 | 0.159 |
| E3 | E3 forced-choice identification model vs chance (gemma2:9b) — post hoc | 0.640 | 0.250 | <0.001 |
| E3 | E3 forced-choice identification model vs random-clusters (phi4) — post hoc, added after the absolute rating failed | 0.627 | 0.520 | 0.124 |
| E3 | E3 forced-choice identification model vs chance (phi4) — post hoc | 0.627 | 0.250 | <0.001 |
| E4 | E4 median cost model vs full-null | 1042.600 | 1330.834 | 0.238 |
| E4 | E4 median cost model vs random-labels | 1042.600 | 1416.154 | 0.210 |
| E4 | E4 cost hierarchy vs ppr | 1042.600 | 3.500 | 1.000 |
| E4 | E4 cost hierarchy vs degree-popularity | 1042.600 | 10.750 | 1.000 |
