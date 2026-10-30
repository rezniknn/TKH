# Budgeted Semantic–Hypergraph Agglomeration over an Evolving Knowledge Hypergraph

**Alexey Reznik**

**Abstract.** We build a budgeted, laminar, three-level abstraction of a temporal knowledge hypergraph in four
cumulative snapshots. SHAC is a deterministic greedy agglomeration whose merge score mixes, on a common rank scale,
semantic similarity and a structural term on the collapsed hyper-edge incidence, with a soft prior from the previous
snapshot. Laminarity, exact level budgets, the collapse rule and super-node identity tracking hold by construction; coherence is measured with signals the method never sees; stability, label faithfulness and utility are evaluated empirically. Of five values of the semantic weight tested, α = 0.75 is a recommended variant that balances semantic and structural signal when forming super-nodes. A held-out citation coherence ruler beats both null models at every hierarchy level on the later snapshots; model's utility for retrieval is mixed and not established.


## 1. Problem definition

The Temporal Knowledge Hypergraph (TKH) provided represents scientific literature as typed nodes joined by dated hyper-edges.
Per snapshot H(t) we need a laminar sequence of partitions under hard per-level budgets (P1, P2), with super-nodes close
in meaning (P3), computed on the hypergraph (P4), evolving smoothly with trackable identities (P5) and faithfully
labelled (P6). The export covers papers on machine learning for materials science and chemistry; snapshot ≤t (t = 2020, 2022, 2024, 2026) holds every node and hyper-edge of papers published up to t.

## 2. Formal statement

*Concept nodes* are the nodes of the seven types that name a scientific idea (method, task, problem, technique,
component, dataset, metric); V_t denotes those of snapshot t, n_t = |V_t|. The other nodes (articles, claims, authors,
cited works, future-work topics) record papers rather than ideas. SHAC clusters V_t only, so that citations stay outside the method and
remain available as an independent test of coherence.

**Inputs.** Structure is the *clustering hypergraph* G_t = (V_t, E_t) of the six concept relations, each edge a star
around one paper's method; *hubs* (concepts in more than a fraction h of the papers) leave the edges, and w_e =
1/(|e| − 1), rescaled to equal weight per relation. Semantics is z_v: the TF-IDF of the character 3–5-grams of a
concept's name and aliases, reduced by LSA fitted per snapshot. Citations, claims, authors and titles are left out of coarsening method.

**Output.** Nested partitions P_{t,0} ⪰ P_{t,1} ⪰ P_{t,2} of V_t with exactly min(N_k, n_t) super-nodes for budgets
N = (15, 60, 240). The level budgets are chosen for convinience, model's performance under different level budgets has not been tested. Every node of the snapshot is an implicit leaf below L2; leaves are not a budgeted level.

**Procedure.** A nested partition under hard budgets contains NP-hard single-level problems, so SHAC optimises no
global objective. From the finest level up, it repeatedly merges the feasible pair of items (super-nodes of the level
below, or concepts) with the highest score until min(N_k, #items) remain:

$$ s(A,B) = \alpha\,F_S\big(S(A,B)\big) + (1-\alpha)\,F_H\big(H(A,B)\big), \qquad
   s_t(A,B) = (1-\gamma)\,s(A,B) + \gamma\,\Pi(A,B) \text{ if } A, B \text{ both hold stable old nodes.} $$

- **Semantic term** S(A,B) = ⟨z̄_A, z̄_B⟩, average linkage over member vectors.
- **Structural term** H(A,B) = Σ_{e∋A,B} w_e / √(d_A d_B), with d_A = Σ_{e∋A} w_e on the collapsed incidence of §4,
  where an edge counts each super-node it touches once.
- **Rank calibration.** F_S and F_H are mid-rank empirical distribution functions over the item pairs (for H, those
  with H > 0; F_H(0) = 0), frozen per level, so α is an explicit structure–semantics weight.
- **Temporal prior** Π(A,B): the share of pairs of stable members (old nodes no new paper touches) of A and B that
  shared a level-k super-node at t − 1.
- **Feasibility.** |A| + |B| ≤ ρ·n_t/N_k concept nodes; for ρ ≥ 2 a feasible pair always exists, so every budget is met
  exactly (Appendix A.1). Ties go to the lowest item index, so the build is deterministic.

**Default parameters**: α = 0.75 comes from the α comparison sweep; γ = 0.5, ρ = 2 and h = 0.2 are stated priors. 

**Anchoring.** Every non-concept node joins, at every level, the super-node of one concept: a claim that of the
method on its claims edge, an article that of the method it presents, any other node that of the method of the
earliest paper it occurs in. Each level is thus a partition of the whole snapshot (P1). A node shared by several
papers gets one home, whose semantic fit was not tested.

*Table 1. Guaranteed and measured properties.*

<!-- table:properties -->
| Property | Status | Evidence |
|---|---|---|
| P1 laminarity, P2 budgets | construction (merge-only; a feasible merge for ρ ≥ 2) | `validate.py` |
| P4 hyper-edge fidelity | construction (collapsed incidence, multi-way edges whole) | §4 |
| No future information | construction (snapshot-only edges, hubs, LSA, anchors); aliases assumed | `validate.py` |
| P5 identity and lineage | construction (overlap matching; one fate per super-node) | `validate.py` |
| P5 temporal stability | empirical (soft prior; no bound on reassignment) | Tables 3, A3–A5 |
| P3 coherence, trade-off | empirical (α chosen on these results) | Tables 2–3, A1–A2 |
| P6 labels, T6 utility | empirical | Tables 3, A6–A7 |
<!-- /table:properties -->

We rejected two alternatives. h-Louvain [1] greedily maximises a hypergraph modularity (Chung–Lu degree tax, weights
(c/d)^τ for c of an edge's d members in one part), blended with 2-section modularity on a schedule tuned by Bayesian
optimisation: the number of communities is an outcome, and stages need not nest, whereas P1–P2 fix nested counts. A
two-stage scheme (structure, then names) would freeze single-paper bundles before names could join them.

## 3. Method and literature positioning

SHAC resolves disagreement between structure and semantics per merge: on the common rank scale either signal can carry
a merge, and a pair that shares no edge can win only on names, at weight α, or on the temporal prior. Because the trade-off is one scalar, a balance between semantic and stuctural signal can be found by variying α.

Temporal stability (T3) uses a soft prior: an old node is *touched* if a new paper's edge contains it or its (or an
edge-neighbour's) hub status changed, and only pairs that both hold untouched, *stable* nodes receive Π, which pulls
but does not force them to keep their grouping. The prior is a mechanism, not a guarantee of smoothness: it bounds no
reassignment, and refitted LSA vectors and renormalised relation weights change even stable nodes' inputs. Identities
and the event log come from largest-overlap matching between snapshots, checked by `validate.py`.

**Positioning** (details in Appendix Table A0).

 From h-Louvain [1] SHAC takes hyper-edge-aware affinity and multilevel
aggregation, but fixes nested counts instead of optimising modularity; from Featured Graph Coarsening [2], joint
topology–feature coarsening, here greedy on the hyper-edge incidence; from DynHAC [3], average linkage and confining
change to affected regions, through a soft prior rather than recomputation; from HyperEF 2.0 [4], hyper-edge
contraction with explicit coarse edges, but with fixed counts and the connectivity cut as score. The structural null
follows the hypergraph configuration model [5], and Π is an evolutionary-clustering term [6]. The
contribution is their integration under hard budgets, with an evaluation that does not reuse the method's signals.

## 4. Coarsening decision

For a fine edge e with n_e members after hub removal, let c_S(e) be its endpoints in super-node S, λ_e the number of
super-nodes it touches and m_e = max_S c_S(e). `tkh/coarsen.py` assigns every edge to one class:

- **internal** (m_e = n_e): it leaves every H numerator but keeps its weight in d_A, damping super-nodes that already
  absorbed much of their incident weight;
- **partial** (1 < m_e < n_e): one coarse hyper-edge over its λ_e super-nodes, endpoint counts kept as metadata, only
  presence scored;
- **uncollapsed** (m_e = 1): the fine edge itself, scored like a partial edge.

An edge touching three or more super-nodes is *multi-way*: it is never split into pairs and adds w_e to the numerator
of every pair of super-nodes it touches.

**Example.** A paper's uses_technique edge {M, T₁, T₂, T₃} with T₁, T₂ ∈ A, M ∈ B, T₃ ∈ C is partial and multi-way
(λ = 3, m = 2)
and adds w_e to H(A,B), H(A,C) and H(B,C). A clique score would credit (A, B) with c_A·c_B = 2, rewarding A for holding
more of one paper; presence credits it once. After A and B merge it still links them to C; once C joins, it is
internal.

**Proposition 1.** For the connectivity objective C = Σ_e w_e(λ_e − 1), the standard (λ − 1) objective of hypergraph
partitioning, merging A and B reduces C by exactly Σ_{e∋A,B} w_e, since each such edge loses one distinct super-node and
no other edge changes. The numerator of H is thus the gain in this objective, for any arity.

`out/<t>/coarse_hyperedges.json` records every coarse edge and its class (Appendix A.3). The score loses endpoint
multiplicity and coarse-edge identity; whether a clique build would merge differently was not measured.

## 5. Evaluation

### 5.1 Metrics

**Coherence.** Grading coherence with names or relations would restate the merge criterion. The ruler used instead is *bibliographic coupling*, the IDF-weighted cosine of two papers' cited-work sets, scored only on
paper pairs that share no concept node or name, after dropping citations to works named like a concept of the citing
paper. The *lift* compares co-assigned pairs with same-period pairs under five period schemes, against a
configuration null (degrees and arities kept, real names) and a random-label null (members permuted within type and period). A cell (snapshot × level) is *robust* if it beats both nulls under every scheme.

**Stability.** *Perturbation*: 10% of hyper-edges removed (5 seeds), the chain rebuilt, ARI and HARI (a pair-counting
index pooled over levels) against the unperturbed run. *Cross-snapshot agreement* is tested against a *new-paper null*
that attaches new papers' edges to random old nodes; *localisation* compares the reassignment of old nodes in a new
paper's edges with that of the other old nodes.

**Label faithfulness.** The LLM labeller sees half of each super-node's evidence (citations data excluded); an LLM judge of
another model family splits label and gloss into at most three claims and checks each against the held-out half,
citing a line that must exist. The *over-claim rate* (labels with an unsupported claim) is descriptive: the judge is not
validated.

**Extrinsic utility.** A drill-down agent answers 18 questions by beam search from L0 to L2; flat search ranks all
leaves with the same keyword scorer. Gold items match by name, claims by source article, not content. We report
hit-rates on attainable items and end to end, reach, items inspected and candidates scored: point
estimates over 14 type-A and 4 type-B questions, with settings chosen in view of them.

### 5.2 Choosing α

α was varied over 0, 0.25, 0.5, 0.75 and 1, all other parameters fixed, each variant built and evaluated in full
(Appendix B); stability comparisons with the pre-sweep default, α = 0.5, are paired by seed.

*Table 2. α variants across the four criteria; the recommended variant in bold (`alpha_sweep`). The T6 column counts
point estimates of correlated measures, a descriptive simplification rather than independent votes.*

<!-- table:alpha_sweep -->
| α | P3 robust / below-null cells (exact) | P5 perturbation HARI ≤2026 [t-interval] | P5 paired difference ≤2026 to the pre-sweep default | P6 over-claim [95% CI] | T6 measures favouring drill-down / flat / tie |
|---|---|---|---|---|---|
| 0 | 2 / 1 | 0.22 [0.20, 0.25] | 0.05 [0.02, 0.08] | 0.55 [0.49, 0.61] | 1 / 10 / 1 |
| 0.25 | 3 / 2 | 0.18 [0.17, 0.20] | 0.01 [-0.01, 0.03] | 0.57 [0.51, 0.63] | 4 / 7 / 1 |
| 0.5 (pre-sweep default) | 3 / 3 | 0.17 [0.16, 0.18] | — | 0.61 [0.55, 0.67] | 3 / 8 / 1 |
| **0.75 (default)** | **7 / 0** | **0.19 [0.15, 0.23]** | **0.02 [-0.03, 0.07]** | **0.63 [0.58, 0.68]** | **3 / 7 / 2** |
| 1 | 0 / 0 | 0.90 [0.83, 0.96] | 0.73 [0.67, 0.79] | 0.57 [0.52, 0.63] | 3 / 8 / 1 |

Coherence cells are out of 12 (snapshot × level), retrieval measures out of 12.
<!-- /table:alpha_sweep -->

**Best candidate selection rule**: a variant is eligible unless distinguishably worse than the pre-sweep default (paired HARI
difference at the last snapshot wholly below zero, or over-claim interval wholly above); the eligible variant with the most robust coherence cells 
wins, since coherence alone tests with a held-out ruler whether groups mean something. 

**Trade-offs** of α = 0.75: less robust to perturbation at the first snapshot, and less consistent across
one of temporal transitions; α = 1 is the most resisitant to perturbation largely because its score ignores the edges (only the prior's stable
set depends on them), but loses largly on coherence; α = 0.75 has the highest over-claim of the five variants, though its
interval overlaps the pre-sweep default's; retrieval does not show a clear direction, with type-A reach worse. The choice is optimistic: α was selected on the data that report its quality, and the stability guard was revised once after the results were read (Appendix B §9).

### 5.3 Evaluation of α = 0.75

Full comparison tables and figures are in Appendix A.5.

**Coherence.** Under the exact filter, every level of the two latest snapshots co-assigns citation-coupled, concept-disjoint papers more than
both nulls under every scheme, and no cell lies below both nulls; earlier snapshots provide fewer pairs, and the first
has one period stratum, so it is not evaluable. p-values are not corrected across cells, and the tests
are conditional on these papers: every lift's paper-bootstrap interval includes chance, so the effect is not shown to
generalise beyond this corpus. 

**Stability.** Robustness falls
from the first to the last snapshot; change concentrates on old nodes in new papers' edges everywhere, yet the other old
nodes carry most of the reassignment and few cross-snapshot indices beat the new-paper null; without a γ = 0 control,
localisation is not attributed to Π. No super-node dies, since
snapshots only grow. 

**Faithfulness.** Most labels over-claim, L1 more than L0, so coarse labels are the more
trustworthy. 

**Utility.** Drill-down returns no more type-A methods than flat search, reaches fewer type-A questions
(losing them at L1), and scores fewer candidates but needs more inspection.

### 5.4 Why α = 0.75 is the ship candidate

We propose α = 0.75: it has more robust coherence cells than any other variant and none below both null models, at no
measurable cost in stability at the last snapshot or in overall label faithfulness. Semantic claims should be restricted to its robust
cells. Retrieval quality was not considered in the decision, since the results mixed and no retrieval utility could be established at this point.

### 5.5 Extra: coherence on paper abstracts

*This check was not asked for in the assignment. It has been implemented as an additional evaluation measure to sanity check the resulting L0 super-node semantic coherence.*

As a ruler independent of citations, an LLM model rated every pair of ≤2026 papers with an abstract for topical closeness
(0–10), from titles and abstracts only; each paper belongs to the L0 super-node of its method. Pairs within and across
super-nodes are compared with a paper bootstrap and a permutation null with sizes fixed (`eval/extra/REPORT.md`).

*Table 4 (extra). LLM-rated closeness of paper abstracts within vs across L0 super-nodes (`abstract_coherence`).*

<!-- table:abstract_coherence -->
| Item | Value (phi4, ≤2026, L0, α = 0.75) |
|---|---|
| Papers with an abstract; L0 super-nodes holding them | 49 of 52; 12 of 15 |
| Pairs rated, same / different L0 super-node | 144 / 1032 |
| Mean closeness (0–10), same / different | 5.97 / 5.37 |
| Difference [95% paper-bootstrap CI] | 0.60 [0.02, 1.20] |
| Permutation null (R = 9999): mean; 97.5% q.; p | -0.00; 0.42; 0.0036 |
| Difference, one of 8 super-nodes with ≥ 2 papers left out: min; max | 0.46 (without L0.1); 0.70 (without L0.16) |
<!-- /table:abstract_coherence -->

Same-super-node papers are rated closer: the bootstrap interval excludes zero, the difference exceeds the null's 97.5%
quantile, and it stays positive with any one multi-paper super-node left out. The effect is modest in one narrow field, and the check depends on names and an unvalidated rater.

## 6. Limitations and future work

**What is verified, measured and assumed.** Laminarity and exact budgets (P1–P2), the collapse rule, snapshot-only
membership and the identity log hold by construction and are checked by `validate.py` on every run. Coherence,
stability, faithfulness and utility are measured, with uncorrected tests on this one corpus, and α was selected on the
same data. The results rest on six assumptions:

1. *Meaning is a lexical proxy.* Character n-grams relate spellings, not the methods the names refer to, and a shared
   node is anchored to its earliest paper. Neither choice was validated with cluster examples or sensitivity checks.
2. *Citation coupling indicates topical closeness*, although shared benchmarks also produce it.
3. *Relations within one paper indicate relatedness.*
4. *Untouched structure should keep its grouping.* No γ = 0 control isolates the effect of the temporal prior.
5. *No post-cutoff information enters*, although aliases come from the whole export.
6. *The level budgets suit the corpus.* Other budgets were not tested.

**With four more weeks** we would:

- replace character n-grams with an embedding model fitted on pre-cutoff text, or with LLM judgements of node and
  super-node similarity;
- add the LLM labels and glosses to super-node similarity, and use a separate α per level;
- tune γ (including γ = 0), ρ, the hub fraction and the retrieval settings (super-nodes kept, answers returned) on one
  half of the data, and report on the other;
- test retrieval on synthetic question–answer pairs, with a development/test split, claim-identity scoring and paired
  confidence intervals;
- validate the rulers and labels with blind ratings, a second judge, repeated evidence splits and a label-distinctness
  check;
- compare multiplicity-aware collapse rules between presence and clique, multi-hop affinity, and DynHAC-style local
  updates [3].

## References

1. B. Kamiński, P. Misiorek, P. Prałat, F. Théberge. Modularity based community detection in hypergraphs. *J. Complex
   Networks*, 2024.
2. M. Kumar, A. Sharma, S. Saxena, S. Kumar. Featured graph coarsening with similarity guarantees. *ICML*, 2023.
3. S. Yu, L. Dhulipala, J. Łącki, N. Parotsidis. DynHAC: Fully dynamic approximate hierarchical agglomerative
   clustering. *SDM*, 2025.
4. Sajadinia, Feng. HyperEF 2.0: Spectral hypergraph coarsening via Krylov subspace expansion and resistance-based
   local clustering. *ICCAD*, 2025 (arXiv:2511.06600).
5. P. S. Chodrow. Configuration models of random hypergraphs. *J. Complex Networks*, 2020.
6. D. Chakrabarti, R. Kumar, A. Tomkins. Evolutionary clustering. *KDD*, 2006.
