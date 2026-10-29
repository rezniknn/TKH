# SHAC-T against four prior methods

This document positions SHAC-T (`docs/formal_statement.md`, `tkh/coarsen.py`, `tkh/hierarchy.py`) against four arXiv papers. It also lists the improvement hypotheses that the comparison suggests.

| id | paper | what it actually is | code |
|---|---|---|---|
| **HEF2** | Sajadinia & Feng, *HyperEF 2.0: Spectral Hypergraph Coarsening via Krylov Subspace Expansion and Resistance-based Local Clustering*, arXiv 2511.06600v1 (ICCAD 2025) | structural hypergraph coarsening | [Feng-Research/HyperEF2.0](https://github.com/Feng-Research/HyperEF2.0) @22f7f48, Julia |
| **DYN** | Yu, Dhulipala, Łącki, Parotsidis, *DynHAC: Fully Dynamic Approximate Hierarchical Agglomerative Clustering*, arXiv 2501.07745v1 | dynamic average-linkage HAC on a weighted graph; not coarsening in the spectral sense | [yushangdi/dynamic-hac](https://github.com/yushangdi/dynamic-hac) @b4d39a6 (experiments); core in [google/graph-mining](https://github.com/google/graph-mining) @aaf5a5a `in_memory/clustering/dynamic/hac/`, C++ |
| **HLV** | Kamiński, Misiorek, Prałat, Théberge, *Modularity Based Community Detection in Hypergraphs*, arXiv 2406.17556v1 (J. Complex Networks 2024) | hypergraph community detection (h-Louvain) | [pawelwm/h-louvain](https://github.com/pawelwm/h-louvain) @cd68d79, Python |
| **MPC** | Joly & Keriven, *Graph Coarsening with Message-Passing Guarantees*, arXiv 2405.18127v1 (NeurIPS 2024) | coarse propagation operator for GNNs on a plain graph; the coarsening itself is a Loukas (2019) variant | [anjoly/mp-guarantees-graph-coarsening](https://gitlab.inria.fr/anjoly/mp-guarantees-graph-coarsening): **empty**, the README says the code is under licensing review; no code in the public history |

The formal statement already cites HLV as a rejected alternative (§10, as "h-Louvain"). Report §2 cites HyperEF (ICCAD 2022), the predecessor of HEF2, and Loukas (2019), the coarsening that MPC builds on.

**Sources and checks.**
- Paper details come from the arXiv HTML or PDF. For MPC they also come from the NeurIPS camera-ready, which adds the Reddit experiment and the code link.
- Code details come from reading the cloned repositories. None of that code was run.
- The following code-level claims were re-checked by hand:
  - HEF2's `HSC` (`src/Functions.jl`) ignores hyperedge weights.
  - HEF2's default `R = 1.0` (`src/Run_HypperEF_2_0.jl:26`) makes every hyperedge a contraction candidate.
  - In HLV's `last_step` (`h_louvain.py:877`, `:981`), `VolA[m] += deg_v` updates the last loop variable, not `best`.
- Other code-level statements below are from the reading pass and are marked *(read, not run)*.

## 1. Formal definitions side by side

| | SHAC-T | HEF2 | DYN | HLV | MPC |
|---|---|---|---|---|---|
| Input | concept-node hypergraph G_t, node name text, previous partition | weighted hypergraph, no features | weighted similarity graph (50-NN of point vectors) | hypergraph, optional weights, no features | weighted graph; features X used only by the GNN |
| Output | laminar partitions P_{t,0..2} per snapshot | nested multilevel label vector | (1+ε)-approximate average-linkage dendrogram | flat partition (internal levels are discarded) | flat hard partition Q (internal levels are discarded) |
| Criterion | stepwise greedy score s_t = (1−γ)[α F_S(S) + (1−α) F_H(H)] + γ Π; no global objective | contract hyperedges with low effective resistance R_e; local clustering of leftover nodes | merge any edge with w̄ ≥ w̄_max/(1+ε), with w̄(xy) = w(xy)/(\|x\|\|y\|) | maximise α q_H + (1−α) q_{H[2]}, where α follows a schedule from 0 to 1 | greedy contraction sets ranked by Loukas cost on a spectral subspace R |
| Structural term | H = connectivity-cut reduction / √(d_A d_B) on the collapsed incidence (Prop. 1) | R_e from Krylov vectors over the star and clique expansions, with Q_H(χ) = Σ_e w_e max_{u,v∈e}(χ_u−χ_v)² | summed edge weights / size product | binomial Chung–Lu degree tax per (c, d) edge type | Laplacian quadratic form on R |
| Semantics | char-n-gram LSA of names, average linkage S | none | the whole similarity *is* semantic (embedding distance) | none | none in the coarsening |
| Size control | **exact** budgets min(N_k, n_t), plus the cap ρ n_t/N_k | none: indirect via threshold δ and level count L | none: cut threshold ≥ t | none: modularity optimum (resolution γ only) | target ratio r; whether it is hit exactly is not verifiable (Alg. 1 garbled, no code) |
| Hierarchy | nested, 3 levels, laminar by construction | nested multilevel | full dendrogram | internal only | internal only |
| Temporal | snapshots plus a merge prior Π (evolutionary clustering) | none | node insertions and deletions with local recomputation | none | none |
| Labels / interpretability | LLM labels, faithfulness judge (M3) | none | none | none | none |

**Collapse of hyperedges after contraction.**
- **SHAC-T** keeps every fine edge as one coarse edge over its λ_e super-nodes:
  - λ_e = 1 edges become internal and are kept as metadata;
  - edges with λ_e ≥ 3 stay multi-way;
  - endpoint counts are kept as metadata, but the score uses presence only.
- **HEF2** maps each edge to its super-node set, removes duplicate edges and drops edges left with one super-node.
  - Duplicates keep the first edge's weight; weights are not summed *(read, not run)*.
  - So multiplicity is lost twice: within an edge and across duplicate edges.
- **HLV** keeps the original hyperedges and stores each super-node's multiplicity c in each edge.
  - The score is built on (c, d) directly: η_{c,d} = (c/d)^τ, counted only for c > d/2.
- **DYN** (a plain graph) sums parallel edges and drops self-loops.
- **MPC** forms A_c = (Q^+)^T A Q^+ and drops the diagonal. Its propagation operator is S_c^MP = Q S Q^+, which is asymmetric.

**Correspondences worth stating precisely.**
- **SHAC-T's S is exactly average linkage.** The mean-vector inner product equals the average pairwise cosine, which is DYN's normalised weight w̄ on a complete cosine graph.
- **H is not average linkage.** It uses Salton (√(d_A d_B)) normalisation on set-union presence, so it is **not reducible**. Example: if C shares one edge with A and a different edge with B, and A and B each have degree 1, then H(A ∪ B, C) = √2 · H(A, C) > max(H(A, C), H(B, C)).
  - The cap and the Π term add further non-monotonicity.
  - Consequence: DYN's (1+ε)-good-merge theory and its locality theorem do not transfer to SHAC-T as is.
- **SHAC-T's `projection` variant is average linkage on the 2-section** with weights w_e/(|e|−1), normalised by the hypergraph degrees.
  - HLV's degree-preserving 2-section uses the same w_e/(|e|−1) weighting.
  - HLV's own heuristic, C(c,2)/C(d,2) ≈ (c/d)², places the 2-section near τ = 2.
  - Presence (native H) ignores multiplicity entirely. The two SHAC-T variants are therefore two points of a multiplicity family that HLV parameterises with τ.
- **The λ−1 cut and HEF2's Q_H.** SHAC-T's merge gain is the reduction of the λ−1 (connectivity) cut. HEF2's Q_H = Σ_e w_e (max − min)² is the quadratic form of the all-or-nothing splitting function. These are different splitting functions in the sense of Veldt, Benson and Kleinberg (2022).

## 2. Assumptions and limitations

| | key assumptions | main limitations |
|---|---|---|
| SHAC-T | A1 within-paper co-occurrence is relatedness; A2 names carry weak semantics; A3 the previous partition is a valid prior; A4 provenance year = entry time; A5 export-wide names do not leak | greedy and irreversible; no optimality guarantee; dense O(n²) memory; non-reducible score; H is zero for 98–99% of singleton pairs; nulls not beaten on M1 or M4 (report §5) |
| HEF2 | low effective resistance marks tightly connected hyperedges; graph results on ER-diameter clusters (Alev et al.) "extend naturally" to hypergraphs, which is asserted, not proved | no supernode count control; no features; the clique expansion is quadratic in edge size (the sampling fix is commented out); the code ignores input weights; evaluated on VLSI only, against hMETIS only, without HyperEF |
| DYN | positive similarities; average linkage is the target; the k-NN graph is a good proxy | no target k; the dendrogram can only be cut above t; worst-case update cost equals recomputation; insertions and deletions cannot be mixed in one call |
| HLV | latent communities exist; an edge is evidence only for its majority community; the user picks τ | stochastic (the seeded core is reproducible, `last_step` is not seeded); no count control; resolution limit; tested on n ≤ 1,434; the default `hmod_tau="infinity"` (strict) differs from the paper's recommended τ = 2 |
| MPC | the projection Π preserves ker(L); features lie in the first K eigenvectors (homophily); linear activation (SGC) for the training bound | the coarsening is expensive (eigendecomposition, inversion); only the largest connected component is used; ReLU/GCN is not covered by Thm 2; no code |

**What is unique to SHAC-T in this set:**
- exact per-level budgets with laminarity (P1, P2);
- a hyperedge-preserving collapse rule (T4);
- semantic and structural signals combined on one scale;
- coupling between snapshots;
- labels that are tested for faithfulness.

**What SHAC-T lacks that others have:**
- an explicit approximation guarantee (DYN, MPC);
- incremental updates with provable locality (DYN);
- multi-hop structural affinity (HEF2, through spectral smoothing);
- a scalable sparse implementation (DYN, HEF2).

## 3. Evaluation metrics

| | intrinsic | extrinsic / downstream | baselines | nulls / statistics |
|---|---|---|---|---|
| SHAC-T | perturbation ARI and HARI, cross-snapshot ARI, change localisation, giant share | M1 residual citation lift (held-out signal), M3 label entailment, M4 known-item retrieval cost | flat lexical, PPR, degree, a foreign baseline | configuration-model null, jackknife CIs, Holm-corrected primaries, dev/report split |
| HEF2 | average cluster conductance Φ_avg (Eq. 18), runtime | cut size when used inside KaHyPar (ISPD98, Titan23) | hMETIS; inside KaHyPar: Louvain, HyperEF, HyperSF | none; no seeds, no variance |
| DYN | update time, speedup | NMI against class labels (best of 40 cut thresholds) | static ParHAC, GRINCH, GraphGrove | none |
| HLV | modularity q_H, (c, d) edge composition tables | AMI against ground truth; ΔAMI vs 2-section Louvain | 2-section Louvain, Kumar et al., AON | 30 h-ABCD graphs per noise level |
| MPC | message-passing error ‖S^k x − Q^+(S_c^MP)^k Q x‖_L, RSA constant ε | node classification accuracy (Cora, Citeseer, Reddit), training time | other coarse propagation matrices (naive, diag, diff, sym) | 10 runs, mean ± std |

**How SHAC-T's evaluation compares.**
- SHAC-T has the only evaluation with a null model, a held-out signal and multiplicity correction.
- None of the four papers evaluates against a degree-preserving null.
- The external-label metrics (NMI, AMI) have no counterpart in this project, because the TKH has no ground-truth partition.
- The metrics of HEF2 (conductance), HLV (q_H) and MPC (MP error) are cheap intrinsic quantities that SHAC-T does not report.

## 4. Implementation details

| | language / stack | complexity | determinism | data scale |
|---|---|---|---|---|
| SHAC-T | Python: numpy, scipy, sklearn | O(n²) memory, O(n(m+d)) per merge (worst case O(n²)) | fully deterministic (ARPACK SVD, index tie-break) | n = 3,980, m = 554 |
| HEF2 | Julia 1.5 (no Project.toml), multithreaded | O(ρ\|E\| + \|E_b\| + Σ_e \|e\|²) | `seed!(1)`; threaded atomic adds can reorder float sums *(read, not run)* | 12.7K–210K nodes |
| DYN | C++/Bazel with parlaylib and gbbs; Python for evaluation | O(R(m+n) log² n) for insertions | hash-based colouring, deterministic | 50K–108K points |
| HLV | Python with hypernetx 2.3.5 and bayes_opt | not stated | seeded core; unseeded `last_step`, which also has the `VolA[m]` bug | ≤ 1.4K nodes |
| MPC | not available | O(T(n+e)D + TN) for training on the coarse graph | not verifiable | 2.1K–233K nodes |

## 5. Improvement hypotheses to validate here

**Protocol.**
- Each hypothesis is a SHAC-T variant or an added metric, evaluated through `scripts/evaluate.py`.
- Report half B and the α selection are already spent (report §5–7). A new hypothesis must be:
  - pre-registered in `configs/eval.toml`;
  - iterated on dev half A;
  - reported once, on a fresh cited-work split or fresh snapshots.
- Changes to the method must keep P1, P2, the cap lemma and determinism; `validate.py` checks the first two.

**H1. Multiplicity-aware collapse (from HLV's τ-family).**
- *Change.* Replace the presence incidence X ∈ {0,1} by the counts raised to a power, c^β. The term becomes H_β(A, B) = Σ_e w_e (c_{A,e} c_{B,e})^β / √(d_A d_B), with d_A = Σ_e w_e c_{A,e}^{2β}.
  - β = 0 is the shipped native score.
  - β = 1 counts member pairs (c_A c_B), as the 2-section and the `projection` variant do, but with cosine normalisation over the counted incidence. β = ½ lies in between.
  - By Cauchy–Schwarz, H_β ≤ 1 for every β.
- *Why.* The projection ablation gave the highest E1a lift in the post-hoc table: 1.75 [1.15, 2.65] at level 1. That is already a lead in report §7.
- *What changes formally.* Prop. 1 is replaced by a cut weighted by the counts.
- *Test.* E1a on the primary no-overlap stratum, as a function of β ∈ {0, ½, 1}, plus E2 perturbation ARI.
- *Diagnostic.* Report HLV-style (c, d) composition tables of the coarse edges per level, next to the λ classes of T4.
- *Kill criterion.* No β beats β = 0 by more than one SE on dev half A.

**H2. Multi-hop structural affinity (from HEF2's Krylov smoothing).**
- *Change.* At singletons, H is zero for 98–99% of pairs, so F_H is in effect binary. Add, or substitute, a graded affinity: the cosine of low-pass filtered random vectors (ρ steps of D^{-1/2} A D^{-1/2} on the star expansion of G_t, then orthogonalised), as in HEF2's `Filter`.
  - The same vectors give an effective resistance per hyperedge. That resistance can down-weight loose edges, i.e. replace w_e = 1/(|e|−1) with a weight that falls with R_e.
- *Predictions.*
  - Perturbation ARI rises, because multi-hop paths survive the removal of a single edge. The current ARI is 0.26 at level 1, not significantly above the null's 0.19.
  - Fewer ties in F_H.
- *Risk.* A1 warns that structure rebuilds papers, and smoothing on per-paper stars may make that worse. Track paper purity (notebook 04).
- *Kill criterion.* No ARI gain over the paired null, or E1a below the shipped value.

**H3. Dirty-region rebuild at snapshot transitions (from DYN).**
- *Change.* For t−1 → t, mark as dirty the super-nodes that contain a node within h hops (h ∈ {1, 2}) of any edge of a new paper. Keep all clean level-k groups as fixed items, and re-agglomerate only the dirty groups and the new nodes under the same budgets.
  - This sits between `freeze` (all old groups fixed, no cap, giant share 0.22) and the shipped γ prior (everything rebuilt).
- *Caveat.* DYN's guarantee (Thm C.2: only a 4-hop neighbourhood can change) relies on reducible average linkage. SHAC-T's score is not reducible (§1), so locality here is a design choice, not a theorem.
- *Predictions.*
  - Change localisation goes up compared with the shipped 1.54 at level 1, 2024→26.
  - Cross-snapshot ARI comes close to `freeze`.
  - Giant share stays near 0.13, since the cap still applies to the dirty items.
  - E1a is not worse.
- *Also measure* the runtime saved per transition.

**H4. Merge-inversion diagnostic (from DYN's good-merge definition).**
- *Change.* None to the method. Log the score of each merge and report the inversion rate per level: the share of merges whose score exceeds that of an earlier merge in the same level.
  - Also report the largest ratio max(w_max(u), w_max(v)) / s(u, v), i.e. how far each merge is from (1+ε)-good.
- *Why.* §1 shows that H, the cap and Π can make merges non-monotone. Inversions make a dendrogram hard to read and its cut points arbitrary.
- *Hypothesis.* Inversions are concentrated in merges that the cap forces. If so, a softer cap (a size penalty instead of the hard mask) would remove most of them without breaking P2.

**H5. Hierarchical retrieval through a coarse propagation operator (from MPC).**
- *Why.* Drill-down loses badly to PPR on E4: median cost 1043 against 3.5. Report §7 already asks for "a drill-down that gets the same structural information as PPR".
- *Change.* Build S on the evaluator's own hypergraph (`tkh/structure.py`, so that test_eval_independence keeps holding).
  - At level k, run PPR with S_c^MP = Q S Q^+, which acts on super-node vectors as Q S Q^+ x_c and lifts back through Q^+.
  - Rank inside the top super-nodes by the fine scores.
- *Metrics.*
  - E4 cost against fine PPR and the current drill-down.
  - MPC's MP error ‖S^k x − Q^+(S_c^MP)^k Q x‖ on the query seed vectors, per level. This is a new intrinsic metric of how much structure each level keeps, comparable across variants and nulls.
- *Caveat.* MPC's bounds need connectivity and a spectral subspace R. G_t is very fragmented (88% of concept nodes lie in at most one edge), so the bound is vacuous here. Use the error only as an empirical quantity.

**H6. Lift error as a continuous coherence ruler (from MPC's RSA constant).**
- *Change.* A complement to M1. Build a held-out per-concept signal x, e.g. the vector of cited works of each concept's papers on dev half A, with the existing residual filter. Report the lift error ‖x − Πx‖² / ‖x‖² per level, against the configuration null and random labels.
- *Why.* It uses every concept node, not only the citing paper pairs, so its intervals may be tighter than those of the pair lift. M1's wide intervals are its main weakness (report §5).
- *Validation.* The metric must pass the existing degradation sensitivity check (ancestor-path swaps) before it can be used.

**H7. Intrinsic descriptors, reported but not used for selection (from HEF2 and HLV).**
- *Change.* Per level, report Φ_avg (average conductance) and the τ = 2 hypergraph modularity on the evaluator's hypergraph, against the configuration null.
- *Caveats.*
  - These descriptors are computed on structure the method also uses, so they are descriptive only, never a selection criterion.
  - They also make SHAC-T comparable to HEF2 and HLV in those papers' own terms.

**H8. Sparse candidate set (from DYN's k-NN graph).**
- *Change.* Restrict candidate pairs to the text k-NN (k ≈ 50) united with the structural neighbours, and keep the best-partner caches on that sparse set. Memory drops from O(n²) to O(nk).
- *Test.*
  - ARI and HARI against the dense build, with the target ≥ 0.95 at every level.
  - Runtime and memory.
  - Required for any export much larger than 4k concepts (formal statement §7).
- *Caveat.* Pairs that are neither text neighbours nor structural neighbours would never merge. Late, cap-driven merges therefore need a fallback (the full scan, used only when the sparse set has no feasible pair).

## 6. What not to borrow, and why

- **Spectral-preservation objectives (MPC/Loukas, HEF2).**
  - P2 makes the super-node counts display constraints, not compression targets.
  - These methods need connected graphs; MPC restricts itself to the largest connected component.
  - G_t is mostly tiny components.
- **Modularity maximisation (HLV).** Already rejected in formal statement §10: it has no count control, a resolution limit, and it rewards paper bundles (A1). HLV's α schedule addresses a "lift-off" problem that SHAC-T's rank mixing does not have.
- **HEF2's contraction rule as a replacement.** It has no exact count and no semantic input, and its leftover-node local clustering merges every isolated node at once. Only its affinity estimate (H2) transfers.
- **DYN's ε-approximation as a guarantee.** It needs reducibility, which SHAC-T's score lacks. H3 and H4 borrow the mechanism and the diagnostic, not the theorem.
