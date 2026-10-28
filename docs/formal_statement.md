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
| Temporal prior (§2, §9) | `tkh/hierarchy.py` (`stable_nodes`, `build_concept`) |
| Persistent ids and temporal events | `tkh/temporal.py` |
| LLM labels and glosses (levels 0–1, T5, §4): evidence lines, seeded kind-stratified 50/50 split, contrast with neighbouring groups; LLM client and response cache | `tkh/label.py`, `tkh/llm.py`, `configs/prompts/labeller.txt` |
| Output assembly | `tkh/export.py` |
| Configuration | `tkh/config.py`, `configs/default.toml` |
| Run | `tkh/pipeline.py`, `python -m tkh build` |
| Null models | `tkh/null.py`, `python -m tkh null` |
| Output checks (schema, P1, P2, cutoff, labels present, events) | `validate.py` |
| Held-out coherence check (P3) and the selection sweep (evaluation, outside the method package; sweep output not current, §10) | `eval/coherence.py`, `eval/experiments.py`, `python -m eval coherence`, `python -m eval sweep` |
| Stability evaluation (P5) and the temporal-prior variants (variant output not current, §9) | `eval/stability.py`, `python -m eval stability`, `python -m eval gamma` |
| Label faithfulness (P6, T6): held-out NLI judge | `eval/faithfulness.py`, `configs/prompts/claims_split.txt`, `configs/prompts/claim_entail.txt`, `python -m eval faithfulness` |
| Retrieval agent and its evaluation (T6 extrinsic utility) | `tkh/retrieve.py`, `eval/retrieval.py`, `python -m eval retrieval` |
| Figures of `metrics.json` | `eval/figures.py`, `make figures` |

**Configuration.**
- The method parameters (`alpha`, `gamma`, `rho`, `edge_weight`, `hub_frac`, `lsa_dim`) are in `[method]` of
  `configs/default.toml`. Unknown keys are an error.
- Budgets are in `[hierarchy]` and cutoffs in `[snapshots]`.
- The labeller and judge settings are in `[labels]`: `labeller = "llm"` (or `"placeholder"`), `labeller_model`
  qwen2.5:7b-instruct, `judge_model` phi4, `mode` offline (replay from `data/llm_cache.json`; `live` and `refresh`
  need a local Ollama server), `seed` 0 of the 50/50 evidence split, `max_items` 40 lines per half, `contrast` 10,
  `workers` 4.
- `python -m tkh` overrides them with `--param k=v`, `--budgets` and `--cutoffs`.
- Each run writes the resolved values, including `[labels]`, to `<out>/run_config.toml`.

**Where the numbers come from.**
- Every run result in this document (§§1–3 and 5–12: counts, hubs, thresholds, caps and sizes as well as the
  evaluation results) comes from `out/run_info.json`, `out/metrics.json` (sections `coherence`,
  `stability`, `faithfulness`, `retrieval`), `out/faithfulness_judgements.json`, `out/retrieval_answers.json`,
  `out/temporal_events.json` or `out/<t>/coarse_hyperedges.json`, produced by `make all` (build → validate →
  metrics → test). Values recomputed from these files are marked *(derived)*.
- The full results, with CIs and breakdowns, are in `docs/evaluation_report.md`; this document keeps only what
  the statements need.
- `out/sweep.json` (`make sweep`) and `out/gamma/` (`make gamma`) predate the verification fixes and are not
  current results. No number here is taken from them.
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
  - **Why** (notebook 03 §8): citations are the held-out coherence ruler (§8), and titles are shared by every
    node of a paper, so they would re-encode "same paper".
  - Claim sentences, titles, future topics and evaluated_on attributes are label evidence (§4), split 50/50:
    the labeller sees one half, the faithfulness judge only the other. Citations are excluded from label
    evidence.
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

    s(A, B)   = α · F_S(S(A, B)) + (1 − α) · F_H(H(A, B))
    s_t(A, B) = (1 − γ) · s(A, B) + γ · Π(A, B)   if A and B both hold stable old nodes, else s(A, B)

The temporal term Π and the stable set are defined in §9. With γ = 0 every snapshot is built on its own.

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
  and `multi_endpoint` (Prop. 2), plus `prior` (merges where Π applied); per snapshot also `n_concept`,
  `n_edges`, `hub_threshold_papers`, `hubs`, `n_stable` and `n_anchored`.

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
  - At ≤2026, edges with λ_e ≥ 2 that share their set of super-nodes with another edge number 255 (level 0),
    205 (level 1) and 170 (level 2) *(derived)*.

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
| 0 | 194 | 325 | 35 | 111 (94 + 17) |
| 1 | 115 | 382 | 57 | 153 (116 + 37) |
| 2 | 68 | 386 | 100 | 249 (173 + 76) |

The split of the multi-way edges by class is *(derived)* from `edges[].class`.

**Proposition 1 (merge gain).** Let C = Σ_e w_e (λ_e − 1). Merging A and B reduces C by exactly
Σ_{e: A∈e, B∈e} w_e. *Proof:* an edge with endpoints in both A and B loses one distinct super-node,
and no other edge changes. ∎

**Proposition 2 (where native and clique scores differ).**
- **Numerators.** At singletons, the numerator Σ_{e∋a,b} w_e is the weighted clique-expansion weight of
  the pair. The two numerators, Σ_e w_e [c_A,e > 0][c_B,e > 0] and the clique form Σ_e w_e c_A,e c_B,e,
  differ only once a super-node holds two or more endpoints of a shared edge. Native H counts that edge
  once per pair of super-nodes; the clique view counts it once per member pair.
- **Denominators.** The normaliser is the hyperdegree d_A (each incident edge once), not a clique-graph
  degree. So H is a cosine on the incidence matrix, and the two scores can differ even without shared
  multi-endpoint edges.
- **How often.** At ≤2026, a shared edge with two or more endpoints on one side occurs in **40 of 45, 151
  of 180 and 2177 of 3740 merges** (89%, 84%, 58% *(derived)*) at levels 0, 1 and 2 (`multi_endpoint`).
  - The two scores therefore differ for most chosen merges.
  - Whether clique linkage would have chosen differently is not measured: no pairwise projection is built.

**Lemma (cap feasibility).** If ρ ≥ 2 and K > N_k items remain, a feasible pair exists. *Proof:*
the two smallest items have total size ≤ 2n_t/K < 2n_t/N_k ≤ c_{t,k}. ∎
- Every level therefore has exactly min(N_k, n_t) super-nodes, for any budget list. `validate.py` checks the
  budgets of each run (P2).
- ρ < 2 is rejected.
- If no feasible pair remained, the level would stop with an error; the lemma rules this out.

## 4. Output

For each t, the output is a set of partitions P_{t,0}, …, P_{t,K−1} of the whole snapshot.
- **Sizes:** |P_{t,k}| = min(N_k, n_t) super-nodes.
- **Nesting:** P_{t,k+1} refines P_{t,k}. Level k starts from level k+1's super-nodes and can only merge
  them. Export finds each parent by containment and raises on a non-laminar input.
- **Anchored nodes** are added to their anchor's super-node at every level.
- **Ids and the event log** come from overlap matching (`tkh/temporal.py`) on top of the temporally coupled
  partitions (§9).

**Labels** (`tkh/label.py`, T5). A label and a one-sentence gloss per super-node at levels 0 and 1 are written
by an open-source LLM (`labeller_model` qwen2.5:7b-instruct, replayed offline from `data/llm_cache.json`). Level
≥ 2 labels are null.
- **Evidence**, all from snapshot t: member concepts ("name [type]", with aliases); each clustering edge with
  at least one tail member in the group, as a fact (edges that touch the group only through their head are left
  out), with the result attributes of evaluated_on edges (metric, value, task, split); member claims;
  future-work topics; paper titles. Cited works and authors are left out.
- **Split.** The evidence is split 50/50, seeded by the members and stratified by kind. Each half is capped at
  `max_items` = 40 lines, ranked by how many snapshot papers mention the node (or how many members an edge
  holds). The labeller sees only the seen half; the held-out half is reserved for the faithfulness judge (§6).
- **Contrast.** The labeller also sees the `contrast` = 10 same-level groups that share the most clustering
  edges with this one, each as its top concept names from its own seen half. No held-out line of any group
  enters the prompt.
- The exact input of every label is recorded in `<t>/label_inputs.json`.
- A failed generation is written as "[label generation failed]"; none occurs in the run. A deterministic
  placeholder labeller remains as an option (`labeller = "placeholder"`), unused in the run.

**Files**, per run directory:

| File | Content | Checked by `validate.py` |
|---|---|---|
| `<t>/hierarchy.json` | `{cutoff, levels, budgets, supernodes: [{id, level, parent_id, member_ids, label, gloss}]}` | yes, against `schema/hierarchy.schema.json` |
| `<t>/coarse_hyperedges.json` | the T4 records (§3) | no |
| `temporal_events.json` | `{events: [...]}` | yes, against `schema/temporal_events.schema.json` |
| `<t>/label_inputs.json` | per labelled super-node: the seen and held-out evidence and the prompt SHA-256 | no |
| `run_config.toml` | the resolved inputs, cutoffs, budgets, `[method]` and `[labels]`; paths relative to the run directory | used as the validator's config |
| `run_info.json` | parameters, budgets, cutoffs, runtime, and diagnostics per snapshot and level | no |
| `metrics.json` | evaluation results, one section per check: `coherence`, `stability`, `faithfulness`, `retrieval` | no |
| `faithfulness_judgements.json`, `retrieval_answers.json` | per-claim judge verdicts; retrieval answers and resolved gold | no |

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
| Determinism | **by construction**: ARPACK with a fixed seed, rounding of S, H and scores, lowest-index ties, and sorted processing; LLM labels replay from the response cache. Not covered by a test (only the validator is tested); repeatability is expected within one numerical environment, not across machines or BLAS builds. |
| No future information | **by construction** for structure and membership (edges, hub counts, LSA fit and anchoring use snapshot t only; `validate.py` checks member cutoffs). Label evidence is drawn from snapshot t only, but names and aliases are export-wide (A4) and the LLM's own knowledge is not restricted. The deterministic checks of the faithfulness evaluation find, over the 300 labels, 0 years after the cutoff, 4 future entities and 33 named non-members. |
| P3 semantic coherence | **empirical** (§8), controlling for publication period. Exact filter, robust (p ≤ 0.05 against both nulls under all five schemes) at ≤2026 levels 1 and 2 and ≤2024 level 2; ≤2024 level 1 fails only `gap`; ≤2022 levels 1 and 2 are significant under `year1` only; level 0 at no snapshot; ≤2020 is not evidence (level 2 undefined). |
| P5 temporal stability | **by construction** that untouched regions are held together by the prior (§9), with persistent ids and a validated event log; the size of the effect is **empirical** (§9): cross-snapshot HARI 0.86 / 0.80 / 0.89, change concentrated on touched nodes (ratios 2.4–7.0), but not distinguishable from a random-attachment null (HARI p = 0.33, 0.06, 0.12); perturbation HARI 0.17 at ≤2026. No γ = 0 control exists for the current build. |
| P6 faithful labels | **empirical** (checks below): LLM labels from the seen half of the evidence; a judge of another family (`judge_model` phi4) checks each atomic claim against the held-out half and must cite an existing line. Over-claim rate 0.58 [0.52, 0.64] of 296 judged labels (300 labelled, 4 without held-out evidence); claim-level unsupported 0.45; level 0 0.37 [0.25, 0.48], level 1 0.64 [0.57, 0.69]. The judge is not validated (no known-answer controls, no nulls). `validate.py` checks non-empty labels and glosses at levels 0–1. |
| T6 retrieval utility | **empirical**, descriptive (settings chosen in sample, no nulls or CIs): on 18 questions at ≤2026 (14 type A, 4 type B), drill-down vs flat search: methods hit-rate 0.28 vs 0.30, method claims 0.25 vs 0.31, citations 0.66 vs 0.58 (A); claims 0.74 vs 0.54 (B); reach 0.83 vs 1.00 (A); median steps to the first target 206.5 vs 10.5 (A), 143 vs 2 (B). |

**Evaluation checks as implemented** (`make metrics` = coherence → stability → faithfulness → retrieval; each
writes its own section of `out/metrics.json`; results in `docs/evaluation_report.md` §§3–6):
- **Coherence** (`eval/coherence.py`, `eval/experiments.py`): the held-out coupling lift against the
  configuration null and random labels (§8).
- **Stability** (`eval/stability.py`): perturbation, cross-snapshot agreement against the random-attachment
  null, change localisation and event counts (§9).
- **Faithfulness** (`eval/faithfulness.py`): label + gloss are decomposed into at most 3 atomic claims
  (`claims_split.txt`); each is judged against the held-out lines (`claim_entail.txt`) and counts as supported
  only if the judge cites a numbered line that exists. Held-out facts whose head method is outside the group
  are shown to the judge marked as such (`Evidence.judge_view`), and the cited-line check runs on this view. Reported: the over-claim rate (share of judged labels
  with ≥ 1 unsupported claim, bootstrap CI over labels), the claim-level unsupported share, breakdowns by cutoff
  and level, and deterministic checks without an LLM (years after the cutoff, named non-members, future
  entities). There are no known-answer controls, no null trees and no rigor levels.
- **Retrieval** (`tkh/retrieve.py`, `eval/retrieval.py`): an agent picks the snapshot the question names, scores
  super-nodes by keyword overlap with label + gloss (levels 0–1) and the member centroid, keeps a beam of
  10 / 20 / 40 super-nodes per level and ranks the leaves of the kept level-2 nodes; the flat baseline ranks
  every leaf with the same scorer. It is scored against `data/ground_truth.json` (hit-rate, error rate,
  steps to target); only the evaluator reads the ground truth.

## 7. Complexity

Per level, with n items at the start of the level, m fine reduced edges and d = `lsa_dim`:
- **Initialisation:** O(n²(m + d)) time for the score matrix, plus O(n² log n) for the rank CDFs.
- **Each merge:** O(n(m + d)) to rescore the merged item.
  - A row whose best partner was one of the two merged items is rescanned at O(n). The number of such rows
    is unbounded, so the worst case is O(n²) per merge.
- **Merges per level:** n − min(N_k, n): 3740, 180 and 45 at ≤2026.
- **m is the same at every level.** A coarser level's incidence has the same fine-edge columns.
- **Text:** the TF-IDF and SVD run once per snapshot (12k–24k character n-gram features).
- **Temporal prior:** Π adds O(n²·K′) at initialisation and O(n·K′) per merge, with K′ = N_k previous
  super-nodes, and one more n×n array.
- **Memory:** O(n²), dominated by the dense score matrix and the arrays used to build it. At n = 3980 the
  score matrix alone is 127 MB, and the measured peak resident memory of the ≤2026 build is about 2 GB. The incidence is O(nm), about
  18 MB dense.

**Runtime.** The full build of four snapshots takes 34.7 s in one process (`runtime_s`, measured after
loading), including label assembly with the LLM answers replayed from the cache (offline mode). Cache misses
add the LLM time.
- The finest level of the largest snapshot dominates.
- Per-snapshot time grows roughly with n_t².
- Much larger graphs would need a sparse candidate set.

The evaluation is separate and runs as `make metrics`: `make coherence` (§8) runs 99 null rebuilds per
snapshot on 8 worker processes; `make stability` (§9) runs 5 perturbed rebuilds and R = 99 random-attachment
null rebuilds per transition; `make faithfulness` replays the judge from the cache; `make retrieval` runs
offline in seconds. `make sweep` (§10) is annotated at about 6 min on 8 cores.

## 8. Null models and the held-out coherence check

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
  - The node-set check runs in `python -m tkh null`. The rebuilds inside `eval/experiments.py` skip it.
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
- **Null for cross-snapshot stability** (`attachment_null`, §9): for a transition c0 → c1, every old
  concept-node tail member (members[1:]) of a new paper's clustering edge is redrawn among the old concept nodes
  of its type, with probability proportional to their tail degree on clustering edges up to c0, without
  duplicates in the edge; nodes that never occur in a tail are never drawn. The graph ≤ c0,
  the new nodes and each edge's arity, type mix and head are kept, so it randomises which old nodes the new papers
  touch.

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
    holds (p ≤ 0.05 against both nulls) under every scheme.
- **p-values:** one-sided, p = (1 + #null ≥ obs)/(R + 1). With R = 99 null rebuilds and R = 999
  random-label draws, the floors are 0.01 and 0.001.
- **Every snapshot is evaluated on its own.** The ruler, the pairs and the random labels are rebuilt at
  each cutoff, and the null hierarchy is rebuilt at each cutoff from the seed's null graph.
- **Command:** `make coherence`, i.e. `python -m eval coherence --run out`.
  - It reads the run's own `run_config.toml`, refuses null runs, and writes the `coherence` section of
    `out/metrics.json` (stability, faithfulness and retrieval write their own sections). It is part of
    `make metrics`.
  - A new build into the same directory deletes `metrics.json`.

**Coverage per snapshot (exact filter):**

| Snapshot | Citing papers | No-overlap pairs | Coupled pairs | Interval strata |
|---|---|---|---|---|
| ≤2020 | 9 | 18 | 5 | 1 |
| ≤2022 | 14 | 34 | 11 | 3 |
| ≤2024 | 25 | 100 | 21 | 6 |
| ≤2026 | 37 | 253 | 58 | 10 |

**Period-adjusted coherence** (primary scheme, exact filter; `out/metrics.json → coherence`; full tables in
`docs/evaluation_report.md` §3). Each cell gives the lift [95% paper-bootstrap CI], and for each null its mean
and p. A scheme counts as significant when p ≤ 0.05 against both nulls; ranges over the five schemes and the
scheme counts are *(derived)*.

| Snapshot | Level | Lift [95% CI] | Configuration null | Random labels | Robust across period schemes |
|---|---|---|---|---|---|
| ≤2026 | 0 (15) | 0.88 [0.53, 1.25] | 1.00, 1.00 | 1.01, 1.00 | no evidence under any scheme (0.82–0.89) |
| ≤2026 | 1 (60) | 1.31 [0.54, 2.00] | 1.01, **0.01** | 1.01, **0.001** | **yes**: 1.17–1.31 under every scheme |
| ≤2026 | 2 (240) | 1.57 [0.43, 2.63] | 1.01, **0.01** | 0.99, **0.001** | **yes**: 1.55–1.65 under every scheme |
| ≤2024 | 0 (15) | 0.83 [0.35, 1.54] | 1.01, 1.00 | 1.02, 1.00 | no evidence under any scheme (0.73–0.90) |
| ≤2024 | 1 (60) | 1.32 [0.38, 2.25] | 1.01, **0.01** | 1.00, **0.001** | no: significant under interval, year1, year2, year3, not gap (1.10–1.60; gap p = 0.10 / 0.152) |
| ≤2024 | 2 (240) | 1.86 [0.35, 3.17] | 1.02, **0.01** | 0.99, **0.001** | **yes**: 1.47–1.86 under every scheme |
| ≤2022 | 0 (15) | 0.55 [0.05, 2.18] | 0.99, 1.00 | 1.00, 1.00 | no evidence under any scheme (0.47–0.66) |
| ≤2022 | 1 (60) | 1.06 [0.26, 3.20] | 1.00, 0.17 | 1.00, 0.139 | no: significant under year1 only (0.92–1.29) |
| ≤2022 | 2 (240) | 0.99 [0.47, 2.67] | 1.08, 0.76 | 1.01, 0.60 | no: significant under year1 only (0.89–1.16) |
| ≤2020 | 0 (15) | 0.03 [0.00, 4.93] | 0.96, 1.00 | 0.99, 1.00 | no evidence under any scheme (0.03–0.51) |
| ≤2020 | 1 (60) | 0.16 [0.00, 6.98] | 0.96, 1.00 | 0.98, 1.00 | no: significant under year1, year2, year3 only (0.16–3.76) |
| ≤2020 | 2 (240) | undefined | 1.03, – | 1.03, – | not evaluable (no no-overlap pair co-assigned) |

These results are for the shipped run (γ = 0.5). The unadjusted lifts, the other period schemes and the
fuzzy filter are all in `metrics.json`. Under the fuzzy filter, the robust cells are ≤2026 levels 1–2, ≤2024
levels 1–2 and ≤2022 level 1; ≤2024 level 0 is significant under no scheme, and ≤2022 level 2 under `interval`
only. No γ = 0 control exists for the current build.

**Reading:**
- **Robust evidence of P3 (exact filter, all five schemes): ≤2026 levels 1 and 2, and ≤2024 level 2.** There,
  the hierarchy groups the concepts of citation-coupled papers within the same period more than a
  degree-preserving null rebuild or a random relabelling does, under every period scheme. ≤2024 level 1 fails
  only `gap`. ≤2022 does not beat the nulls under the primary scheme (level 1 1.06, p = 0.17 / 0.139; level 2
  0.99, p = 0.76 / 0.60).
- **Level 0 shows no coherence** at any snapshot (lift 0.55–0.88; ≤2020 0.03), with p = 1.0 against both nulls
  under exact matching.
- **The period control is essential.** Without it, at ≤2026, levels 1 and 2 still beat both nulls (1.25 and
  1.52; p = 0.01 / 0.001), but the null means rise to 1.05–1.21 through same-period mixing. With it, the nulls
  fall to about 1.0.
- **No attribution to the temporal prior.** Whether γ = 0.5 moves coherence between levels is not measured.
- **The earlier snapshots are thin.** They have 5–21 coupled pairs; among them only ≤2024 level 2 (21 pairs) is
  robust. ≤2020 is a single period stratum with 18 pairs and cannot be evaluated.
- **Two kinds of uncertainty.**
  - The null tests are conditional on each snapshot's papers: the ruler is fixed and only the partition
    varies.
  - Over papers, the bootstrap CIs are wide and include 1 everywhere.
  - So the evidence is "better than chance for this corpus", not a population estimate.

## 9. Temporal coupling (T3) and stability (T6)

**Mechanism: a localised temporal prior.** This is the evolutionary-clustering term of the literature
review: a merge score with "temporal similarity to previous clusters", plus identity matching.
- **Stable old nodes.** For snapshot t, the stable set U_t holds the concept nodes of t−1 that
  - are not a (non-hub) member of a clustering edge from a new paper (year in (t−1, t]),
  - did not change hub status, and
  - are not a member of an old clustering edge that gains or loses a hub (an edge containing a node whose hub
    status changed).
- **The prior.** Π(A, B) = Σ_c M_A,c M_B,c / (u_A u_B).
  - M_A,c counts A's stable members in level-k super-node c of t−1, and u_A = |A ∩ U_t|. So Π is the share of
    A×B pairs of stable nodes that shared a super-node at the same level in t−1.
  - It is undefined, and the plain score is used, when either side holds no stable node.
- **The score** s_t = (1 − γ)·s + γ·Π puts the prior on the same [0, 1] scale as the rank mix.
  - The default γ = 0.5 was stated before any result.
  - γ = 0 builds each snapshot independently, as before.
  - γ = 1 is the freeze-like extreme.
- **Localisation by construction.** Touched nodes and new nodes are placed by structure and names alone, so
  change can happen exactly where the corpus changed (P5). Untouched regions are pulled to stay together.
  U_t holds 876, 1169 and 2629 of the 1018, 1464 and 2829 old concept nodes (`n_stable`).
- **Identity.** Persistent ids and the event log come from overlap matching (`tkh/temporal.py`), checked by
  `validate.py`. Births, growth, merges and splits occur, but deaths cannot: snapshots only grow, so every old
  super-node overlaps a new one.
- **Cost.**
  - Runtime: Π adds O(n²·K′) at initialisation and O(n·K′) per merge (§7).
  - **Path dependence:** a decision made on a small early snapshot is carried forward. This is a design
    argument: its effect on perturbation robustness and on coherence per level is not measured on the current
    build (no γ = 0 control).

**Stability evaluation** (`eval/stability.py`, `make stability`). Scores are on concept nodes only.
- **ARI** is the adjusted Rand index per level.
- **HARI** is its level-pooled laminar analogue, Σ_k (I_k − E_k) / Σ_k (M_k − E_k), with ARI's per-level
  index I_k, expectation E_k and maximum M_k. It is 1 for identical trees and has expectation 0 under a node
  permutation applied at every level.

**1. Perturbation** (the brief's protocol). Remove 10% of all hyper-edges, stratified by publication period ×
relation (10% of each relation in every period), for seeds 0–4, and rebuild the whole chain. Values are the mean and t-interval over the seeds, against the
unperturbed run.

| Snapshot | ARI level 0 | ARI level 1 | ARI level 2 | HARI |
|---|---|---|---|---|
| ≤2020 | 0.53 [0.48, 0.57] | 0.71 [0.65, 0.76] | 0.90 [0.87, 0.92] | 0.58 [0.54, 0.62] |
| ≤2022 | 0.30 [0.25, 0.35] | 0.50 [0.45, 0.55] | 0.79 [0.77, 0.82] | 0.36 [0.32, 0.40] |
| ≤2024 | 0.15 [0.12, 0.18] | 0.30 [0.28, 0.33] | 0.67 [0.64, 0.69] | 0.20 [0.18, 0.23] |
| ≤2026 | 0.12 [0.11, 0.13] | 0.26 [0.24, 0.27] | 0.63 [0.61, 0.65] | 0.17 [0.16, 0.18] |

**2. Real cross-snapshot stability.** Agreement on the old concept nodes between consecutive snapshots,
with 95% intervals over 200 half-subsamples of the nodes.
- **New-paper null** (random attachment, `attachment_null`, §8): the graph ≤ t−1 stays real; every old
  concept-node tail member (members[1:]) of a new paper's clustering edge is redrawn among the old concept nodes
  of its type, with probability proportional to their tail degree on clustering edges up to t−1; the head is
  kept; snapshot t is rebuilt from the real t−1 hierarchy,
  with the stable set recomputed, for R = 99 seeds.
- **p** is one-sided: (1 + #null ≥ obs) / (R + 1).

| Transition | Old concept nodes | ARI level 0 | ARI level 1 | ARI level 2 | HARI [95% CI] | New-paper null HARI: mean [2.5–97.5%], p |
|---|---|---|---|---|---|---|
| 2020→2022 | 1018 | 0.85 | 0.87 | 0.92 | 0.86 [0.83, 0.88] | 0.85 [0.79, 0.89], 0.33 |
| 2022→2024 | 1464 | 0.80 | 0.79 | 0.79 | 0.80 [0.77, 0.82] | 0.75 [0.69, 0.81], 0.06 |
| 2024→2026 | 2829 | 0.89 | 0.90 | 0.92 | 0.89 [0.87, 0.90] | 0.86 [0.81, 0.90], 0.12 |

**3. Change localisation.**
- **Touched:** old concept nodes that are members of any edge of a new paper, of any relation. This is the
  evaluator's own definition, broader than the method's.
- **Reassignment:** 1 − Jaccard of a node's old co-members before and after.
- **Ratio:** touched over untouched reassignment, with a 1000-draw node bootstrap.

| Transition | Touched old nodes | Reassignment touched / untouched, level 0 | level 1 | level 2 | Ratio level 0 / 1 / 2 [95% CI] |
|---|---|---|---|---|---|
| 2020→2022 | 40 of 1018 | 0.46 / 0.15 | 0.60 / 0.16 | 0.68 / 0.10 | 3.1 [2.2, 4.1] / 3.8 [2.8, 4.7] / 6.8 [5.2, 8.5] |
| 2022→2024 | 87 of 1464 | 0.50 / 0.20 | 0.57 / 0.23 | 0.61 / 0.17 | 2.5 [2.0, 2.9] / 2.4 [2.0, 2.9] / 3.6 [3.0, 4.2] |
| 2024→2026 | 111 of 2829 | 0.59 / 0.14 | 0.62 / 0.12 | 0.64 / 0.09 | 4.3 [3.6, 4.9] / 5.3 [4.6, 6.1] / 7.0 [6.0, 8.0] |

**4. Events** (`temporal_events.json`; no deaths, as explained above):

| Transition | Level 0 | Level 1 | Level 2 |
|---|---|---|---|
| 2020→2022 | change 3, continue 3, growth 6, merge 1, split 1 | birth 7, change 6, continue 23, growth 17, merge 7 | birth 32, change 6, continue 144, growth 28, merge 24, split 3 |
| 2022→2024 | change 9, continue 1, growth 5 | birth 2, change 11, continue 11, growth 21, merge 6, split 4 | birth 27, change 21, continue 104, growth 70, merge 18 |
| 2024→2026 | change 9, continue 1, growth 2, merge 1, split 1 | birth 1, change 23, continue 8, growth 21, merge 3, split 2 | birth 11, change 39, continue 118, growth 52, merge 14, split 3 |

**What the prior buys and what it costs.** The temporal-prior variants (`make gamma`, `out/gamma/gamma.json`)
predate the verification fixes and are not current results; no γ = 0 control exists for the current build
(`docs/evaluation_report.md` §9). The comparison with γ = 0 is therefore not reported here.

**Reading** (γ = 0.5; details in `docs/evaluation_report.md` §4):
- **Persistence is high.** Cross-snapshot HARI is 0.86, 0.80 and 0.89.
- **Change concentrates on touched nodes.** Touched old nodes are reassigned 2.4–7.0 times more often than
  untouched ones (all CIs above 1, lowest bound 2.0). Untouched nodes still move (reassignment 0.09–0.23), so
  untouched regions are held, not frozen.
- **The persistence is not the data's.** The random-attachment null is nearly as stable (null HARI means 0.85,
  0.75 and 0.86 against 0.86, 0.80 and 0.89; p = 0.33, 0.06 and 0.12). The observed HARI is above the null mean
  at every transition, but not significantly; of the per-level ARIs only 2024→2026 level 2 has p = 0.01. So the
  persistence comes from what the null keeps (the real ≤ t−1 graph, the real t−1 hierarchy and the prior), and is
  not evidence that the corpus' own attachment pattern is stable.
- **Robustness to perturbation is low at the coarse levels of late snapshots.** HARI under 10% edge removal is
  0.58, 0.36, 0.20 and 0.17 at ≤2020–≤2026, and level-0 ARI is 0.12 at ≤2026. The fine level is the most robust:
  level-2 ARI is 0.63–0.90. How much of the decline the prior causes is not measured (no γ = 0 control).
- **Why γ = 0.5.** It was stated before any result. No current result justifies another value.

## 10. Parameters and selection

| Parameter | Default | Role |
|---|---|---|
| α (`alpha`) | 0.5 | weight of the semantic rank |
| γ (`gamma`) | 0.5 | weight of the localised temporal prior (§9); 0 = independent snapshots |
| ρ (`rho`) | 2 | size-cap factor (≥ 2, or inf) |
| `edge_weight` | relation_balanced | edge weighting (§1) |
| `hub_frac` | 0.2 | hub threshold as a share of the snapshot's papers (1.0 = no hubs) |
| `lsa_dim` | 100 | text projection rank |

- **Overrides.**
  - `--param k=v ...` overrides single parameters (e.g. `gamma=0`); values are JSON-decoded.
  - `--budgets` and `--cutoffs` override the levels and snapshots; `--graph` and `--articles` override the
    inputs.
  - Example: `python -m tkh build --param alpha=0.25 hub_frac=0.3 --budgets 10 40 160 --out /tmp/run`.
  - Without `--out`, the build overwrites `out/`.
- **Strict parsing.** Unknown parameters are an error.
- **Run record and validation.**
  - Each build writes its resolved `run_config.toml`, with input paths relative to the run directory.
  - Validation is a separate step: `validate.py <out> --config <out>/run_config.toml`. It runs in
    `make validate`, in `make all` (build → validate → metrics → test, where `make metrics` = coherence →
    stability → faithfulness → retrieval) and in `make null`.
  - `make test` runs only `tests/test_validate.py` (the validator on valid and broken fixtures).
  - `.NOTPARALLEL` keeps the checks sequential, because they share `metrics.json`.

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

**Outcome: not current.** The sweep results (`out/sweep.json`) predate the verification fixes and are not
used (`docs/evaluation_report.md` §9). The shipped `[method]` defaults are therefore not shown to be optimal,
nor compared with the other configurations, on the current build. Telling configurations apart would need a
stronger independent signal than this citation ruler; the T6 checks now implemented (label faithfulness and
retrieval, §6) evaluate the shipped configuration only.

## 11. Assumptions

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
  configurations rank (the sweep has no current result, §10).
- **A8.** Old structure that no new paper touches should keep its grouping (P5). The prior encodes this
  premise, and it is not tested by the data: the random-attachment null is nearly as stable as the real run
  (HARI p = 0.33, 0.06, 0.12; §9).

## 12. Trade-offs and rejected alternatives

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
- **Semantics only, rejected.** Proper-named methods find only their own family (notebook 02).
- **Rank mixing vs raw mixing.**
  - Raw S and H live on incomparable scales, and H is 0 for 99% of singleton pairs.
  - Ranks make α an interpretable weight, and F_H(0) = 0 keeps the structural rank from being nearly
    binary.
  - The cost is that magnitudes inside each signal are lost.
- **Temporal coupling.**
  - **Chosen: a localised merge prior** (§9). It has a smooth weight γ, keeps the budgets and the cap
    untouched, and lets change happen where new papers attach.
  - **Rejected: matching only** (γ = 0). Identity is tracked, but nothing keeps untouched regions together, so
    each snapshot's greedy build can reshuffle them (a design argument; no γ = 0 control on the current build).
  - **Rejected: a dirty-region rebuild**, which re-agglomerates only touched groups (DynHAC-style). Fixed
    groups would use up budget slots and need extra rules, and it has no smooth knob.
  - **Rejected: freeze**, where old nodes keep their groups. It cannot adapt to new evidence about old nodes;
    γ = 1 is close to it.
- **Size cap.**
  - It prevents the giant clusters that average linkage produces on sparse data: without a cap, 87% of the
    concept nodes fall into one level-0 super-node at ≤2026.
  - The cost is that sizes are imposed. At ≤2026 the largest super-nodes hold 512, 120 and 33 concept nodes,
    against caps of 530.7, 132.7 and 33.2.
- **Hub removal.**
  - It stops generic terms such as "materials science", "MAE" and "molecular dynamics" from fusing
    unrelated papers.
  - The cost is that hubs are placed by their names alone.
  - The threshold is a parameter, and its meaning shifts across snapshots (4 to 11 papers at 0.2), so the
    effective threshold is logged per run.
