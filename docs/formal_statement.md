# Formal statement of the method (Deliverable 0)

**SHAC:** semantic–hypergraph agglomerative coarsening, a budget-constrained hierarchical
agglomeration of the concept nodes that scores merges on the collapsed hypergraph and on name
semantics.

| Part | Code |
|---|---|
| Method | `tkh/hierarchy.py` |
| Clustering hypergraph and T4 collapse | `tkh/coarsen.py` |
| Run | `tkh/pipeline.py`, `python -m tkh build` |
| Null models | `tkh/null.py` |
| Held-out P3 check | `tkh/p3.py`, `tkh/experiments.py` |

Parameters are in `[method]` of `configs/default.toml`. Every result in §§3, 8 and 9 comes from
`out/run_info.json`, `out/metrics.json`, `out/sweep.json` or `out/<t>/coarse_hyperedges.json`, produced by
`make all` and `make sweep`. Data facts cite notebooks 01–03.

## 1. Input and notation

- **Snapshots.** Cutoffs t ∈ {2020, 2022, 2024, 2026}, configurable. An edge is in snapshot t iff
  its paper is from year ≤ t. A node's entry year is the earliest year of its provenance papers and
  of its incident edges' papers; the node is in t iff that year is ≤ t (`tkh/io.py`; notebook 01
  §2 shows why the export's other year fields leak).
- **Items.** V_t is the set of concept nodes of snapshot t: types method, task, problem, technique,
  component, dataset and metric, which are exactly the member types of the method-centred relations
  (notebook 03 §1). n_t = |V_t| is 1018, 1464, 2829 and 3980.
  - Articles, authors, claims, cited works and future topics are anchored after clustering (§5).
- **Clustering hypergraph G_t = (V_t, E_t).**
  - E_t holds the snapshot's edges of the six method-centred relations (addresses, solves, extends,
    uses_component, uses_technique, evaluated_on), with members restricted to V_t and deduplicated.
  - Hubs are removed: concept nodes in more than `hub_frac` of the snapshot's papers, i.e. in at
    least ⌊hub_frac·|papers_t|⌋ + 1 papers. With the default 0.2 the threshold is 4, 5, 8 and 11
    papers, giving 5, 8, 7 and 6 hubs.
  - Edges left with fewer than 2 members are dropped, leaving m_t = 141, 230, 406 and 554 edges.
  - `cites`, `claims`, `presents`, `authored_by` and `proposes_future_work` never enter G_t.
- **Edge weights w_e** (`edge_weight`):
  - `inverse_size`: w_e = 1/(|e| − 1).
  - `relation_balanced` (default): inverse_size rescaled so that each relation's weights sum to 1.
  - Why the default: under inverse_size alone, evaluated_on carries 85% of the weight, because it is
    mostly small benchmark triples, a large share of them from a few papers (notebook 03 §5). Any weighting chooses
    which relation drives the grouping, so the default spreads the choice evenly.
- **Text.** z_v is the L2-normalised, mean-centred LSA projection of node v's name and aliases:
  - a character 3–5-gram TF-IDF (sublinear), fitted on V_t only;
  - then a dense exact SVD when the TF-IDF matrix has at most 400 rows or columns, otherwise ARPACK
    with a fixed seed, to `lsa_dim` = 100 dimensions.

  In notebook 02's trial clustering, raw TF-IDF chains (99.6% of nodes in one of 15 clusters), while
  LSA reduces this to 39% at 15 clusters and 7.5% at 60.
- **Never used in G_t or z_v:** titles, claims, future topics, edge attributes, cited works,
  citations, authors, abstracts. `claims` and `cites` edges are used only to anchor claim and
  cited-work nodes after clustering (§5). Notebook 03 §8 explains why: they re-encode "same paper" or serve as held-out
  evidence.
- **Budgets.** N_0 ≤ N_1 ≤ … ≤ N_{K−1}, any list of length ≥ 2; the default is (15, 60, 240).
  - Level 0 is the coarsest. The brief fixes only N_0 ≈ 10–15.
  - No step assumes particular values: N_k enters only as the stopping target min(N_k, n_t) and
    through the size cap ρ·n_t/N_k, so any non-decreasing list works.
  - The singleton level P_K is implicit in `member_ids`; it is not written as a level.

## 2. Objective

SHAC optimises no global objective. The problem it would face is a hierarchical partition with
hard budgets. Even its single-level, unconstrained relatives, modularity and normalised cut, are
NP-hard. SHAC is instead a **deterministic greedy procedure with a stepwise criterion**. The
criterion is the method; there is no optimality guarantee.

**Level k of snapshot t**, run from the finest level to the coarsest:
- **Start.** The items are the super-nodes of level k+1, or the singletons of V_t at the finest level.
- **Step.** Repeat: merge the feasible pair (A, B) with the largest s(A, B). Stop when
  min(N_k, #items) items remain.

**Score:**

    s(A, B) = α · F_S(S(A, B)) + (1 − α) · F_H(H(A, B))

- **Semantic term.** S(A, B) = ⟨z̄_A, z̄_B⟩, the dot product of the members' mean vectors. This
  equals the average pairwise cosine between members of A and members of B (average linkage).
- **Structural term.** H(A, B) = Σ_{e: A∈e, B∈e} w_e / √(d_A d_B), with d_A = Σ_{e∋A} w_e
  (0 if d_A·d_B = 0).
  - It is computed on the **current collapsed incidence**: A ∈ e iff e has at least one endpoint in A (§3).
  - Its numerator is the reduction of the weighted connectivity cut that the merge causes (Prop. 1).
  - The denominator is a Salton normalisation by hyperdegree, which stops high-degree super-nodes
    from absorbing everything.
- **Reconciliation.**
  - F_S is the mid-rank CDF of S over all live item pairs at the start of the level.
  - F_H is the mid-rank CDF of H over the pairs with H > 0, with **F_H(0) = 0**.
  - Both are frozen for the level.
  - Ranks put two incomparable scales on [0, 1]. A pair that shares no edge gets no structural
    credit, and can win only on semantics, at weight α.
  - The convex mix is the explicit structure-versus-content trade-off that P3 asks for. α = 0 is
    structure only and α = 1 is semantics only.
- **Feasibility.** The size cap |A| + |B| ≤ c_{t,k} = ρ · n_t / N_k, counted in concept nodes,
  with ρ ≥ 2.
- **Ties.** S and H are rounded to 1e-12 before ranking, so values that differ only by
  floating-point error tie exactly; scores are rounded to 1e-9; then the lower item index wins (ids
  sorted). The build is deterministic.

**Why a joint score rather than two stages.** The two signals fail in different places:
- names alone cannot relate proper-named methods across families (SchNet's best name neighbour
  scores 0.11, notebook 02 §2);
- structure alone mostly links nodes of one paper, because 94% of concept nodes are in a single
  paper and cross-paper evidence is a few bridges (notebook 03 §§3, 5).

A two-stage scheme, structure first and then semantics, would freeze paper bundles before names
could join them across papers. A single score lets either signal decide each merge.

## 3. T4: what a hyper-edge becomes, and how the method uses it

A fine edge e with arity n has endpoint counts c_S(e) over the super-nodes S. Let
λ_e = #{S : c_S(e) > 0}.

| Case | Coarse edge | In the score |
|---|---|---|
| m = n (λ_e = 1) | **internal**: links no super-nodes; kept as a record | drops out of every H numerator; its weight still counts in d_A, which lowers H for that super-node |
| 1 < m < n (λ_e < n) | **partial**: one coarse edge over the λ_e super-nodes, with c_S(e) kept as metadata | counted once per pair of super-nodes it touches (presence) |
| three or more super-nodes (λ_e ≥ 3) | **multi-way**: stays one hyper-edge, never split into pairs | its weight enters H for every pair of super-nodes it touches, and the cut reduction Σ w_e(λ_e − 1) keeps it whole |

The score is computed from exactly this collapsed incidence, which is updated after every merge
(`_Level.merge`). The records in `out/<t>/coarse_hyperedges.json` come from the same incidence and
partition.

**What the rule loses:**
- endpoint multiplicity in the score, which uses presence only;
- which fine members took part, kept only as the fine edge id.

**At ≤2026**, of the 554 edges:

| Level | Internal | Partial | Uncollapsed | Multi-way |
|---|---|---|---|---|
| 0 | 311 | 217 | 26 | 59 |
| 1 | 218 | 289 | 47 | 105 |
| 2 | 82 | 381 | 91 | 203 |

**Proposition 1 (merge gain).** Let C = Σ_e w_e (λ_e − 1). Merging A and B reduces C by exactly
Σ_{e: A∈e, B∈e} w_e. *Proof:* an edge with endpoints in both A and B loses one distinct super-node,
and no other edge changes. ∎ This is tested on 50 random cases.

**Proposition 2 (where native and clique expansion differ).**
- At singletons, H(a, b) = Σ_{e∋a,b} w_e / √(d_a d_b) is a normalised weighted clique expansion.
- The native score differs from clique average linkage only once a super-node holds two or more
  endpoints of an edge it shares with its merge partner. Native H counts that edge once per pair of
  super-nodes; the clique view counts it once per member pair.
- Measured at ≤2026, this happens in **39 of 45, 174 of 180 and 2287 of 3740 merges** at levels 0,
  1 and 2 (`multi_endpoint` in `run_info.json`). So the hypergraph form decides most merges.
- No pairwise projection is built or compared.

**Lemma (cap feasibility).** If ρ ≥ 2 and K > N_k items remain, a feasible pair exists. *Proof:*
the two smallest items have total size ≤ 2n_t/K < 2n_t/N_k ≤ c_{t,k}. ∎
- Every level therefore has exactly min(N_k, n_t) super-nodes, for any budget list (tested on five
  lists, including N_k > n_t).
- ρ < 2 is rejected.

## 4. Output

For each t, the output is a set of partitions P_{t,0}, …, P_{t,K−1} of the whole snapshot with:
- |P_{t,k}| = min(N_k, n_t) super-nodes;
- P_{t,k+1} refining P_{t,k}, because every level is a cut of one merge sequence.

Anchored nodes are added to their anchor's super-node at every level. Ids and the event log come
from overlap matching (`tkh/temporal.py`).

Labels are deterministic placeholders. They restate the composition, counting papers within the
snapshot only.

## 5. Anchoring of non-concept nodes

| Node type | Anchor |
|---|---|
| claim | the method member of its `claims` edge, else the paper's presented method |
| cited_work | the presented method of the earliest citing paper |
| article | its own presented method |
| author, future_topic | the presented method of their earliest paper |

No anchor uses names, so cited works cannot reach clusters through text. A node with no anchor
raises an error; none occurs in the data.

## 6. Guaranteed vs measured

| Property | Status |
|---|---|
| P1 laminarity | **by construction** (one merge sequence); checked by `validate.py` |
| P2 budgets | **by construction**: exactly min(N_k, n_t) per level (lemma); checked by `validate.py` |
| Hyper-edge fidelity (P4, T4) | **by construction**: H is computed on the collapsed incidence (Prop. 1), and multi-way edges stay whole |
| Size bound | **by construction**: no super-node exceeds ρ·n_t/N_k concept nodes; anchored nodes are not counted |
| Determinism | **by construction**: deterministic SVD and tie-breaking; tested on the fixture and on the real ≤2020 snapshot |
| No future information | structure, membership and labels use snapshot t only; text only up to A4 |
| P3 semantic coherence | **empirical**, at the last snapshot only (§8): level 0 beats both nulls; level 1 beats the configuration null, and random labels only under the fuzzy filter; level 2 beats neither |
| P5 temporal stability | not addressed: matching does identity bookkeeping only |
| P6 faithful labels | not addressed: placeholders |

## 7. Complexity

Per level, with n items, m fine edges and d = `lsa_dim`:
- **Initialisation:** O(n²(m + d)) time for the score matrix, plus O(n² log n) for the rank CDFs.
- **Each merge:** O(n(m + d)) to rescore the merged item. Rows whose best partner was a merged item
  are rescanned at O(n) each. There are n − N_k merges.
- **Memory:** O(n²) for the dense score matrix (127 MB at n = 3980), plus O(nm) for the incidence.

The full build of four snapshots takes about 29 s in one process (`runtime_s` in `run_info.json`). Much larger graphs
would need a sparse candidate set.

## 8. Null models and the held-out P3 check

**Null model** (`tkh/null.py`): the **type- and period-preserving hypergraph configuration model**.
- It is the degree- and arity-preserving shuffle that the brief names (T6) and the standard
  structural null for hypergraph clustering (Chodrow 2020, vertex-labelled).
- **Sampling.** Curveball trades on the edge tails (members[1:]) within each stratum of
  (relation, cutoff interval, member type), for 10 sweeps.
- **Preserved:** each node's degree per relation, interval and type, and each edge's arity,
  type mix, hub members[0], paper and year. Hence every snapshot keeps its node set (asserted),
  and the other relations are untouched.
- **Mixing:** 86% of the incidences move.
- **Use.** The null graph runs through the same pipeline with the same parameters, and with the
  real snapshot's hub sets, so `hub_frac` means the same thing in both. Its output passes
  `validate.py` (`make null`).
- **What it measures.** The null keeps the names, so it measures what structure adds beyond
  degrees, given the semantics.
- **Companion:** random labels, i.e. concept-node ids permuted within (type, entry interval) over
  the evaluated tree, which keeps the laminar structure and every size.

**Held-out ruler** (`tkh/p3.py`). P3 asks for closeness in meaning. The proxy is bibliographic
coupling, a signal that no clustering input contains. It is fixed by the evaluator and computed
once on the real export, identically for every configuration and null:
- **Coupling c_pq:** the IDF-weighted Salton cosine of two papers' cited-work sets.
- **Names:** normalised surface forms and aliases, i.e. exactly the names the method's text sees.
- **Residual filter:** drop a paper's cited works named like one of its own concept nodes, so that
  "extends X / cites X" does not count.
  - *exact*: a shared normalised name;
  - *fuzzy*: also name containment, for names of ≥ 4 characters.
- **Pairs:** only **no-overlap** pairs count, i.e. pairs sharing no concept node and no concept name,
  excluding evaluator hubs (fixed share 0.4, independent of `hub_frac`). On these pairs, shared
  structure explains nothing.
- **Co-assignment:** a_pq = Σ_S n_S(p) n_S(q) / (n_p n_q) per level.
- **Lift:** Σ a·c / (Σ a · mean c); 1 means chance.
- **Coverage at ≤2026:** 37 citing papers, 252 no-overlap pairs, 58 of them coupled; the filter
  removes 260 citation incidences.
- **Only the last snapshot is checked.** Earlier snapshots have too few evaluable pairs: 9, 14 and
  25 citing papers at ≤2020, ≤2022 and ≤2024, with 5, 11 and 21 coupled no-overlap pairs.

**Results at ≤2026** (`out/metrics.json`). Lifts use the exact filter, with a paper-bootstrap
95% CI. Null means come from 99 null rebuilds and 999 random-label draws. p = (1 + #null ≥ obs)/(R + 1).

| Level | Lift [95% CI] | Configuration null: mean, p | Random labels: mean, p |
|---|---|---|---|
| 0 (15) | 1.38 [0.81, 2.14] | 1.05, **0.01** | 1.08, **0.001** |
| 1 (60) | 1.28 [0.63, 2.30] | 1.15, **0.02** | 1.25, 0.19 |
| 2 (240) | 1.08 [0.46, 2.03] | 1.39, 1.00 | 1.43, 1.00 |

Under the fuzzy filter:
- level 0 gives 1.55 (p = 0.01 and 0.001);
- level 1 gives 1.48, which also beats random labels (1.20, p = 0.001);
- level 2 gives 1.30, which beats neither null (p = 0.69 and 0.75).

**Reading:**
- **Level 0** groups concepts of citation-coupled papers more than chance, and more than the same
  pipeline on degree-preserving random structure.
- **Level 1** beats the structural null. It beats the random-label baseline only under the fuzzy
  filter, so it is supported less firmly.
- **Level 2** does not show P3. Its small, cap-bound super-nodes mostly rebuild paper bundles (A1),
  and random partitions of the same sizes do as well or better.
- **Random labels exceed 1.** They keep each super-node's mix of type and entry period, and papers
  of the same period cite similar work. That is why the baseline is the null, not 1.
- **Two kinds of uncertainty.**
  - The null tests are conditional on these 37 papers: the ruler is held fixed and only the
    partition varies.
  - Over papers, the bootstrap CIs are wide and include 1 at every level.
  - So the evidence is "better than chance for this corpus", not a population estimate.

## 9. Parameters and selection

| Parameter | Default | Role |
|---|---|---|
| α (`alpha`) | 0.5 | weight of the semantic rank |
| ρ (`rho`) | 2 | size-cap factor (≥ 2, or inf) |
| `edge_weight` | relation_balanced | edge weighting (§1) |
| `hub_frac` | 0.2 | hub threshold as a share of the snapshot's papers (1.0 = no hubs) |
| `lsa_dim` | 100 | text projection rank |

- **Overrides.** Every parameter, the budgets and the cutoffs can be overridden, e.g.
  `python -m tkh build --param alpha=0.25 hub_frac=0.3 --budgets 10 40 160`.
- **Strict parsing.** Unknown parameters are an error.
- **Run record.** Each run writes its resolved `run_config.toml` and validates against it.

**Selection protocol** (`make sweep`, `out/sweep.json`):
- **Grid:** α ∈ {0.25, 0.5, 0.75} × ρ ∈ {2, 4} × edge_weight ∈ {inverse_size, relation_balanced} ×
  hub_frac ∈ {0.1, 0.15, 0.2, 0.3, 1.0}, i.e. 60 configurations. At ≤2026 these hub fractions give
  20, 10, 6, 2 and 0 hubs.
- **Ablations:** α = 0 and α = 1, reported but not selectable.
- **Splits:** 20 seeded halves (A, B) of the cited works, stratified by citation count.
- **Rule per split:** on half A, take the best configuration by mean lift over levels. Among the
  configurations within one paper-bootstrap SE of it, pick the one closest to the default,
  comparing in the order α, ρ, edge_weight, hub_frac. Report that pick on half B.

**Outcome: the ruler cannot rank the configurations.**
- The best configuration's bootstrap SE is about 0.87 (median), on its criterion of about 1.8.
  Configurations average 1.2.
- Between 3 and 56 of the 60 configurations lie within one SE, depending on the split.
- The ranking does not replicate: within a split, the half-A and half-B rankings of the
  configurations correlate at a median Spearman ρ of −0.07 (range −0.39 to 0.18).
- So the rule mostly falls back to the default, picked in 16 of 20 splits. **The default is not
  shown to be optimal; it is not distinguishable.**
- Descriptively, on half B (mean over splits):
  - the structure-only ablation α = 0 scores 1.45, 4th of 62;
  - the default scores 1.25, 25th of the 60 grid configurations;
  - α = 1 scores 1.10, 48th of 62.

  This is consistent with structure carrying the cross-paper evidence, but it is within the noise.
- Telling configurations apart needs a stronger independent signal than 37 citing papers. That is
  for the evaluation (T6).

## 10. Assumptions

- **A1.** Concept relations within a paper indicate relatedness. Every clustering edge is a star
  around one paper's method, so structure is mostly paper co-occurrence, and fine levels rebuild
  papers (§8).
- **A2.** Names carry weak but real semantic signal: informative for tasks, problems and
  techniques, nearly useless for proper-named methods (notebook 02). That is why α < 1.
- **A3.** Bibliographic coupling between papers that share no concept is a proxy for closeness in
  meaning.
- **A4.** Names and aliases are export-wide and undated. They are assumed to carry no information
  from after the cutoff that matters; this cannot be checked from the export.
- **A5.** The provenance publication year is when a node or edge enters the graph.

## 11. Trade-offs and rejected alternatives

- **Greedy agglomeration vs global optimisation.**
  - Gains: exact budgets, laminarity by construction, determinism, and merges that can each be
    explained.
  - Costs: early merges cannot be undone, and there is no optimality guarantee.
- **Hypergraph modularity / h-Louvain (Kamiński et al.), rejected.**
  - It controls the number of communities only indirectly, through a resolution parameter,
    whereas P2 makes that number a hard limit.
  - Communities at different resolutions are not nested, so it gives no laminar cuts.
  - It suffers from the resolution limit.
  - It builds its own degree null into the objective, which would blur the comparison with the
    configuration null.
- **Spectral hypergraph coarsening (HyperEF-style), rejected.** It controls a coarsening ratio, not
  exact per-level budgets, and has no semantic term.
- **Clique expansion, rejected.** It splits every multi-member edge into pairs: 9.5 member pairs
  per incidence at ≤2026, and multi-way coarse edges disappear. Prop. 2 and the
  measured merge shares show where it would change decisions.
- **Semantics only, rejected.** Proper-named methods find only their own family (notebook 02). The
  α = 1 ablation scores below the default and below α = 0 on the held-out ruler, but within the
  noise (§9).
- **Rank mixing vs raw mixing.**
  - Raw S and H live on incomparable scales, and H is 0 for 99% of singleton pairs.
  - Ranks make α an interpretable weight. F_H(0) = 0 keeps the structural rank from being nearly
    binary.
  - The cost is that magnitudes inside each signal are lost.
- **Size cap.** It prevents the giant clusters that average linkage produces on sparse data (without a
  cap, 87% of the concept nodes fall into one level-0 super-node at ≤2026). The cost is that sizes are imposed: the cap
  is nearly reached at every level: at ≤2026 the largest super-nodes hold 529, 131 and 33 concept
  nodes, against caps of 530.7, 132.7 and 33.2.
- **Hub removal.**
  - It stops generic terms such as "materials science", "MAE" and "molecular dynamics" from fusing
    unrelated papers.
  - The cost is that hubs are placed by their names alone.
  - The threshold is a parameter: its meaning shifts across snapshots (4 to 11 papers at 0.2), so
    the effective threshold is logged per run.
