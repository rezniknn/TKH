# Budgeted Semantic–Hypergraph Agglomeration over an Evolving Knowledge Hypergraph

**Alexey Reznik**

**Abstract.** We build a three-level, budgeted and laminar abstraction of a temporal knowledge hypergraph of 52
papers, cut into four cumulative snapshots. The method (SHAC) is a deterministic greedy agglomeration whose merge score
mixes, on a common rank scale, a name-similarity term and a structural term computed on the collapsed hyper-edge
incidence, with a localised prior from the previous snapshot. Laminarity, exact budgets and the hyper-edge collapse
rule hold by construction. Coherence is graded with a signal the method never sees, bibliographic coupling of
concept-disjoint papers, against a configuration null and random labels: the two finer levels beat both nulls at the
two largest snapshots (robustly in three of these four cells; p-values uncorrected, every paper-bootstrap CI includes 1), while the coarsest level is below chance. Change is localised, but persistence is not reliably higher
than under a random-attachment null. Labels over-claim in 58% of cases, and drill-down retrieval is no shortcut over
flat search.

*All numbers come from `out/` (run of 2026-10-28: `run_info.json`, `run_config.toml`, `metrics.json`,
`<t>/coarse_hyperedges.json`); formulas follow `tkh/` and `eval/`. Snapshots are written ≤t; levels are L0 (coarsest,
15 super-nodes), L1 (60) and L2 (240).*

## 1. Problem definition

The Temporal Knowledge Hypergraph (TKH) represents scientific literature as typed nodes (methods, tasks, datasets,
metrics, …) joined by dated hyper-edges of arbitrary arity. The assignment asks for a multi-resolution semantic
abstraction: per snapshot H(t), a laminar sequence of partitions under hard per-level budgets (P1, P2) whose
super-nodes are close in meaning (P3), computed on the hypergraph rather than a pairwise projection (P4), evolving
smoothly with trackable identities (P5), and labelled without unsupported claims (P6). The tasks cover the method and
its formal statement (T2), temporal coupling (T3), an implemented hyper-edge collapse rule (T4), labelling (T5) and a
circularity-safe evaluation (T6). We use the provided export cut at t ∈ {2020, 2022, 2024, 2026}: 16, 22, 38 and 52
papers; 1018, 1464, 2829 and 3980 concept nodes; 141, 230, 406 and 554 clustering hyper-edges.

## 2. Formal statement

**Input.** V_t is the set of concept nodes of snapshot t (method, task, problem, technique, component, dataset,
metric); an edge is in t if its paper is from year ≤ t. The clustering hypergraph G_t = (V_t, E_t) holds the edges of
six method-centred relations (addresses, solves, extends, uses_component, uses_technique, evaluated_on) restricted to
V_t, with *hubs* (concepts in more than 20% of the snapshot's papers; 5, 8, 7 and 6 hubs) removed and edges with fewer
than two members dropped. Citations, claims, authorship and titles never enter G_t. Weights are w_e = 1/(|e| − 1),
rescaled to equal total weight per relation. Each node has a text vector z_v: character 3–5-gram TF-IDF of its name
and aliases, reduced by SVD to 100 dimensions, centred and L2-normalised.

**Output.** For budgets (N_0, N_1, N_2) = (15, 60, 240), partitions P_{t,0} ⪰ P_{t,1} ⪰ P_{t,2} of V_t with
|P_{t,k}| = min(N_k, n_t), n_t = |V_t|, each refining the one above. Non-concept nodes (articles, claims, authors, cited works) are
then attached to the super-node of one concept anchor.

**Criterion.** A nested partition under hard budgets contains NP-hard single-level cases (modularity, normalised cut),
so SHAC (semantic–hypergraph agglomerative coarsening) optimises no global objective. It is a deterministic greedy
procedure: level k starts from the super-nodes of level k+1 (the singletons of V_t at the finest level) and merges the
feasible pair with the largest score until min(N_k, #items) remain:

$$ s(A,B) = \alpha\,F_S\big(S(A,B)\big) + (1-\alpha)\,F_H\big(H(A,B)\big), $$
$$ s_t(A,B) = (1-\gamma)\,s(A,B) + \gamma\,\Pi(A,B)\ \text{ if both } A, B \text{ hold stable old nodes, else } s(A,B). $$

- **Semantic term** S(A,B) = ⟨z̄_A, z̄_B⟩, the inner product of mean member vectors, i.e. average linkage.
- **Structural term** H(A,B) = Σ_{e: A∈e, B∈e} w_e / √(d_A d_B), with hyperdegree d_A = Σ_{e∋A} w_e and A ∈ e iff e has
  an endpoint in A, i.e. computed on the *collapsed* incidence of §4. The numerator is the merge's reduction of the
  connectivity cut (Proposition 1, §4); the normaliser stops high-degree super-nodes from absorbing everything.
- **Rank calibration.** F_S is the mid-rank empirical CDF of S over all item pairs at the start of the level; F_H that
  of H over pairs with H > 0, with F_H(0) = 0; both frozen per level. Ranks map incommensurable scales to [0, 1], so α
  is the explicit structure–semantics weight (α = 0 structure only, α = 1 semantics only).
- **Temporal prior** Π(A,B) = Σ_c M_{A,c} M_{B,c} / (u_A u_B), the share of pairs of stable members of A and B that
  shared a level-k super-node at t−1 (M_{A,c}: A's stable members in c; u_A = |A ∩ U_t|, §3).
- **Feasibility** |A| + |B| ≤ ρ·n_t/N_k with ρ = 2 (caps 530.7, 132.7, 33.2 at ≤2026). Ties: S and H are rounded to 1e-12
  and scores to 1e-9; ties of s_t are broken by s, then by the lowest item index.

The run uses α = 0.5, γ = 0.5, ρ = 2; γ was fixed before any result and no current result selects α or ρ.

**Lemma (budget feasibility).** If ρ ≥ 2 and K > N_k items remain, the two smallest have total size
≤ 2n_t/K < ρ·n_t/N_k, so a feasible merge exists and every level meets its budget exactly.

**Complexity.** Per level with n items, m edges, d = 100: O(n²(m + d)) initialisation, O(n(m + d)) per merge (O(n²)
worst case), O(n²) memory; the four-snapshot build takes 34.7 s.

| Property | Status |
|---|---|
| P1 laminarity, P2 budgets | by construction (merge-only levels; lemma); checked by `validate.py` |
| P4 hyper-edge fidelity | by construction: H uses the collapsed incidence; multi-way edges stay whole |
| No future information in structure and membership | by construction; member cutoffs checked by `validate.py` |
| P3, P5, P6, utility | empirical (§5) |

**Rejected alternatives.** Hypergraph modularity (h-Louvain [1]) sets the community count only through a resolution
parameter and does not nest across resolutions, whereas P2 is a hard constraint and P1 requires nesting. A two-stage
scheme (structure, then semantics) would freeze single-paper bundles before names could join them across papers.

## 3. Method and literature positioning

**Reconciling the signals.** Names relate generic tasks and techniques but not proper-named methods across families (a
"-Net" suffix is not a family). Structure relates co-used concepts but almost only within one paper, since every
clustering edge is a star around one paper's method. The rank mix lets either signal decide each merge: a pair sharing
no edge gets no structural credit and can win only on semantics, at weight α. Because the trade-off is one scalar on a
common scale, it is evaluable: the coherence ruler of §5 sees neither signal, so α ∈ {0, 0.5, 1} can be compared on
equal footing. The sweep (`make sweep`) predates the final verification fixes and is not used, so α = 0.5 is a stated
prior, not a measured optimum.

**Temporal stability (T3).** The stable set U_t holds old concept nodes that no new paper's clustering edge touches and
that are unaffected by hub changes (876, 1169 and 2629 nodes at ≤2022–≤2026). Only pairs that both hold stable nodes
receive Π; new and touched nodes are placed by structure and names alone. Change can thus occur where the corpus
changed, while untouched regions are pulled, not forced, to stay together. Identities and the
birth/growth/merge/split log come from largest-overlap matching (`tkh/temporal.py`), checked by `validate.py`; deaths
cannot occur because snapshots only grow. The cost is O(n²N_k) extra initialisation and path dependence.

| Work | Borrowed | Done differently, and why |
|---|---|---|
| h-Louvain [1] | hyper-edge-aware affinity on the native incidence; multilevel aggregation | no modularity or resolution; exact nested budgets; a semantic term |
| Featured Graph Coarsening [2] | joint topology–feature coarsening | on hyper-edge incidence; greedy merges, not a learned coarse graph; no similarity guarantee claimed |
| DynHAC [3] | average linkage; confining change to affected regions | a soft prior, not affected-region recomputation (fixed regions would occupy budget slots); its locality theorem needs a reducible linkage, which H is not |
| HyperEF 2.0 [4] | contracting hyper-edges while keeping coarse edges explicit | no ratio or spectral target (P2 fixes counts); multi-way edges scored by the connectivity cut |

The hypergraph setting needs this because a clique projection counts a multi-way edge once per member pair, rewarding
already-large paper bundles (§4); the temporal setting needs it because static or ratio-controlled coarseners give
neither persistent identities nor fixed display sizes. The structural null follows the hypergraph configuration model
[5], and Π is an evolutionary-clustering term [6]. The contribution is their integration under hard budgets with an
evaluation that does not reuse the method's signals.

## 4. Coarsening decision

For a fine edge e of reduced arity n_e with endpoint counts c_S(e), let λ_e = #{S : c_S(e) > 0} and m_e = max_S c_S(e).
`tkh/coarsen.py` assigns every edge to exactly one of three classes:

- **m_e = n_e (λ_e = 1): internal.** It drops out of every H numerator, but its weight stays in d_A, damping
  super-nodes that have already absorbed much of their incident weight.
- **1 < m_e < n_e (2 ≤ λ_e < n_e): partial.** One coarse hyper-edge over its λ_e super-nodes; counts kept as metadata;
  presence scored.
- **m_e = 1 (λ_e = n_e): uncollapsed.** The fine edge itself, one endpoint per super-node; scored as partial.

Separately, an edge touching three or more super-nodes (λ_e ≥ 3) is flagged **multi-way**. The flag is not a class: a
multi-way edge is partial or uncollapsed. It stays one hyper-edge, is never split into pairs, and adds w_e to the H
numerator of every pair of super-nodes it touches.

**Proposition 1.** Let C = Σ_e w_e(λ_e − 1). Merging A and B reduces C by exactly Σ_{e∋A,B} w_e, since each such edge
loses one distinct super-node and no other edge changes. The structural numerator is thus the gain in the standard
(λ − 1) connectivity objective of hypergraph partitioning, for any arity.

**Why this rule.** Every clustering edge is a star around one paper's method. A count-based (clique) score
c_A(e)·c_B(e) pays a super-node more the more of that star it already holds, reinforcing paper bundling; presence
counts each edge once per super-node. The rule is the one the method applies: the incidence is updated after every
merge (`_Level.merge`), and the same partition writes `out/<t>/coarse_hyperedges.json`. At ≤2026:

| Level | Internal | Partial | Uncollapsed | Multi-way (partial + uncollapsed) |
|---|---|---|---|---|
| L0 | 194 | 325 | 35 | 111 (94 + 17) |
| L1 | 115 | 382 | 57 | 153 (116 + 37) |
| L2 | 68 | 386 | 100 | 249 (173 + 76) |

Native and clique scores diverge when a shared edge has two or more endpoints on one side, as in 40 of 45, 151 of 180
and 2177 of 3740 merges at L0–L2 (≤2026); whether a clique build would have *chosen* other merges was not measured. **Losses:**
endpoint multiplicity in the score, which fine members took part, coarse-edge identity across levels, and merging of
parallel coarse edges (score-neutral, as H and d_A are sums over edges).

## 5. Evaluation

**Coherence and the circularity hazard.** Clustering uses name n-grams and six method-centred relations, so a
coherence score built on either would grade the method with its own ruler. `eval/coherence.py` neutralises this in four
steps. (i) *Held-out signal:* bibliographic coupling c_pq, the IDF-weighted Salton cosine of two papers' cited-work
sets; citations never enter G_t, z_v or Π. (ii) *Residual name filter:* citations to works named like one of the
paper's own concepts are dropped, so "extends X / cites X" cannot leak (260 removed at ≤2026 by exact, 342 by fuzzy
matching). (iii) *No-overlap pairs:* only paper pairs sharing no concept node or name are scored. (iv) *Period
control:* same-era papers cite the same works, so the lift Σ a_pq c_pq / Σ a_pq e_pq standardises by e_pq, the mean
coupling of no-overlap pairs in the same period stratum (a_pq: co-assignment of the papers' concepts; 1 = chance). The
lift is compared with a **configuration null** (99 full rebuilds on a type- and period-preserving hypergraph
configuration model [5]; it keeps the real names, so it asks what the hyper-edge structure adds beyond degrees) and **random labels** (999 permutations within type × entry interval over the fixed tree, which keep every super-node's size); p floors are 0.01 and
0.001. A cell is *robust* only if p ≤ 0.05 against both nulls under all five period schemes with the exact filter (primary); p-values are not corrected across the 12 snapshot × level cells. The stricter fuzzy filter gives the same or stronger verdicts (it adds ≤2022 L1 and ≤2024 L1).

**Stability.** As the brief asks, 10% of all hyper-edges are removed for 5 seeds (stratifying by period × relation is our addition) and the
chain rebuilt; snapshots are scored against the unperturbed run by per-level ARI and HARI, a level-pooled laminar ARI
Σ_k(I_k − E_k)/Σ_k(M_k − E_k) weighted about 75% to L0 (t-intervals). Cross-snapshot agreement on common concept nodes
(intervals over 200 half-subsamples) is tested against a **new-paper null** (R = 99) that keeps the real past graph and
hierarchy and redraws which old nodes new papers attach to. *Localisation* compares reassignment (1 − Jaccard of
co-members) of old nodes touched by new papers with untouched ones.

**Label faithfulness.** L0–L1 labels and one-sentence glosses come from `qwen2.5:7b-instruct`, which sees one half of
a seeded, kind-stratified 50/50 split of the group's snapshot evidence (concept names with types and aliases, clustering facts, claims, future-work topics, paper titles; no citations; both halves in `out/<t>/label_inputs.json`), plus, as contrast, up to 4 seen-half concept names from each of the 10 same-level groups that share the most clustering edges with it. A judge
of another family (`phi4`) splits label + gloss into ≤ 3 atomic claims and checks each against the **held-out** half,
citing an existing line; the over-claim rate is the share of labels with an unsupported claim. Restating the
labeller's input cannot pass, but both halves use the same kinds of text, so shared vocabulary is not controlled.
Decomposition passes its content check for 61% of labels; the rest are judged as [label, gloss]. Deterministic checks flag post-cutoff years, named non-members and future entities.

**Extrinsic utility.** An agent answers 18 questions at ≤2026 (14 type A, specific search; 4 type B, synthesis),
descending from L0 with a 10/20/40 beam scored by keyword overlap with label, gloss and member text, against flat
search with the same scorer. Only the evaluator reads the ground truth; one step is one inspected node.

| Metric | Cell | Result | Reference | Verdict |
|---|---|---|---|---|
| Coherence lift (interval, exact) | ≤2026 L0 / L1 / L2 | 0.88 [0.53, 1.25] / 1.31 [0.54, 2.00] / 1.57 [0.43, 2.63] | null means ≈ 1.0; p (config. / labels) 1.0/1.0, 0.01/0.001, 0.01/0.001 | L1, L2 robust; L0 below chance |
| | ≤2024 L0 / L1 / L2 | 0.83 / 1.32 / 1.86 | p 1.0/1.0, 0.01/0.001, 0.01/0.001 | L2 robust; L1 fails `gap` (p 0.10/0.152) |
| | ≤2022 L1 / L2 | 1.06 / 0.99 | p 0.17/0.139, 0.76/0.60 | not significant |
| Perturbation HARI | ≤2020, ≤2022, ≤2024, ≤2026 | 0.58 [0.54, 0.62], 0.36 [0.32, 0.40], 0.20 [0.18, 0.23], 0.17 [0.16, 0.18] | unperturbed run | L2 ARI 0.90 → 0.63; L0 0.53 → 0.12 |
| Cross-snapshot HARI | 2020→22, 22→24, 24→26 | 0.86 [0.83, 0.88], 0.80 [0.77, 0.82], 0.89 [0.87, 0.90] | null 0.85, 0.75, 0.86; p 0.33, 0.06, 0.12 | high, not above null |
| Localisation ratio | all transitions, levels | 2.4–7.0, CI lower bounds ≥ 2.0 | 1 = none | localised |
| Over-claim rate | L0–L1 (n = 296) | 0.58 [0.52, 0.64]; L0 0.37 [0.25, 0.48], L1 0.64 [0.57, 0.69] | no chance baseline | not faithful |
| Hit-rate, drill-down vs flat | A methods (12) / A method claims (9) / A citations (14) / B claims (4) | 0.275 vs 0.295 / 0.250 vs 0.306 / 0.657 vs 0.578 / 0.740 vs 0.543 | flat search | mixed |
| Median steps to first target | A / B | 206.5 vs 10.5 / 143 vs 2 | flat search | flat far cheaper |

*Evaluation summary; brackets are 95% intervals. Sources in `out/metrics.json`: `coherence.snapshots.<t>`,
`stability.perturbation`, `stability.cross_snapshot`, `stability.localisation`, `faithfulness.over_claim`,
`faithfulness.by_level`, `retrieval.summary`.*

![Held-out coherence lift](figures/coherence_lift.png)

*Figure 1. Period-adjusted held-out lift (exact filter) with both null bands; 1 = chance.*

**Coherence.** Where evidence is densest (≤2024, ≤2026: 21 and 58 coupled pairs), L1 and L2 co-assign concepts of
citation-coupled, concept-disjoint papers more than both nulls, and the lift grows with resolution (Figure 1); three
cells are robust (≤2026 L1, L2; ≤2024 L2). L0 lies *below* both null bands at every snapshot (p = 1.0), so the citation
signal does not support its groupings. ≤2022 does not beat the nulls under the primary scheme with the exact filter (with the fuzzy filter L1 and L2 do, and
L1 is robust), and ≤2020 (5 coupled
pairs) is not evidence. Without period control the ≤2026 L2 null means rise to 1.20 and 1.21; with it they fall to
about 1.0. The tests are conditional on the corpus and every paper-bootstrap CI includes 1, so the finding is "better
than chance on this corpus", not a population estimate.

![Stability](figures/stability.png)

*Figure 2. (a) Perturbation ARI and HARI; (b) cross-snapshot agreement against the new-paper null band.*

**Stability.** Persistence is high but statistically neutral: the new-paper null is nearly as stable (Figure 2b), and
of 12 tests only 2024→26 L2 reaches p = 0.01, uncorrected. Persistence therefore comes from what the null shares with
the run (past graph, past hierarchy, prior), not from the corpus' attachment pattern. Perturbation robustness is low at
coarse levels and falls with snapshot size (Figure 2a): at ≤2026 a 10% deletion yields a different L0 (ARI 0.12).

![Localisation](figures/localisation.png)

*Figure 3. Reassignment of touched and untouched old nodes and their ratio with 95% CI.*

**Localisation.** Touched nodes are reassigned 2.4–7.0 times as often as untouched ones, most sharply at L2 (Figure 3);
untouched nodes still move (0.09–0.23) and, being 94–96% of old nodes, carry 78–89% of all reassignment, so regions are held, not frozen. Without a γ = 0 control on the current build,
neither localisation nor the robustness loss can be attributed to Π.

**Labels and retrieval.** Most labels over-claim (0.58). L0 labels are more faithful than L1 labels (non-overlapping
CIs), although L0 groups also have larger held-out pools, and the judge is not validated, so the rate is descriptive.
No label names a post-cutoff year; 33 labels name a method or dataset outside the group, mostly generic acronyms such as "DFT" and "GNN", and the 4 future-entity flags are name collisions. In retrieval the hierarchy acts as a
filter that can sharpen answers (citations, synthesis claims), not as a shortcut: it scores 133–162 super-nodes before
its first leaf and misses 2 questions at L1. This comparison has no CIs or nulls and was tuned in sample.

**Variant to ship.** No variant comparison is current (`make gamma`, `make sweep` predate the final fixes). We would
ship the evaluated configuration, using L1–L2 for semantic claims and L0 for navigation only.

## 6. Future work

**Assumed, not verified:** within-paper relations indicate relatedness; names carry weak semantics; coupling between
concept-disjoint papers proxies closeness in meaning; export-wide names carry no post-cutoff information; entry follows
publication years; untouched structure should keep its grouping (not supported by the null). **Simplifications:**
irrevocable greedy merges, dense O(n²) memory, a lexical retrieval scorer, one labeller, one judge, one evidence split.
**Verified:** P1–P2 at every snapshot; the applied T4 rule; L1–L2 coherence above both nulls under all five period schemes at ≤2026, and for L2 at ≤2024 (≤2024 L1 fails only the `gap` scheme; uncorrected tests, this corpus only); localised
change; no post-cutoff years in labels.

1. **Controls:** γ = 0 runs and a fresh α/ρ/hub sweep selected on held-out halves of the citation ruler.
2. **Multiplicity-aware collapse:** H_β = Σ_e w_e (c_{A,e} c_{B,e})^β/√(d_A d_B), from β = 0 (shipped) to β = 1
   (clique), to quantify what the projection loses.
3. **Graded structure:** multi-hop affinity (spectral smoothing as in [4]), since H is zero for most singleton pairs.
4. **Repair L0:** per-super-node coupled-pair diagnostics; an L0 from task and dataset families or a stronger
   independent embedding.
5. **Labels:** judge validation (known answers, second judge, human ratings), null-tree baselines, repeated splits.
6. **Retrieval:** paired bootstrap CIs, a random-tree null, held-out tuning, earlier snapshots.
7. **Scale:** sparse k-NN candidates and DynHAC-style dirty-region updates [3].

## References

[1] B. Kamiński, P. Misiorek, P. Prałat, F. Théberge. Modularity based community detection in hypergraphs. *J. Complex
Networks*, 2024.
[2] M. Kumar, A. Sharma, S. Saxena, S. Kumar. Featured graph coarsening with similarity guarantees. *ICML*, 2023.
[3] S. Yu, L. Dhulipala, J. Łącki, N. Parotsidis. DynHAC: Fully dynamic approximate hierarchical agglomerative
clustering. *SDM*, 2025.
[4] Sajadinia, Feng. HyperEF 2.0: Spectral hypergraph coarsening via Krylov subspace expansion and resistance-based
local clustering. *ICCAD*, 2025 (arXiv:2511.06600).
[5] P. S. Chodrow. Configuration models of random hypergraphs. *J. Complex Networks*, 2020.
[6] D. Chakrabarti, R. Kumar, A. Tomkins. Evolutionary clustering. *KDD*, 2006.
