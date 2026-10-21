# Formal statement of the method (Deliverable 0)

**SHAC-T:** semantic–hypergraph agglomerative coarsening with temporal coupling.
Implementation: `tkh/coarsen.py` (T4 collapse), `tkh/hierarchy.py` (method),
`scripts/build.py` (pipeline). Parameters: the `[method]` section of `configs/default.toml`.

_Status: draft. The sections marked **[results]** are filled in once the evaluation
(T6) has been run._

## 1. Input and notation

- **Snapshots.** Cutoffs t ∈ {2020, 2022, 2024, 2026}. An edge belongs to snapshot t iff
  its provenance article has year ≤ t. A node belongs to t iff it has a provenance article
  or an incident edge with year ≤ t (`tkh/io.py`).
- **Items.** V_t = the concept nodes of snapshot t (types method, task, problem,
  technique, component, dataset, metric), n_t = |V_t|. At ≤2026, n_t = 3980.
  All other nodes (article, author, claim, cited_work, future_topic) are *anchored* (§5).
- **Clustering hypergraph** G_t = (V_t, E_t):
  - E_t holds the snapshot's edges with relation in addresses, solves, extends,
    uses_component, uses_technique, evaluated_on, restricted to V_t;
  - hubs (concept nodes in more than `hub_frac` = 20% of the snapshot's papers) are
    removed from every edge;
  - edges left with fewer than 2 members are dropped;
  - each remaining edge e has weight w_e = 1/(|e| − 1).

  `cites`, `claims`, `presents`, `authored_by` and `proposes_future_work` never enter
  G_t. Citations are therefore free to serve as the held-out signal in the evaluation
  (T6, E1a).
- **Text.** z_v = the mean-centred, L2-normalised projection of node v's name and
  aliases. The projection is a character 3–5-gram TF-IDF followed by a deterministic
  truncated SVD (100 dimensions), fitted on V_t of each snapshot separately, so no text
  from later snapshots is used.
- **Budgets.** N_0 < N_1 < N_2 = 15 < 60 < 240. Level 0 is the coarsest.

## 2. Output

For each t, partitions P_{t,0}, …, P_{t,2} of V_t with:
- |P_{t,k}| = min(N_k, n_t);
- P_{t,k+1} refines P_{t,k} (laminar).

Each anchored node is added to its anchor's super-node at every level. The partitions
are therefore partitions of the whole snapshot, and P1 (laminarity) and P2 (budgets)
hold over all nodes. Super-node ids and the event log come from
`tkh/temporal.match_and_name`.

## 3. Objective

SHAC-T has no global objective that it optimises. That problem would be a constrained
hierarchical partition problem; even its single-level, unconstrained versions
(modularity, normalised cut) are NP-hard. The method is defined instead as a
**deterministic greedy procedure with a stepwise criterion**, applied level by level from
the finest level to the coarsest.

**Level k of snapshot t.**
- **Start.** The items are the super-nodes of P_{t,k+1}, or the singletons of V_t when
  k is the finest level.
- **Step.** Repeat: merge the feasible pair (A, B) maximising s_t(A, B), until
  min(N_k, n_t) items remain. Then P_{t,k} is the result.

**Feasibility (size cap).** |A| + |B| ≤ c_{t,k} = ρ·n_t/N_k, with sizes counted in
concept nodes.

**Score.**

    s(A, B)   = α·F_S(S(A, B)) + (1 − α)·F_H(H(A, B))
    s_t(A, B) = (1 − γ)·s(A, B) + γ·Π(A, B)   if A and B both contain nodes of snapshot t−1
              = s(A, B)                         otherwise

- **Semantic term.** S(A, B) = ⟨z̄_A, z̄_B⟩, where z̄_A is the mean of z_v over A. This
  equals the average pairwise cosine between members of A and members of B.
- **Structural term (native).** H(A, B) = Σ_{e : A∈e, B∈e} w_e / √(d_A d_B), with
  d_A = Σ_{e∋A} w_e, computed on the **current collapsed incidence**. Here "A ∈ e" means
  that e has at least one endpoint in A (§4).
- **Reconciliation.** F_S and F_H are the mid-rank empirical CDFs of S and H over all
  item pairs, fitted once at the start of each level. They put both signals on a common
  scale, the percentile rank in [0, 1], before mixing.
- **Temporal term.** Π(A, B) is the fraction of pairs (a, b) ∈ (A ∩ V_{t−1}) × (B ∩ V_{t−1})
  that shared a super-node at level k in snapshot t−1. This is the evolutionary
  clustering "snapshot cost" of Chakrabarti et al. (KDD 2006), in the
  preserving-cluster-membership form of Chi et al. (KDD 2007), used as a merge prior.

**Ties.** Scores are rounded to 1e-9, and ties go to the smaller item index (node ids
sorted), so the build is deterministic.

## 4. Hypergraph-native structure and the T4 collapse rule

**Collapse.** After merges, a fine edge e with arity n has its endpoints in λ_e
distinct super-nodes:
- **λ_e = 1 (m = n):** the edge is internal. It is kept as metadata and contributes no
  affinity.
- **1 < λ_e < n:** the edge becomes a coarse edge over λ_e super-nodes, keeping the
  endpoint counts as metadata.
- **λ_e ≥ 3:** it remains one multi-way coarse hyper-edge and is never split into pairs.

Coarse edges are written to `out/<t>/coarse_hyperedges.json`.

**What the rule loses.** Endpoint multiplicity, and which fine members participated
(only the fine edge id is kept).

**Proposition 1 (merge gain).** Let the connectivity cut be C = Σ_e w_e (λ_e − 1).
Merging A and B reduces C by exactly Σ_{e : A∈e, B∈e} w_e. *Proof:* an edge with
endpoints in both A and B loses one distinct super-node; no other edge changes. ∎

H is therefore the cut reduction normalised by √(d_A d_B), a Salton-type normalisation
that stops large or high-degree super-nodes from absorbing everything. The test
`test_merge_gain_equals_connectivity_cut_reduction` checks the identity on 50 random
cases.

**Proposition 2 (singleton equivalence).** At singletons, H(a, b) = Σ_{e∋a,b} w_e/√(d_a d_b),
which is the normalised weight of the clique expansion with w_e = 1/(|e| − 1). Native
and projection scores therefore coincide at the first merge. They differ once a
super-node holds two endpoints of one edge:
- the native H counts that edge once per pair of super-nodes (presence, λ);
- the projection (`structure = "projection"`, the average linkage of the singleton
  clique weights) counts it once per member pair.

This is the controlled comparison T2 asks for. The projection variant differs from the
native method in that one place only (test
`test_native_and_projection_agree_at_singletons_and_diverge_later`).

**Lemma (cap feasibility).** If ρ ≥ 2, a feasible pair exists whenever K > N_k items
remain. *Proof:* the two smallest items have total size ≤ 2n_t/K < 2n_t/N_k ≤ c_{t,k}. ∎

Hence every level reaches exactly min(N_k, n_t) super-nodes (test
`test_cap_rho_two_always_reaches_the_target`). Configurations with ρ < 2 are rejected.

## 5. Anchoring of non-concept nodes

Each non-concept node v in snapshot t joins the super-node of one concept node a(v) of
snapshot t:

| Node type | Anchor |
|---|---|
| claim | the method member of its `claims` edge, else the presented method of the paper |
| cited_work | the presented method of the earliest citing paper (year, then id) |
| article | its own presented method |
| author, future_topic | the presented method of the earliest of their papers |

- **No name matching.** No anchor uses name matching, so cited works do not leak into
  clusters through text.
- **Excluded from metrics.** Anchored nodes are excluded from every metric
  (`concept_only`).
- **Failure is loud.** A node with no anchor raises an error; none occurs in the data.

## 6. Guaranteed vs measured

| Property | Status |
|---|---|
| P1 laminarity | guaranteed: level k merges level-(k+1) super-nodes; checked by `validate.py` |
| P2 budgets | guaranteed: exactly min(N_k, n_t) super-nodes (lemma, §4); checked by `validate.py` |
| Giant-cluster bound | guaranteed: no super-node exceeds ρ·n_t/N_k concept nodes |
| Hypergraph-native structure at coarse levels | guaranteed: H is computed on the collapsed incidence (Prop. 1) |
| Determinism | guaranteed: deterministic SVD, deterministic tie-breaking; tested |
| No future information | guaranteed: snapshot-t inputs only (G_t, V_t, the text projection fitted on V_t, P_{t−1}) |
| P3 coherence, P4 stability, P5 temporal consistency, P6 faithful labels | measured (T6) **[results]** |

## 7. Complexity

Per level, with n items, m fine edges and d = 100 text dimensions:
- **Initialisation:** O(n²(m + d)) for the score matrix, plus O(n² log n) for the CDFs.
- **Each merge:** O(n(m + d)) to recompute one row and refresh the cached best partners.
  There are n − N_k merges.

Memory is O(n²), for the dense score matrix. At ≤2026, n = 3980 and m = 554; the four
snapshots take about 25 s on a laptop. That is enough for the sweep and the nulls
(about 130 builds). A sparse heap would be needed above roughly 20k items.

## 8. Parameters

| Parameter | Default | Role | Selection |
|---|---|---|---|
| α | 0.5 | semantic vs structural weight | selected on E1a, half A, by the one-SE rule **[results]** |
| γ | 0.5 | temporal prior | pre-registered; γ = 0 reported as an ablation |
| ρ | 2 | size cap | pre-registered; ρ = ∞ reported as an ablation |
| structure | native | native vs projection H | pre-registered; projection reported as an ablation |
| lsa_dim | 100 | text projection rank | pre-registered |
| hub_frac | 0.2 | hub removal threshold | pre-registered; hubs logged in `out/run_info.json` |

All six can be overridden from the command line: `scripts/build.py --param alpha=0.25`.

## 9. Assumptions

- **A1.** Concept relations within a paper are evidence of relatedness. The data has one
  star per paper, so structure is mostly paper co-occurrence. The structural signal is
  therefore expected to rebuild papers. This is measured (paper purity, notebook 03) and
  not hidden.
- **A2.** Name strings carry weak but real semantic signal (notebook 02: useful for
  generic tasks and metrics, useless for proper-named methods). This is why α is
  bounded and selected, not fixed at 1.
- **A3.** Membership in the previous snapshot is a valid prior for the current one
  (P5). γ trades stability against adaptation.
- **A4.** The provenance year is the time a node and an edge enter the graph.

## 10. Trade-offs and rejected alternatives

- **Greedy agglomeration vs global optimisation.** Agglomeration controls the budgets
  exactly, gives laminarity by construction, and is deterministic and explainable merge
  by merge. The cost is that early merges cannot be undone and there is no optimality
  guarantee.
- **h-Louvain / hypergraph modularity (rejected).** They give no control over the
  number of communities, which P2 requires. They suffer from the resolution limit. And
  on per-paper stars they would reward exactly the paper bundles that A1 warns about.
- **Attributed hypergraph SBM (discussed, not used).** It is principled and could use
  names as attributes. But at about 4k nodes and about 550 edges, with 88% of concept
  nodes in a single edge, inference is badly under-determined. It is also not natively
  hierarchical with fixed budgets.
- **Clique expansion.** It is kept only as the `projection` ablation (Prop. 2), so that
  what it discards can be measured.
- **Rank-normalised mixing vs raw mixing.** Raw S and H live on incomparable scales (H
  is 0 for about 99% of pairs). Percentile ranks make α interpretable. The cost is that
  magnitudes inside each signal are lost.
- **Size cap.** It prevents the giant clusters that pure average linkage produces on
  sparse data. The cost is that sizes are partly imposed, not discovered. ρ = ∞ is
  reported as an ablation.
- **Hub removal.** It stops generic domain terms and metrics from fusing unrelated
  papers. At ≤2026 the hubs are "materials science", "computational chemistry",
  "computational materials science", "computational physics", "molecular dynamics" and
  "MAE". The cost is that the hubs' own placement is decided by
  text only.

## 11. Results **[results]**

To be completed: the selected α with its evidence, and the model vs null comparison on
E1–E4.
