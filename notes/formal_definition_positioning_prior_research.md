# Positioning the Formal Definition and SHAC Against Prior Research

## Overview

The formal statement in `formal_statement.md` defines SHAC as a **budget-constrained, semantic–hypergraph, hierarchical agglomerative coarsening method** over temporal knowledge-hypergraph snapshots.[file:779] Its strongest contribution is not a new generic clustering objective in isolation, but the integration of four requirements that prior methods generally treat separately: semantic similarity, native hyperedge handling, hard multi-level budgets, and temporally persistent hierarchy construction.[file:779]

## Relation to prior work

| Requirement in the formal statement | Prior-work area | What prior work provides | What SHAC adds or changes |
|---|---|---|---|
| Laminar hierarchy | Hierarchical agglomerative clustering, dynamic HAC | Hierarchical partitions and dynamic maintenance | Enforces nested partitions directly while also enforcing exact display budgets[file:779][web:785] |
| Semantic–structural reconciliation | Feature-aware graph coarsening | Joint use of graph structure and node features | Extends the idea from graphs to a temporal hypergraph and uses a merge-level semantic/structural score[file:779][web:311] |
| Native hyperedge structure | Hypergraph modularity and spectral hypergraph methods | Hyperedge-aware community objectives | Maintains explicit hyperedge incidence during every merge and defines an implemented collapse rule[file:779][web:126] |
| Hard number of super-nodes | Graph coarsening and multilevel clustering | Reduction ratios or learned coarse graph sizes | Treats \(N_k\) as a hard per-level constraint and proves feasibility under the size-cap condition[file:779] |
| Temporal stability | Dynamic HAC and evolutionary community detection | Efficient updates or temporal smoothness | Uses a localized temporal merge prior plus persistent identity/event tracking[file:779][web:785] |
| Faithful labels | Generally under-addressed | Often post-processes or does not evaluate labels | The task requires evidence-supported labels, although the current implementation still uses placeholders[file:779] |

This combination is the main research positioning. The individual ingredients are recognisable, but their joint formulation for an evolving semantic hypergraph is not directly supplied by the cited prior work.[file:779][web:126][web:311][web:785]

## What was already studied

### Hypergraph community detection

Hypergraph community detection is well established, including modularity-based methods such as h-Louvain. h-Louvain adapts Louvain-style multilevel optimisation to hypergraphs and combines two-section graph modularity with hypergraph modularity during optimisation.[web:126][web:273]

This prior work is directly relevant to SHAC’s structural component. Both methods try to avoid treating higher-order interactions as ordinary pairwise edges, and both use multilevel aggregation ideas.[web:126][file:779]

However, h-Louvain is designed primarily to find communities that optimise a modularity objective. It does not directly solve the SHAC problem of producing a laminar sequence with predetermined numbers of super-nodes \(N_0,N_1,\ldots\), semantic labels, temporal identities, and snapshot-specific event logs.[web:126][file:779] The formal statement explicitly rejects it because community count is controlled indirectly by resolution parameters and because independently optimised resolutions do not guarantee nesting.[file:779]

### Hypergraph coarsening

Hypergraph coarsening has also been studied from a structural and spectral perspective. HyperEF-style approaches use resistance or spectral information to reduce a hypergraph while preserving structural properties, but they are primarily concerned with structural fidelity and coarsening ratios rather than semantic abstraction and exact display budgets.[file:779]

In SHAC, the coarsened hypergraph is not merely an output graph for a downstream solver. It is the actual representation used during subsequent merges: the method updates endpoint presence and recomputes hyperdegrees after every merge.[file:779] That makes the T4 collapse rule operational rather than descriptive.[file:779]

### Feature-aware graph coarsening

Featured Graph Coarsening is especially relevant because it jointly considers a graph matrix and node features, rather than relying only on topology.[web:311][web:500] Its goal is to learn a smaller graph and feature matrix while preserving desired properties and providing similarity guarantees for the coarsened representation.[web:311][web:500]

SHAC follows the same high-level principle: topology and semantic features should influence coarsening jointly. Its implementation differs in several important ways:[file:779]

- FGC operates on ordinary graphs, whereas SHAC operates on explicit hyperedge incidence.[web:311][file:779]
- FGC learns a coarsened graph and feature representation; SHAC greedily merges existing super-nodes.[web:311][file:779]
- FGC targets similarity guarantees for graph coarsening; SHAC provides construction guarantees for laminarity, budgets, and its hyperedge-collapse mechanics, but no global optimisation or semantic-optimality guarantee.[web:311][file:779]
- FGC does not address temporal identity persistence or evidence-supported labels in the formal problem considered here.[web:311][file:779]

Therefore, FGC is a conceptual precedent for the structure–feature combination, not a direct algorithmic substitute.[web:311][file:779]

### Dynamic hierarchical clustering

DynHAC addresses dynamic hierarchical agglomerative clustering under point insertions and deletions. It maintains an approximate average-linkage hierarchy while updating only affected parts of the dendrogram and reports a \(1+\epsilon\) approximation objective for its setting.[web:785][web:479]

This is relevant to SHAC’s temporal dimension, but the problem settings differ:[file:779]

- DynHAC maintains an approximate HAC solution under dynamic point updates.[web:785]
- SHAC receives evolving hypergraph snapshots with new nodes, new hyperedges, changing hub status, semantic representations, and hard level budgets.[file:779]
- DynHAC is primarily concerned with computational maintenance and approximation to average linkage.[web:785]
- SHAC is primarily concerned with semantic abstraction, native hyperedge fidelity, temporal identity, and interpretable fixed-size views.[file:779]

The formal statement therefore borrows the general idea of localized temporal updating but chooses a temporal merge prior rather than a DynHAC-style affected-dendrogram maintenance scheme.[file:779][web:785]

## What was not jointly studied

The gap is best stated carefully. The prior literature does not show that each individual component is new; rather, it does not provide a single validated solution to the complete requirement set.[file:779][web:126][web:311][web:785]

### Hard budgets plus laminarity

Many community-detection methods choose the number of clusters through a resolution parameter, an objective optimum, or a coarsening ratio. SHAC instead requires:

\[
|P_{t,k}|=\min(N_k,n_t)
\]

for every snapshot \(t\) and level \(k\).[file:779]

The hierarchy is laminar because level \(k\) begins from the super-nodes at level \(k+1\) and only merges them. The budget is enforced by stopping at the target count, while the size cap guarantees that a feasible merge remains available when \(\rho\geq 2\).[file:779]

This exact combination—nested partitions with prescribed display counts and an implemented hypergraph collapse rule—is not supplied by h-Louvain, FGC, or DynHAC.[file:779][web:126][web:311][web:785]

### Semantic coherence plus native hyperedges

Feature-aware graph coarsening establishes the importance of combining attributes with structure, but it does not address hyperedges directly.[web:311] Hypergraph community detection preserves higher-order relations, but the cited methods do not formulate the same text-semantic abstraction problem.[web:126][web:273]

SHAC makes this trade-off explicit through:

\[
s(A,B)
=
\alpha F_S(S(A,B))
+
(1-\alpha)F_H(H(A,B)).
\]

Here:

- \(S(A,B)\) is semantic similarity between aggregate node representations.[file:779]
- \(H(A,B)\) is hypergraph incidence similarity.[file:779]
- \(F_S\) and \(F_H\) are frozen mid-rank empirical CDF transforms.[file:779]
- \(\alpha\) controls the structure–semantics trade-off.[file:779]

The rank transformation is a design choice specific to SHAC. It places semantically and structurally different quantities on a common \([0,1]\) scale, rather than adding raw cosine and hypergraph-linkage values.[file:779]

### Temporal stability plus semantic re-coarsening

Dynamic HAC studies efficient hierarchy maintenance, while evolutionary community detection studies temporal smoothness. SHAC combines temporal continuity with a changing semantic–hypergraph input and hard budgets.[file:779][web:785]

Its temporal score is:

\[
s_t(A,B)
=
(1-\gamma)s(A,B)
+
\gamma\Pi(A,B),
\]

when both candidate aggregates contain stable old nodes.[file:779] \(\Pi(A,B)\) measures whether their stable members shared a previous-level super-node.[file:779]

This is neither pure recomputation nor a hard freeze:

- with \(\gamma=0\), snapshots are built independently;[file:779]
- with \(\gamma>0\), prior identities influence merge choices;[file:779]
- with \(\gamma=1\), the method approaches a freeze-like temporal prior.[file:779]

The proposed mechanism is therefore a compromise between adaptation and persistence.[file:779]

### Label faithfulness as a measured requirement

The formal problem includes P6: generated labels and glosses must assert nothing unsupported by their members.[file:779] The attached implementation does not yet satisfy this part: it generates deterministic placeholder labels, and validation checks only that labels are non-empty.[file:779]

This is an important distinction between the formal problem and the current method. Evidence-supported generation, NLI/entailment checks, and over-claim-rate measurement were required by the task but remain unimplemented in the current formal statement’s output status.[file:779]

## How SHAC coarsening works

At each level, SHAC starts with the finer-level super-nodes and repeatedly merges the feasible pair with the highest score until the requested budget is reached.[file:779]

The merge score has three components:[file:779]

1. semantic similarity of aggregate node representations;[file:779]
2. native hypergraph incidence similarity;[file:779]
3. temporal similarity to the previous snapshot’s hierarchy.[file:779]

The feasibility constraint is:

\[
|A|+|B|
\leq
\rho\frac{n_t}{N_k}.
\]

This prevents one merge from creating a super-node substantially larger than the intended average size. Unlike ordinary agglomerative clustering, the cap is part of the method rather than an after-the-fact visualisation rule.[file:779]

## Comparison with alternative coarsening approaches

| Method | Representation | Objective or criterion | Budget handling | Semantics | Temporal treatment | Hierarchy guarantee |
|---|---|---|---|---|---|---|
| h-Louvain | Hypergraph plus two-section graph | Hypergraph modularity mixed with graph modularity | Indirect through resolution | No explicit text-semantic term | No intrinsic temporal coupling | No guaranteed laminar levels [web:126] |
| Spectral hypergraph coarsening | Native or expanded hypergraph spectral structure | Preserve spectral/resistance properties | Coarsening ratio or reduction target | Generally no semantic term | Generally static | Not necessarily a semantic hierarchy |
| Featured Graph Coarsening | Ordinary graph plus node features | Joint structural and feature preservation | Learned reduction size | Yes, through features | Static | No temporal identity mechanism [web:311] |
| DynHAC | Pairwise similarity graph or points | Approximate average linkage under updates | HAC-defined hierarchy | Depends on input similarity | Dynamic insertions/deletions | Approximate HAC maintenance [web:785] |
| Clique expansion | Pairwise graph generated from hyperedges | Any graph algorithm applied after projection | Depends on downstream method | Only if added separately | None by itself | Depends on downstream method |
| SHAC | Explicit hypergraph incidence plus semantic node representations | Greedy rank-normalized semantic–hypergraph score plus temporal prior | Hard \(N_k\) targets and size cap | Explicit | Localized prior and persistent IDs | Laminarity by construction [file:779] |

## Relation to clique expansion

At singleton level, SHAC’s structural numerator resembles a weighted clique-expansion score because two singleton nodes receive credit when they participate in the same hyperedge. The difference appears after aggregation.[file:779]

For an edge \(e\), SHAC uses endpoint presence:

\[
\mathbf{1}[A\in e]\mathbf{1}[B\in e].
\]

A clique-style aggregate would effectively count member pairs, proportional to:

\[
c_{A,e}c_{B,e}.
\]

Therefore, if a hyperedge has multiple endpoints already inside one super-node, clique expansion gives that edge more influence according to endpoint multiplicity, while SHAC counts the edge once for the pair of super-nodes it connects.[file:779]

This is a substantive methodological difference. It prevents a large paper-level hyperedge from automatically making already-large paper bundles more attractive merely because they contain more of its members.[file:779]

The formal statement reports that multi-endpoint situations are common in the actual build, so the native and clique-style scores diverge for many merges rather than only in rare edge cases.[file:779]

## Relation to h-Louvain

SHAC and h-Louvain share a recognition that pairwise projection can obscure higher-order structure. h-Louvain uses a dynamically weighted combination of two-section modularity and hypergraph modularity during a multilevel optimisation process.[web:126][web:273]

SHAC differs in four ways:[file:779]

1. **Target:** h-Louvain seeks communities; SHAC constructs a budgeted hierarchy.[web:126][file:779]
2. **Objective:** h-Louvain optimises modularity; SHAC uses greedy merge scores and makes no global optimality claim.[web:126][file:779]
3. **Semantics:** SHAC includes node-name representations explicitly.[file:779]
4. **Temporal structure:** SHAC includes a previous-snapshot merge prior and persistent identity tracking.[file:779]

The trade-off is that h-Louvain has a more conventional community-quality objective, whereas SHAC provides stronger construction-level control over output shape.[web:126][file:779]

## Relation to spectral coarsening

Spectral coarsening methods typically aim to preserve global graph properties, such as Laplacian structure, effective resistance, or downstream spectral behaviour.[file:779] That is valuable when the coarse graph must remain mathematically similar to the original graph.

SHAC has a different primary notion of fidelity:[file:779]

- semantic similarity of grouped concepts;[file:779]
- hyperedge incidence preservation;[file:779]
- hierarchy shape;[file:779]
- temporal persistence;[file:779]
- human navigability.[file:779]

Consequently, SHAC should not claim spectral equivalence. Its appropriate comparison is empirical: compare native SHAC with a spectral or HyperEF-style baseline on hyperedge cut, structural similarity, semantic coherence, temporal stability, and retrieval utility.[file:779]

## Relation to DynHAC

SHAC resembles dynamic HAC because both build hierarchical structures through merges and address changing data. DynHAC, however, seeks efficient approximate maintenance of average-linkage structure and identifies dendrogram regions that need updating.[web:785]

SHAC instead re-runs a constrained agglomeration at each snapshot, but uses a temporal prior to make merge decisions consistent with previous structure. This is simpler to implement and preserves hard budgets, but it is more path-dependent and does not provide DynHAC’s approximation guarantee.[file:779][web:785]

The formal statement correctly identifies the trade-off:[file:779]

- SHAC gains exact budget control, deterministic output, and a smooth stability parameter;[file:779]
- SHAC pays with greedy irrevocability, path dependence, and no global optimality guarantee.[file:779]

## What the current results actually establish

The formal statement distinguishes construction guarantees from empirical evidence.[file:779]

### Guaranteed by construction

- laminar refinement;[file:779]
- budget compliance;[file:779]
- native hyperedge-collapse application;[file:779]
- deterministic tie-breaking;[file:779]
- snapshot-specific membership cutoff;[file:779]
- persistent IDs and validated event-log structure.[file:779]

### Empirical rather than guaranteed

- semantic coherence;[file:779]
- temporal stability magnitude;[file:779]
- robustness to perturbations;[file:779]
- usefulness for retrieval;[file:779]
- any superiority over competing methods.[file:779]

### Not yet established

- faithful generated labels;[file:779]
- a global optimum for the semantic–hypergraph objective;[file:779]
- spectral preservation;[file:779]
- superiority over a true clique-projection baseline;[file:779]
- scalability beyond the several-thousand-node setting.[file:779]

This separation is academically important. The formal statement does not overclaim: it presents SHAC as a deterministic, constrained heuristic with explicit invariants, not as an optimiser with universal optimality or semantic guarantees.[file:779]

## Main research contribution

The strongest defensible contribution is:

> SHAC formulates semantic abstraction over an evolving knowledge hypergraph as a hard-budget, laminar, native-hyperedge agglomeration problem, and implements a merge rule that combines semantic similarity, hypergraph incidence, and temporal continuity.[file:779]

What has already been studied are the components:[file:779][web:126][web:311][web:785]

- hypergraph modularity and community detection;[web:126][web:273]
- graph coarsening;[web:311]
- feature-aware graph coarsening;[web:311][web:500]
- spectral hypergraph reduction;[file:779]
- dynamic hierarchical clustering.[web:785][web:479]

What remains comparatively under-studied is their joint application to a growing scientific knowledge hypergraph where:[file:779]

- the output must have fixed display budgets;[file:779]
- levels must be nested;[file:779]
- hyperedges must remain explicit;[file:779]
- semantic and structural signals must be reconciled;[file:779]
- identities must persist over time;[file:779]
- labels must be evidence-faithful;[file:779]
- evaluation must avoid circularity.[file:779]

The method is therefore best positioned as an **integration and formalisation contribution**, with novelty depending on how rigorously the experiments demonstrate that the combination improves the required task—not merely on the fact that each ingredient is individually new.[file:779]
