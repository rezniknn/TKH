# Literature shortlist — Perplexity Deep Research output (raw, unverified)

Tool: Perplexity Deep Research with the Academic connector enabled. The task brief was uploaded as an attachment.

Prompt: "Find 3-4 best candidate papers most relevant to the research problem I will be solving based on proceed problem statement fully matching requested search criteria. Result should be 3-4 papers with links, brief summary and justification for why they are relevant to my research problem"

This is the output, kept close to verbatim. Citations that pointed to the uploaded brief (temporary pre-signed S3 links) are replaced with `[brief]`. Nothing here has been checked yet.

---

**I recommend the following four papers as a complementary reading set:** h-Louvain, Featured Graph Coarsening, DynHAC, and HyperEF 2.0. Together, they cover the four literature areas requested in your brief: hierarchical community detection, hypergraph clustering, graph coarsening, and dynamic clustering. [brief]

**Important distinction:** these are relevant building blocks—not four complete solutions to P1–P6. Your assessment specifically requires combining semantic coherence, native hyperedge handling, hard size budgets, temporal stability, and faithful labels; the shortlist should support that synthesis rather than imply those requirements are already solved. [brief]

## 1. h-Louvain

**[Modularity Based Community Detection in Hypergraphs](https://doi.org/10.1093/comnet/cnae041)**
Bogumił Kamiński, Paweł Misiorek, Paweł Prałat, François Théberge — *Journal of Complex Networks*, 2024.
[Open-access paper](https://arxiv.org/html/2406.17556) · [Author code](https://github.com/pawelwm/h-louvain)

**Brief summary:** Introduces h-Louvain, a scalable hypergraph community-detection algorithm that transitions from graph modularity toward a tunable hypergraph-modularity objective.

**Why it is relevant:** This is the strongest starting point for your **hyperedge-aware structural objective**. Its strict, majority, and intermediate modularity variants let you explicitly decide how strongly a hyperedge should imply common cluster membership—an important choice when scientific hyperedges contain different entity types. Its multilevel aggregation also provides a starting point for hierarchical abstraction. [brief]

**Critical limitation:** It uses the two-section graph during optimization, although its target objective retains hypergraph information; it is therefore not a projection-free method. Semantic coherence, temporal coupling, and hard display budgets would need additional mechanisms.

**What to borrow:** The hypergraph-modularity formulation and multilevel optimization; explicitly justify your chosen notion of hyperedge homogeneity.

## 2. Featured Graph Coarsening

**[Featured Graph Coarsening with Similarity Guarantees](https://proceedings.mlr.press/v202/kumar23a/kumar23a.pdf)**
Manoj Kumar, Anurag Sharma, Shashwat Saxena, Sandeep Kumar — *ICML*, 2023.

**Brief summary:** Jointly learns a smaller graph and its node-feature matrix, using an optimization framework that incorporates both structural and attribute information.

**Why it is relevant:** Your brief makes the **structure–semantics trade-off** a central research question, rather than an implementation detail. This paper directly informs that formulation: it treats topology and features jointly instead of clustering structurally and adding semantic labels afterward. It is also an appropriate reference for the requested graph-coarsening literature strand.

**Critical limitation:** Its formulation concerns ordinary graphs, not your evolving knowledge hypergraph. Its feature-preservation guarantees should not be presented as guarantees of scientific semantic coherence or transferred automatically to a hypergraph adaptation. [brief]

**What to borrow:** The joint structure–feature objective as a design reference or baseline—not as a ready-made solution to native hyperedge fidelity.

## 3. DynHAC

**[DynHAC: Fully Dynamic Approximate Hierarchical Agglomerative Clustering](https://epubs.siam.org/doi/10.1137/1.9781611978520.24)**
Shangdi Yu, Laxman Dhulipala, Jakub Łącki, Nikos Parotsidis — *SIAM International Conference on Data Mining*, 2025.
[Open-access paper](https://arxiv.org/html/2501.07745v1) · [Author code](https://github.com/yushangdi/dynamic-hac)

**Brief summary:** Maintains approximate average-linkage hierarchical clustering under point insertions and deletions, recomputing affected portions rather than rebuilding the entire hierarchy. ([alphaxiv](https://www.alphaxiv.org/overview/2501.07745))

**Why it is relevant:** This is the most directly useful reference for **maintaining a hierarchy as the corpus grows**. Its affected-partition mechanism gives you a concrete alternative to independent clustering at every snapshot, while its explicit approximation definition helps distinguish algorithmic guarantees from empirical quality claims.

**Critical limitation:** **Efficient dynamic maintenance is not the same as temporal stability.** The paper explicitly acknowledges that a small input change can cause extensive dendrogram changes; it does not guarantee persistent semantic identities or low cross-snapshot churn. It also operates on a pairwise similarity graph.

**What to borrow:** Affected-region updating and reuse of unchanged merges; evaluate identity persistence and hierarchy stability separately, as your brief requires.

## 4. HyperEF 2.0

**[HyperEF 2.0: Spectral Hypergraph Coarsening via Krylov Subspace Expansion and Resistance-Based Local Clustering](https://ieeexplore.ieee.org/document/11240836/)**
2025 — IEEE Xplore publication. (No authors given in the output.)

**Brief summary:** Coarsens hypergraphs using effective-resistance estimates and local clustering, aiming to reduce size while preserving structural properties and improving partition quality.

**Why it is relevant:** This is the closest match to your **explicit hypergraph-coarsening component**. It provides a structural counterpart to feature-aware graph coarsening and a credible alternative against which to defend your method: preserve spectral structure, rather than optimize community modularity.

**Critical limitation:** Its reported experiments concern VLSI benchmarks, not scientific semantic abstraction. It also uses clique and star expansions internally, so citing it does not establish that your implementation satisfies P4; your actual coarse hyperedges must remain explicit and participate in the method.

**What to borrow:** Resistance-based aggregation and structural-preservation criteria; use these to motivate or test your T4 collapse rule, without claiming they establish semantic faithfulness. [brief]

## How to position them

| Paper | Role in your literature synthesis |
|---|---|
| **h-Louvain** | Hypergraph-aware community objective and multilevel aggregation. |
| **Featured Graph Coarsening** | Explicit reconciliation of topology and node features. |
| **DynHAC** | Updating a hierarchy without unconditional full recomputation. |
| **HyperEF 2.0** | Hypergraph coarsening and structural-preservation alternative. |

For your write-up, the defensible research gap is **the integration and independent evaluation of these components under the assessment's constraints**—especially hard level budgets, implemented hyperedge collapse, temporal identity tracking, and faithful labels. Present that as the scope of your proposed method, not as a claim that no prior work anywhere addresses the combination. [brief]
