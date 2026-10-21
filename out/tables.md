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
| **SHAC-T (selected, α=0.5)** | 0.98 [0.74, 1.22] | 0.99 [0.70, 1.27] | 1.24 [0.69, 1.78] |
| struct-null | 1.02 [0.99, 1.05] | 1.07 [1.02, 1.11] | 1.21 [1.16, 1.26] |
| sem-null | 1.01 [0.89, 1.12] | 1.08 [0.95, 1.23] | 1.17 [0.82, 1.39] |
| full-null | 1.02 [1.00, 1.05] | 1.06 [1.03, 1.10] | 1.18 [1.13, 1.22] |
| random-labels | 1.01 [0.98, 1.04] | 1.05 [1.02, 1.09] | 1.19 [1.13, 1.24] |

## e1_strata

| level 1, ≤2026, split B | overlap pairs | no-overlap pairs | pooled | unstratified |
|---|---|---|---|---|
| **SHAC-T (selected, α=0.5)** | 0.98 [0.62, 1.35] | 0.99 [0.41, 1.58] | 0.99 [0.70, 1.27] | 1.09 [0.81, 1.37] |
| full-null | 1.04 [1.00, 1.08] | 1.11 [1.04, 1.18] | 1.06 [1.03, 1.10] | 1.08 [1.05, 1.14] |

Paper pairs: 253 with a shared non-hub concept, 342 without.

## configs

| configuration (≤2026, level 1) | E1a lift (B) | perturbation ARI | cross-snapshot ARI 2024→26 | change localisation | E4 median cost | E4 recall@200 | level-0 giant share |
|---|---|---|---|---|---|---|---|
| **SHAC-T (selected, α=0.5)** | 0.99 [0.70, 1.27] | 0.26 [0.23, 0.29] | 0.96 | 1.54 | 1022 [178, 1758] | 0.01 | 0.13 |
| α = 0 | 0.90 [0.40, 1.40] | 0.35 [0.31, 0.39] | 0.85 | 1.52 | 400 [69, 1450] | 0.26 | 0.13 |
| α = 0.25 | 1.11 [0.57, 1.65] | 0.26 [0.22, 0.29] | 0.96 | 2.27 | 702 [282, 1642] | 0.13 | 0.12 |
| α = 0.75 | 1.17 [0.85, 1.49] | 0.24 [0.21, 0.27] | 0.94 | 0.94 | 1196 [130, 2232] | 0.03 | 0.13 |
| α = 1 | 1.12 [0.90, 1.33] | 1.00 [1.00, 1.00] | 0.98 | 0.79 | 1542 [328, 2118] | 0.03 | 0.13 |
| ablation: gamma0 | 1.41 [0.81, 2.02] | 0.37 [0.30, 0.44] | 0.37 | 1.08 | 860 [341, 2254] | 0.03 | 0.13 |
| ablation: rho_inf | 1.14 [0.90, 1.39] | 0.18 [0.08, 0.28] | 1.00 | – | 440 [302, 1454] | 0.08 | 0.93 |
| ablation: projection | 1.75 [1.05, 2.44] | 0.26 [0.24, 0.29] | 0.93 | 1.07 | 1146 [222, 2036] | 0.02 | 0.13 |
| ablation: freeze | 1.22 [0.38, 2.05] | 0.35 [0.25, 0.44] | 1.00 | – | 238 [160, 1158] | 0.14 | 0.22 |
| full-null | 1.06 [1.03, 1.10] | 0.19 [0.16, 0.22] | 0.89 | 1.30 | 1320 [798, 2159] | 0.01 | – |
| struct-null | 1.07 [1.02, 1.11] | 0.19 [0.17, 0.20] | 0.88 | 1.25 | 1350 [819, 2029] | 0.02 | – |
| sem-null | 1.08 [0.95, 1.23] | 0.20 [0.18, 0.23] | 0.89 | 1.26 | 778 [396, 1271] | 0.09 | – |

## e2_levels

| variant (≤2026) | pert. ARI L0 | pert. ARI L1 | pert. ARI L2 | 2024→26 ARI L0 | L1 | L2 |
|---|---|---|---|---|---|---|
| **SHAC-T (selected, α=0.5)** | 0.12 [0.10, 0.14] | 0.26 [0.23, 0.29] | 0.58 [0.53, 0.63] | 0.98 | 0.96 | 0.96 |
| ablation: gamma0 | 0.21 [0.18, 0.24] | 0.37 [0.30, 0.44] | 0.64 [0.57, 0.72] | 0.19 | 0.37 | 0.57 |
| ablation: freeze | 0.18 [0.15, 0.21] | 0.35 [0.25, 0.44] | 0.47 [0.37, 0.58] | 1.00 | 1.00 | 1.00 |
| full-null | 0.09 [0.08, 0.10] | 0.19 [0.16, 0.22] | 0.49 [0.44, 0.54] | 0.86 | 0.89 | 0.94 |

## e3

| judge | labels (≤2026, levels 0–1) | n | identified among 4 (chance 0.25) | over-claim = not identified | most-chosen position share |
|---|---|---|---|---|---|
| llama3.1:8b (primary) | **SHAC-T (selected, α=0.5)** | 75 | 0.49 [0.38, 0.60] | 0.51 [0.40, 0.62] | 0.43 |
| llama3.1:8b (primary) | random-labels | 75 | 0.45 [0.35, 0.57] | 0.55 [0.43, 0.65] | 0.48 |
| gemma2:9b | **SHAC-T (selected, α=0.5)** | 75 | 0.64 [0.53, 0.74] | 0.36 [0.26, 0.47] | 0.31 |
| gemma2:9b | random-labels | 75 | 0.55 [0.43, 0.65] | 0.45 [0.35, 0.57] | 0.37 |
| phi4 | **SHAC-T (selected, α=0.5)** | 75 | 0.63 [0.51, 0.73] | 0.37 [0.27, 0.49] | 0.27 |
| phi4 | random-labels | 75 | 0.52 [0.41, 0.63] | 0.48 [0.37, 0.59] | 0.33 |

Primary judge over all four snapshots: 0.53 [0.48, 0.59] identified (n = 300).

Absolute rating by the primary judge (failed its negative control):

| labels judged against own held-out evidence (≤2026) | n | accurate | vague | wrong |
|---|---|---|---|---|
| model | 75 | 1.00 [0.95, 1.00] | 0.00 [0.00, 0.05] | 0.00 [0.00, 0.05] |
| swapped-gloss | 75 | 1.00 [0.95, 1.00] | 0.00 [0.00, 0.05] | 0.00 [0.00, 0.05] |
| random-labels | 75 | 1.00 [0.95, 1.00] | 0.00 [0.00, 0.05] | 0.00 [0.00, 0.05] |

Deterministic checks (all snapshots, levels 0–1): year after cutoff 0/300, named non member 12/300, future entity 1/300.

## e4

| method (≤2026, 12 questions) | median cost to first target | recall@50 | recall@200 | wrong-domain@200 |
|---|---|---|---|---|
| **SHAC-T (selected, α=0.5)** | 1022 [178, 1758] | 0.00 [0.00, 0.01] | 0.01 [0.00, 0.03] | 0.00 [0.00, 0.00] |
| flat-lexical | 1207 [128, 1340] | 0.01 [0.00, 0.02] | 0.04 [0.01, 0.08] | 0.00 [0.00, 0.00] |
| ppr | 4 [2, 174] | 0.33 [0.13, 0.54] | 0.44 [0.23, 0.66] | 1.08 [0.50, 1.67] |
| full-null | 1320 [798, 2159] | 0.00 [0.00, 0.00] | 0.01 [0.00, 0.07] | 0.05 [0.00, 0.17] |
| struct-null | 1350 [819, 2029] | 0.00 [0.00, 0.01] | 0.02 [0.00, 0.09] | 0.04 [0.00, 0.17] |
| sem-null | 778 [396, 1271] | 0.01 [0.00, 0.10] | 0.09 [0.00, 0.21] | 0.05 [0.00, 0.17] |
| random-labels | 1270 [745, 1981] | 0.00 [0.00, 0.02] | 0.01 [0.00, 0.08] | 0.04 [0.00, 0.25] |

## tests

| family | pre-registered primary test | model | null / baseline | p | p (Holm) |
|---|---|---|---|---|---|
| E1 | E1a model vs full | 0.985 | 1.062 | 1.000 | 1.000 |
| E2 | E2 perturbation ARI model vs full | 0.259 | 0.188 | 0.031 | 0.125 |
| E3 | E3 forced-choice identification model vs random-labels (llama3.1:8b) | 0.493 | 0.453 | 0.372 | 1.000 |
| E4 | E4 cost hierarchy vs flat-lexical | 1022.500 | 1207.000 | 0.883 | 1.000 |
