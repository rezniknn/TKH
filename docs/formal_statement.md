# Formal statement of the method (Deliverable 0)

**SHAC:** semantic–hypergraph agglomerative coarsening, a budget-constrained hierarchical
agglomeration of the concept nodes that scores merges on the collapsed hypergraph and on name
semantics.

| Part | Code |
|---|---|
| Method (T2 hierarchy) and anchoring of non-concept nodes (§5) | `tkh/hierarchy.py` |
| Clustering hypergraph and T4 collapse | `tkh/coarsen.py` |
| Snapshots and data loading | `tkh/io.py` |
| Name texts and concept types | `tkh/semantic.py` |
| Persistent ids and temporal events | `tkh/temporal.py` |
| Placeholder labels (levels 0–1) | `tkh/label.py` |
| Output assembly | `tkh/export.py` |
| Configuration | `tkh/config.py`, `configs/default.toml` |
| Run | `tkh/pipeline.py`, `python -m tkh build` |
| Null models | `tkh/null.py`, `python -m tkh null` |
| Output checks (schema, P1, P2, cutoff, labels present, events) | `validate.py` |
| Held-out P3 check and experiments (evaluation, outside the method package) | `eval/coherence.py`, `eval/experiments.py`, `python -m eval p3`, `python -m eval sweep` |

**Configuration.**
- The method parameters (`alpha`, `rho`, `edge_weight`, `hub_frac`, `lsa_dim`) are in `[method]` of
  `configs/default.toml`. Unknown keys are an error.
- Budgets are in `[hierarchy]` and cutoffs in `[snapshots]`.
- `python -m tkh` overrides them with `--param k=v`, `--budgets` and `--cutoffs`.
- Each run writes the resolved values to `<out>/run_config.toml`.

**Where the numbers come from.**
- Every result in §§3, 7, 8 and 9 comes from `out/run_info.json`, `out/metrics.json`, `out/sweep.json` or
  `out/<t>/coarse_hyperedges.json`, produced by `make all` and `make sweep`.
- Data facts cite notebooks 01–03.

## 1. Input and notation

- **Snapshots.** The default cutoffs are t ∈ {2020, 2022, 2024, 2026}. They are configurable, sorted
  ascending, and must be at least three distinct years.
  - An edge is in snapshot t iff its paper is from year ≤ t.
  - A node's entry year is the earliest year among its provenance papers and the papers of its incident
    edges; the node is in t iff that year is ≤ t (`tkh/io.py`).
  - Notebook 01 §2 shows why the export's other year fields leak.
- **Items.** V_t is the set of concept nodes of snapshot t, of types method, task, problem, technique,
  component, dataset and metric. These are exactly the member types of the method-centred relations
  (notebook 03 §1). n_t = |V_t| = 1018, 1464, 2829 and 3980.
  - **Hubs stay in V_t.** They count in n_t and in the size cap, and they are clustered. They are removed
    only from the edges, so a hub has hyperdegree 0 and H = 0 with every item, and only its name places
    it. Items with hyperdegree 0 number 5, 10, 8 and 7: the hubs plus 0, 2, 1 and 1 nodes whose only edges
    were dropped.
  - **Other nodes are anchored after clustering (§5):** articles, authors, claims, cited works and future
    topics.
- **Clustering hypergraph G_t = (V_t, E_t).**
  - E_t holds the snapshot's edges of the six method-centred relations: addresses, solves, extends,
    uses_component, uses_technique and evaluated_on. Members are restricted to V_t and deduplicated.
  - **Hubs are removed from every edge.** A hub is a concept node in more than `hub_frac` of the
    snapshot's papers, i.e. in at least ⌊hub_frac·|papers_t|⌋ + 1 papers.
    - |papers_t| = 16, 22, 38 and 52.
    - A node is "in" a paper if the paper is one of its provenance papers, or the source of any snapshot
      edge incident to it (of any relation).
    - With the default 0.2 the threshold is 4, 5, 8 and 11 papers, giving 5, 8, 7 and 6 hubs.
  - Edges left with fewer than 2 members are dropped, which leaves m_t = 141, 230, 406 and 554 edges.
  - `cites`, `claims`, `presents`, `authored_by` and `proposes_future_work` never enter G_t.
- **Edge weights w_e** (`edge_weight`), computed once per snapshot. |e| is the reduced arity (after
  restriction, deduplication and hub removal).
  - `inverse_size`: w_e = 1/(|e| − 1).
  - `relation_balanced` (default): inverse_size rescaled so that each relation's weights sum to 1.
  - Why the default: under inverse_size alone, evaluated_on carries 70.5%, 79.9%, 84.3% and 85.3% of the
    weight in the four snapshots. It is mostly small benchmark triples, a large share of them from a few
    papers (notebook 03 §5). Any weighting chooses which relation drives the grouping, so the default
    spreads the choice evenly.
- **Text z_v.**
  1. Each node's text is its surface form and aliases joined by " ; ", then cleaned: NFKC, Unicode dashes
     mapped to "-", special spaces mapped to " ", whitespace collapsed.
  2. Over V_t only, a character 3–5-gram TF-IDF is computed (sklearn `char_wb`, lowercased, sublinear tf),
     followed by an SVD to k = min(`lsa_dim`, min(shape) − 1) = 100 dimensions. The SVD is an exact dense
     SVD when min(shape) ≤ 400, and ARPACK with a fixed seed otherwise. On the real snapshots (1018×12410
     up to 3980×23525) it is always ARPACK.
  3. The vectors are then mean-centred over V_t and L2-normalised.
  - Raw TF-IDF chains, LSA does not: in notebook 02's text-only average-linkage trial, raw TF-IDF puts
    99.6% of nodes into one of 15 clusters. That notebook's uncentred, randomised LSA lowers it to
    39–57% over seeds.
- **Never used in G_t or z_v:** titles, claims, future topics, edge attributes, cited works, citations,
  authors and abstracts.
  - **Why** (notebook 03 §8): citations and claims are held-out evidence for the coherence ruler and for
    label judging, and titles are shared by every node of a paper, so they would re-encode "same paper".
  - **Where `claims` and `cites` edges are used** outside the clustering:
    - in entry years and the paper counts for hubs;
    - to anchor claim and cited-work nodes (§5).
- **Budgets.** N_0 ≤ N_1 ≤ … ≤ N_{K−1}: at least 2 positive integers, non-decreasing from level 0 (the
  coarsest). At least 2 are needed because levels 0 and 1 are labelled. The default is (15, 60, 240); the
  brief fixes only N_0 ≈ 10–15.
  - No step assumes particular values. N_k enters only as the stopping target min(N_k, n_t) and through
    the size cap ρ·n_t/N_k.
  - Only the K budgeted levels are written. The singleton level P_K is implicit in `member_ids`.

## 2. Objective

SHAC optimises no global objective. The problem it would face is a hierarchical partition with
hard budgets, and even its single-level, unconstrained relatives (modularity, normalised cut) are
NP-hard. SHAC is instead a **deterministic greedy procedure with a stepwise criterion**. The
criterion is the method, and there is no optimality guarantee.

**Level k of snapshot t**, run from the finest level to the coarsest:
- **Start.** The items are the super-nodes of level k+1, or the singletons of V_t at the finest level.
- **Step.** Repeat: merge the feasible pair (A, B) with the largest s(A, B). Stop when min(N_k, #items)
  items remain.

**Score:**

    s(A, B) = α · F_S(S(A, B)) + (1 − α) · F_H(H(A, B))

- **Semantic term.** S(A, B) = ⟨z̄_A, z̄_B⟩, the dot product of the members' mean vectors, i.e. the
  average pairwise cosine (average linkage).
- **Structural term.** H(A, B) = Σ_{e: A∈e, B∈e} w_e / √(d_A d_B), with d_A = Σ_{e∋A} w_e (0 if
  d_A·d_B = 0).
  - It is computed on the **current collapsed incidence**: A ∈ e iff e has at least one endpoint in A (§3).
  - Its numerator is the reduction of the weighted connectivity cut caused by the merge (Prop. 1).
  - The denominator normalises by hyperdegree, which stops high-degree super-nodes from absorbing
    everything.
- **Reconciliation.**
  - F_S is the mid-rank CDF, F(x) = (#{v < x} + #{v ≤ x}) / 2N, of S over all item pairs at the start of the
    level, including pairs that the cap forbids.
  - F_H is the mid-rank CDF of H over the pairs with H > 0, with **F_H(0) = 0**.
  - Both stay frozen for the level. Values that appear after merges are ranked against the start-of-level
    sample.
  - Ranks put two incomparable scales on [0, 1]. A pair that shares no edge gets no structural credit and
    can win only on semantics, at weight α.
  - The convex mix is the explicit structure-versus-content trade-off that P3 asks for: α = 0 is structure
    only, α = 1 semantics only.
- **Feasibility.** The size cap is |A| + |B| ≤ c_{t,k} = ρ · n_t / N_k.
  - Sizes and n_t count concept nodes, hubs included; anchored nodes do not count.
  - ρ ≥ 2, or ρ = ∞ for no cap.
  - With the defaults, c = 135.7 / 33.9 / 8.5 at ≤2020 and 530.7 / 132.7 / 33.2 at ≤2026.
- **After a merge.** B is folded into A:
  - member vectors, sizes and per-edge endpoint counts are summed (C_A ← C_A + C_B);
  - presence is reset to X_A = [C_A > 0], and d_A is recomputed;
  - only A's row of scores is recomputed; B's row and column are removed.
- **Ties.**
  - S and H are rounded to 1e-12 before ranking, so values that differ only by floating-point error tie
    exactly. Scores are rounded to 1e-9.
  - Among the maximal scores, the lowest-indexed item and then its lowest-indexed partner win, and the
    higher index is merged into the lower.
  - Items are ordered by node id at the finest level, and by their smallest member at coarser levels.
  - The build is deterministic.
- **Diagnostics.** `run_info.json` records per snapshot and level: `budget`, `super_nodes`, `cap`,
  `max_size`, `singletons`, and the merge counters `merges`, `linked` (the two super-nodes share an edge)
  and `multi_endpoint` (Prop. 2).

**Why a joint score rather than two stages.** The two signals fail in different places.
- **Names alone cannot relate proper-named methods across families.**
  - On raw character n-grams, SchNet's best name neighbour (ænet) scores 0.11 (notebook 02).
  - In z_v its nearest names are other "-Net" models at about 0.9, which match on the suffix, not on method
    family.
- **Structure alone mostly links nodes of one paper.** 94% of concept nodes at ≤2026 (95–96% earlier)
  occur in a single paper, and cross-paper evidence is a few bridges (notebook 03 §§3, 5).

A two-stage scheme, structure first and then semantics, would freeze paper bundles before names
could join them across papers. A single score lets either signal decide each merge.

## 3. T4: what a hyper-edge becomes, and how the method uses it

**Which edges are collapsed.** Exactly E_t of §1: the six relations, members restricted to V_t,
deduplicated, hubs removed, at least 2 members left. The arity n is this reduced arity (the `arity`
field of the records). The other relations are not collapsed and have no coarse-level representation.

**Classes.** A fine edge e has endpoint counts c_S(e) over the super-nodes S. Two quantities describe it:
- λ_e = #{S : c_S(e) > 0}, the number of super-nodes it touches;
- m_e = max_S c_S(e), the brief's m, the largest number of its endpoints in one super-node.

Each edge is in exactly one class (`tkh/coarsen.py`, `collapse`):

| Class | Condition | Brief's case | Coarse edge | In the score |
|---|---|---|---|---|
| **internal** | λ_e = 1 | m = n | links no super-nodes; kept as a record | drops out of every H numerator; its weight still counts in d_A |
| **partial** | 2 ≤ λ_e < n | 1 < m < n | one coarse edge over the λ_e super-nodes; c_S(e) kept as metadata | counted once per super-node it touches (presence) |
| **uncollapsed** | λ_e = n | m = 1 | the fine edge, one endpoint per super-node | as for partial |

Separately, an edge is flagged **multi-way** when λ_e ≥ 3, which is the brief's "three or more distinct
super-nodes". The flag is not a class: a multi-way edge is partial or uncollapsed.
- It stays one hyper-edge and is never split into pairs.
- Its weight enters H for every pair of super-nodes it touches.
- The connectivity cut charges it once, as w_e(λ_e − 1). So merging any two of its super-nodes lowers the
  cut by exactly w_e, whatever its arity (Prop. 1).

**Why presence, not endpoint counts.**
- Every clustering edge is a star around one paper's method (A1).
- A score that counted endpoints, e.g. c_A(e)·c_B(e), would pay a super-node more the more of that paper's
  star it had already absorbed. That favours merges within a paper and strengthens paper bundling (§8).
- Presence counts each edge once per super-node. The merge gain is then exactly the reduction of the
  connectivity cut Σ_e w_e(λ_e − 1), the standard (λ − 1) objective of hypergraph partitioning.
- An internal edge keeps its weight in d_A. This damps super-nodes that have already absorbed much of
  their incident weight.

**How the method applies it.**
- The score is computed from exactly this collapsed incidence, which is updated after every merge
  (`_Level.merge`).
- The weights w_e are fixed: computed once per snapshot, never re-normalised, independent of λ_e.
- Parallel coarse edges, i.e. fine edges over the same set of super-nodes, are not merged. They stay
  separate columns and records. Because H and d_A are sums over edges, the scores are the same as with one
  edge of summed weight.
  - At ≤2026, the edges in such groups number 203 (level 0), 168 (level 1) and 191 (level 2).

**What the rule loses:**
- endpoint multiplicity in the score, which uses presence only;
- which fine members took part, kept only as the fine edge id;
- a coarse edge's identity across levels: there is one record per fine edge and level, and no coarse-edge
  id;
- merging of parallel coarse edges, which stay separate records even when they share a relation.

**Records** (`out/<t>/coarse_hyperedges.json`).
- Per level k, the file has `{"summary": {internal, partial, uncollapsed, multiway, edges}, "edges": [...]}`.
- Each edge has one record: `{fine_edge, relation_type, arity, weight, lambda, class, multiway,
  endpoint_counts: {super-node id: c_S(e)}}`. The super-node ids are those of `hierarchy.json`.
- The records come from the same incidence and partition as the score.
- No schema covers the file, and `validate.py` does not check it.

**At ≤2026**, of the 554 edges (the three classes sum to 554; the multi-way column overlaps them):

| Level | Internal | Partial | Uncollapsed | Multi-way (partial + uncollapsed) |
|---|---|---|---|---|
| 0 | 311 | 217 | 26 | 59 (46 + 13) |
| 1 | 218 | 289 | 47 | 105 (75 + 30) |
| 2 | 82 | 381 | 91 | 203 (134 + 69) |

**Proposition 1 (merge gain).** Let C = Σ_e w_e (λ_e − 1). Merging A and B reduces C by exactly
Σ_{e: A∈e, B∈e} w_e. *Proof:* an edge with endpoints in both A and B loses one distinct super-node,
and no other edge changes. ∎ This is tested on 50 random cases.

**Proposition 2 (where native and clique scores differ).**
- **Numerators.** At singletons, the numerator Σ_{e∋a,b} w_e is the weighted clique-expansion weight of
  the pair. The two numerators, Σ_e w_e [c_A,e > 0][c_B,e > 0] and the clique form Σ_e w_e c_A,e c_B,e,
  differ only once a super-node holds two or more endpoints of a shared edge. Native H counts that edge
  once per pair of super-nodes; the clique view counts it once per member pair.
- **Denominators.** The normaliser is the hyperdegree d_A (each incident edge once), not a clique-graph
  degree. So H is a cosine on the incidence matrix, and the two scores can differ even without shared
  multi-endpoint edges.
- **How often.** At ≤2026, a shared edge with two or more endpoints on one side occurs in **39 of 45, 174
  of 180 and 2287 of 3740 merges** (87%, 97%, 61%) at levels 0, 1 and 2 (`multi_endpoint`).
  - The two scores therefore differ for most chosen merges.
  - Whether clique linkage would have chosen differently is not measured: no pairwise projection is built.

**Lemma (cap feasibility).** If ρ ≥ 2 and K > N_k items remain, a feasible pair exists. *Proof:*
the two smallest items have total size ≤ 2n_t/K < 2n_t/N_k ≤ c_{t,k}. ∎
- Every level therefore has exactly min(N_k, n_t) super-nodes, for any budget list (tested on five
  lists, including N_k > n_t).
- ρ < 2 is rejected.
- If no feasible pair remained, the level would stop with an error; the lemma rules this out.

## 4. Output

For each t, the output is a set of partitions P_{t,0}, …, P_{t,K−1} of the whole snapshot.
- **Sizes:** |P_{t,k}| = min(N_k, n_t) super-nodes.
- **Nesting:** P_{t,k+1} refines P_{t,k}. Level k starts from level k+1's super-nodes and can only merge
  them. Export finds each parent by containment and raises on a non-laminar input.
- **Anchored nodes** are added to their anchor's super-node at every level.
- **Ids and the event log** come from overlap matching (`tkh/temporal.py`).

**Labels** (`tkh/label.py`) are deterministic placeholders, prefixed "[placeholder]", at levels 0 and 1
only. Level ≥ 2 labels are null.
- **Label:** the most common concept type, followed by the two concept members that occur in the most
  papers of snapshot t. Ties are broken by name, and each name is cut to 30 characters.
- **Gloss:** the concept-node count and the mix of the three most common types.

**Files**, per run directory:

| File | Content | Checked by `validate.py` |
|---|---|---|
| `<t>/hierarchy.json` | `{cutoff, levels, budgets, supernodes: [{id, level, parent_id, member_ids, label, gloss}]}` | yes, against `schema/hierarchy.schema.json` |
| `<t>/coarse_hyperedges.json` | the T4 records (§3) | no |
| `temporal_events.json` | `{events: [...]}` | yes, against `schema/temporal_events.schema.json` |
| `run_config.toml` | the resolved inputs, cutoffs, budgets and `[method]`; paths relative to the run directory | used as the validator's config |
| `run_info.json` | parameters, budgets, cutoffs, runtime, and diagnostics per snapshot and level | no |

## 5. Anchoring of non-concept nodes

Each non-concept node v of snapshot t joins the super-node of one concept node a(v) of V_t, hubs
included.

| Node type | Anchor |
|---|---|
| claim | the first method-type concept member of one of its `claims` edges; else that edge's paper's presented method |
| cited_work | the presented method of the earliest paper (by year, then id) that cites it |
| article | its own presented method |
| author, future_topic, and any node the rules above do not cover | the presented method of its earliest paper, among its provenance papers and the papers of its snapshot edges |

- **Which presented methods count.** Only papers whose presented method is a concept node of V_t.
- **At ≤2026:**
  - 478 of the 690 claims are anchored through a method member, and 212 through the presented method;
  - every cited work is cited in its snapshot.
- **No names are used**, so cited works cannot reach clusters through text.
- **Anchored nodes are not clustered** and do not count toward the cap.
- **Hubs as anchors.** At ≤2022 one presented method is a hub (meth_00030), and 46 nodes are anchored to
  it.
- **A node with no anchor raises an error.** None occurs in the data.

## 6. Guaranteed vs measured

| Property | Status |
|---|---|
| P1 laminarity | **by construction** (each level merges the next finer level's super-nodes); `validate.py` checks nesting, coverage and single parentage |
| P2 budgets | **by construction**: exactly min(N_k, n_t) per level (lemma, ρ ≥ 2); `validate.py` checks ≤ N_k and non-empty levels |
| Hyper-edge fidelity (P4, T4) | **by construction**: H is computed on the collapsed incidence (Prop. 1), and multi-way edges stay whole |
| Size bound | **by construction** for finite ρ: no super-node at level k has more than ⌊ρ·n_t/N_k⌋ concept nodes; anchored nodes are not counted; logged in `run_info.json`, not checked by `validate.py` |
| Determinism | **by construction**: ARPACK with a fixed seed, rounding of S, H and scores, lowest-index ties, and sorted processing. Tested by building twice on the fixture and on the real ≤2020 snapshot. This shows repeatability in one numerical environment, not across machines or BLAS builds. |
| No future information | **by construction** for structure and membership (edges, hub counts, LSA fit and anchoring use snapshot t only; `validate.py` checks member cutoffs). Labels count papers within t, but their text uses export-wide names, so labels and text features rely on A4. |
| P3 semantic coherence | **empirical** (§8), controlling for publication period. Exact filter, ≤2026: levels 0 and 1 beat both nulls under every period scheme; level 2 does not under two schemes. No cell of an earlier snapshot is significant under every scheme. |
| P5 temporal stability | not addressed: matching does identity bookkeeping only |
| P6 faithful labels | not addressed: deterministic placeholders at levels 0–1; `validate.py` checks only that they are non-empty; faithfulness is not evaluated |

## 7. Complexity

Per level, with n items at the start of the level, m fine reduced edges and d = `lsa_dim`:
- **Initialisation:** O(n²(m + d)) time for the score matrix, plus O(n² log n) for the rank CDFs.
- **Each merge:** O(n(m + d)) to rescore the merged item.
  - A row whose best partner was one of the two merged items is rescanned at O(n). The number of such rows
    is unbounded, so the worst case is O(n²) per merge.
  - At ≤2026: 7870 rescans over 3965 merges, a mean of 2.0 per merge and at most 33.
- **Merges per level:** n − min(N_k, n): 3740, 180 and 45 at ≤2026.
- **m is the same at every level.** A coarser level's incidence has the same fine-edge columns.
- **Text:** the TF-IDF and SVD run once per snapshot (12k–24k character n-gram features).
- **Memory:** O(n²), dominated by the dense score matrix and the arrays used to build it. At n = 3980 the
  score matrix alone is 127 MB, and the measured peak resident memory of the ≤2026 build is about 2 GB. The incidence is O(nm), about
  18 MB dense.

**Runtime.** The full build of four snapshots takes 28.5 s in one process (`runtime_s`, measured after
loading).
- The finest level of the largest snapshot dominates.
- Per-snapshot time grows roughly with n_t².
- Much larger graphs would need a sparse candidate set.

The evaluation is separate: `make p3` (§8) runs 99 null rebuilds per snapshot on 8 worker processes,
and `make sweep` (§9) takes about 6 min on 8 cores.

## 8. Null models and the held-out P3 check

**Null model** (`tkh/null.py`): the **type- and period-preserving hypergraph configuration model**.
- It is the degree- and arity-preserving shuffle that the brief names (T6), and the standard structural
  null for hypergraph clustering (Chodrow 2020, vertex-labelled).
- **Sampling.** Curveball trades on the edge tails (members[1:]) of the six clustering relations only.
  - Edges are stratified by relation and by the cutoff interval of the edge's paper.
  - Each stratum gets 10·|stratum| random pair trades.
  - In a trade, the tail members two edges share, or that equal the partner's head members[0], stay put.
    The rest are pooled per member type, shuffled and dealt back, so each edge keeps its type counts.
- **Preserved:** each node's degree per relation, interval and type; each edge's arity, type mix, head
  members[0] (never traded), paper and year.
  - Hence every snapshot keeps its node set, and all other relations are untouched.
  - The node-set check runs in `python -m tkh null` and the tests. The rebuilds inside `eval/experiments.py`
    skip it.
- **Mixing:** 86% of the incidences move.
- **Use.**
  - The null graph runs through the same pipeline with the same parameters and the real snapshot's hub
    sets, so `hub_frac` means the same thing in both. Its output passes `validate.py` (`make null`).
  - One shuffle per seed covers the whole export, so each snapshot of a null is a prefix of that one
    shuffle.
- **What it measures.** The null keeps the names, so it measures what structure adds beyond degrees,
  given the semantics.
- **Companion:** random labels, i.e. concept-node ids permuted within (type, entry interval) over the
  evaluated tree. This keeps the laminar structure and every size.

**Held-out ruler** (`eval/coherence.py`). P3 asks for closeness in meaning, and the proxy is
bibliographic coupling, a signal no clustering input contains. The evaluator fixes it, computes it on
the real export, and applies it identically to every configuration and null.
- **Coupling c_pq:** the IDF-weighted Salton cosine of two papers' cited-work sets. IDF is over the
  snapshot's citing papers.
- **Names:** normalised surface forms and aliases (letters and digits of any script), i.e. the names the
  method's text sees.
- **Residual filter:** drop a paper's cited works named like one of its own non-hub concept nodes, so that
  "extends X / cites X" does not count.
  - *exact*: equal normalised names. It removes 38, 73, 162 and 260 citations per snapshot.
  - *fuzzy*: also containment, for names of ≥ 4 characters. It removes 56, 107, 222 and 342.
- **Pairs:** only **no-overlap** pairs, i.e. citing papers sharing no concept node and no concept name,
  excluding the evaluator's hubs. Their share is fixed at 0.4, independent of `hub_frac`. On these pairs,
  shared structure explains nothing.
- **Co-assignment:** a_pq = Σ_S n_S(p) n_S(q) / (n_p n_q) per level.
- **Lift:** Σ a·c / (Σ a · mean c); 1 means chance.
- **Period control.** Papers of the same period cite the same work, and both nulls keep the period
  composition, so an unadjusted lift rewards "same era".
  - The period-adjusted lift is Σ a·c / Σ a·e (indirect standardisation), where e_pq is the mean coupling
    of the no-overlap pairs in the same stratum.
  - A stratum is the unordered pair of the two papers' periods, or the year gap for the gap scheme.
  - **Primary scheme:** the snapshot cutoff intervals, i.e. the strata within which random labels permute.
    After adjustment, both null means fall to about 1.0.
  - **Sensitivity:** bins of 1, 2 and 3 years, and the absolute year gap. A result is **robust** only if it
    holds under every scheme.
- **p-values:** one-sided, p = (1 + #null ≥ obs)/(R + 1). With R = 99 null rebuilds and R = 999
  random-label draws, the floors are 0.01 and 0.001.
- **Every snapshot is evaluated on its own.** The ruler, the pairs and the random labels are rebuilt at
  each cutoff, and the null hierarchy is rebuilt at each cutoff from the seed's null graph.
- **Command:** `make p3`, i.e. `python -m eval p3 --run out`.
  - It reads the run's own `run_config.toml`, refuses null runs, and writes `out/metrics.json`.
  - A new build into the same directory deletes `metrics.json`.

**Coverage per snapshot (exact filter):**

| Snapshot | Citing papers | No-overlap pairs | Coupled pairs | Interval strata |
|---|---|---|---|---|
| ≤2020 | 9 | 18 | 5 | 1 |
| ≤2022 | 14 | 34 | 11 | 3 |
| ≤2024 | 25 | 100 | 21 | 6 |
| ≤2026 | 37 | 253 | 58 | 10 |

**Period-adjusted coherence** (primary scheme, exact filter; `out/metrics.json`). Each cell gives the lift
[95% paper-bootstrap CI], and for each null its mean and p.

| Snapshot | Level | Lift [95% CI] | Configuration null | Random labels | Robust across period schemes |
|---|---|---|---|---|---|
| ≤2026 | 0 (15) | 1.46 [0.79, 2.07] | 1.01, **0.01** | 1.01, **0.001** | **yes**: 1.21–1.46, both nulls at their p floor under every scheme |
| ≤2026 | 1 (60) | 1.26 [0.66, 2.08] | 1.01, **0.01** | 1.02, **0.001** | **yes**: 1.15–1.32, both nulls at their p floor under every scheme |
| ≤2026 | 2 (240) | 1.04 [0.43, 1.81] | 1.03, 0.36 | 1.03, 0.38 | no: 1.36–1.41 with year bins (both nulls at their floor); 1.19 with year gap (p 0.16 and 0.32) |
| ≤2024 | 0 | 0.87 [0.11, 3.01] | 1.01, 1.00 | 1.00, 1.00 | no evidence under any scheme |
| ≤2024 | 1 | 1.43 [0.04, 2.86] | 1.02, **0.01** | 1.01, **0.001** | no: significant only with interval and year-gap strata; 0.92–1.08 with year bins |
| ≤2024 | 2 | 0.81 [0.00, 2.38] | 1.02, 1.00 | 1.02, 1.00 | no evidence |
| ≤2022 | 0 | 0.41 [0.03, 1.93] | 1.00, 1.00 | 0.99, 1.00 | no evidence |
| ≤2022 | 1 | 1.52 [0.19, 4.61] | 1.00, **0.01** | 1.01, **0.001** | no: significant only with interval and 3-year strata; 0.98–1.11 with 1- and 2-year bins and year gap |
| ≤2022 | 2 | 0.96 [0.02, 2.23] | 1.08, 0.87 | 1.02, 0.75 | no: significant only with 1-year bins (1.20) |
| ≤2020 | 0 | 0.03 [0.00, 4.93] | 0.96, 1.00 | 0.99, 1.00 | not evaluable (5 coupled pairs, 1 stratum) |
| ≤2020 | 1 | 0.16 [0.00, 6.98] | 0.96, 1.00 | 0.98, 1.00 | not evaluable (year bins give 2.5–3.8 at the p floor, on 5 coupled pairs) |
| ≤2020 | 2 | undefined (no no-overlap pair co-assigned) | – | – | not evaluable |

The unadjusted lifts, the other period schemes and the fuzzy filter are all in `metrics.json`. Under
the fuzzy filter, all three levels at ≤2026 beat both nulls under every scheme.

**Reading:**
- **Robust evidence of P3: ≤2026, levels 0 and 1.** There, the hierarchy groups the concepts of
  citation-coupled papers within the same period more than a degree-preserving null rebuild or a random
  relabelling does.
- **The period control is essential.**
  - Without it, level 1 does not beat random labels (p = 0.19), and level 2 falls below both nulls (1.08
    against 1.39 for the configuration null and 1.43 for random labels): the nulls gain from same-period mixing.
  - With it, the nulls fall to about 1.0 and level 2 sits at chance (1.04). Whether level 2 looks
    significant depends on the scheme, so it is not robust.
- **Level 2 mostly rebuilds per-paper bundles** (A1; median paper purity 1.0). So few different papers are
  related at that level that the result hinges on how pairs are stratified.
- **The earlier snapshots cannot show P3.**
  - They have 5–21 coupled pairs, and at ≤2022 and ≤2024 three pairs carry 81–96% of Σ a·c.
  - Their significant level-1 cells depend on the scheme.
  - ≤2020 is a single period stratum with 18 pairs.
- **Two kinds of uncertainty.**
  - The null tests are conditional on each snapshot's papers: the ruler is fixed and only the partition
    varies.
  - Over papers, the bootstrap CIs are wide and include 1 everywhere.
  - So the evidence is "better than chance for this corpus", not a population estimate.

## 9. Parameters and selection

| Parameter | Default | Role |
|---|---|---|
| α (`alpha`) | 0.5 | weight of the semantic rank |
| ρ (`rho`) | 2 | size-cap factor (≥ 2, or inf) |
| `edge_weight` | relation_balanced | edge weighting (§1) |
| `hub_frac` | 0.2 | hub threshold as a share of the snapshot's papers (1.0 = no hubs) |
| `lsa_dim` | 100 | text projection rank |

- **Overrides.**
  - `--param k=v ...` overrides single parameters; values are JSON-decoded.
  - `--budgets` and `--cutoffs` override the levels and snapshots; `--graph` and `--articles` override the
    inputs.
  - Example: `python -m tkh build --param alpha=0.25 hub_frac=0.3 --budgets 10 40 160 --out /tmp/run`.
  - Without `--out`, the build overwrites `out/`.
- **Strict parsing.** Unknown parameters are an error.
- **Run record and validation.**
  - Each build writes its resolved `run_config.toml`, with input paths relative to the run directory.
  - Validation is a separate step: `validate.py <out> --config <out>/run_config.toml`. It runs in
    `make validate`, in `make all` (build → validate → p3 → test) and in `make null`.

**Selection protocol** (`make sweep`, `out/sweep.json`; latest snapshot only).
- **Grid:** α ∈ {0.25, 0.5, 0.75} × ρ ∈ {2, 4} × edge_weight ∈ {inverse_size, relation_balanced} ×
  hub_frac ∈ {0.1, 0.15, 0.2, 0.3, 1.0}, i.e. 60 configurations. At ≤2026 these hub fractions give 20, 10,
  6, 2 and 0 hubs.
- **Ablations:** α = 0 and α = 1, reported but not selectable.
- **Base:** the configured `[method]`, which serves as the fallback and the reported default.
- **Splits:** 20 seeded halves (A, B) of the cited works, stratified by citation count. A half's ruler
  keeps the 34–37 papers that cite a work in it.
- **Rule per split.**
  1. On half A, take the best configuration by its mean lift over levels. This is the unadjusted, exact
     lift, so it is period-confounded (A7).
  2. Among the configurations within one SE of it (the best one's paper bootstrap, B = 200), pick the one
     closest to the default. Closeness compares α, then ρ, then edge_weight, then hub_frac.
  3. Report that pick on half B.

**Outcome: the ruler cannot rank the configurations.**
- The best configuration's SE is about 0.87 (median), on a criterion of about 1.8, while configurations
  average 1.2.
- Between 3 and 56 of the 60 configurations lie within one SE, depending on the split.
- The ranking does not replicate: within a split, the half-A and half-B rankings correlate at a median
  Spearman ρ of −0.07 (range −0.39 to 0.18).
- So the rule mostly falls back to the default, which is picked in 16 of 20 splits. **The default is not
  shown to be optimal; it is not distinguishable.**
- Descriptively, on half B (mean over splits):
  - the structure-only ablation α = 0 scores 1.45, 4th of 62;
  - the default scores 1.25, 25th of the 60 grid configurations;
  - α = 1 scores 1.10, 48th of 62.

  This is consistent with structure carrying the cross-paper evidence, but it is within the noise.
- Telling configurations apart needs a stronger independent signal than this citation ruler. That is for
  the evaluation (T6).

## 10. Assumptions

- **A1.** Concept relations within a paper indicate relatedness. Every clustering edge is a star around
  one paper's method, so structure is mostly paper co-occurrence, and fine levels rebuild papers (§8).
- **A2.** Names carry weak but real semantic signal: informative for tasks, problems and techniques,
  nearly useless for proper-named methods (notebook 02). That is why α < 1.
- **A3.** Bibliographic coupling between papers that share no concept is a proxy for closeness in meaning.
- **A4.** Names and aliases are export-wide and undated, and are assumed to carry no information from
  after the cutoff that matters. This cannot be checked from the export.
- **A5.** Entry follows publication years.
  - An edge enters at its paper's year; a node at the earliest year of its provenance and incident-edge
    papers.
  - The node `year` and `first_seen_year` fields and the edge `year` field are not used, because they leak.
- **A6.** Coupling counts shared cited-work node ids. It assumes the export resolves a cited work to one id
  across the papers that cite it (122 of 580 cited works are cited by more than one paper).
- **A7.** The sweep selects on the unadjusted lift. It assumes the period confound does not change how the
  configurations rank.

## 11. Trade-offs and rejected alternatives

- **Greedy agglomeration vs global optimisation.**
  - Gains: exact budgets, laminarity by construction, determinism, and merges that can each be explained.
  - Costs: early merges cannot be undone, and there is no optimality guarantee.
- **Hypergraph modularity / h-Louvain (Kamiński et al.), rejected.**
  - It controls the number of communities only indirectly, through a resolution parameter, while P2 makes
    that number a hard limit.
  - Communities at different resolutions are not nested, so it gives no laminar cuts.
  - It suffers from the resolution limit.
  - It builds its own degree null into the objective, which would blur the comparison with the
    configuration null.
- **Spectral hypergraph coarsening (HyperEF-style), rejected.** It controls a coarsening ratio, not exact
  per-level budgets, and has no semantic term.
- **Clique expansion, rejected.**
  - It splits every multi-member edge into pairs: 9.5 member pairs per incidence at ≤2026.
  - Multi-way coarse edges disappear.
  - Prop. 2 and the merge shares show where its scores would differ.
- **Semantics only, rejected.** Proper-named methods find only their own family (notebook 02). The α = 1
  ablation scores below the default and below α = 0 on the held-out ruler, within the noise (§9).
- **Rank mixing vs raw mixing.**
  - Raw S and H live on incomparable scales, and H is 0 for 99% of singleton pairs.
  - Ranks make α an interpretable weight, and F_H(0) = 0 keeps the structural rank from being nearly
    binary.
  - The cost is that magnitudes inside each signal are lost.
- **Size cap.**
  - It prevents the giant clusters that average linkage produces on sparse data: without a cap, 87% of the
    concept nodes fall into one level-0 super-node at ≤2026.
  - The cost is that sizes are imposed. At ≤2026 the largest super-nodes hold 529, 131 and 33 concept nodes,
    against caps of 530.7, 132.7 and 33.2.
- **Hub removal.**
  - It stops generic terms such as "materials science", "MAE" and "molecular dynamics" from fusing
    unrelated papers.
  - The cost is that hubs are placed by their names alone.
  - The threshold is a parameter, and its meaning shifts across snapshots (4 to 11 papers at 0.2), so the
    effective threshold is logged per run.
