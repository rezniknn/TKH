# Null models in hypergraph clustering: Perplexity Deep Research output (verbatim, unverified)

Tool: Perplexity Deep Research with the Academic connector enabled, as a follow-up in the same thread as the clustering-methods review (`hypergraph_clustering_review_perplexity.md`).

Prompt: "In the research papers studied earlier, what is typically used as a null model to compare results of more advanced algorithms against?"

The report below is verbatim, as supplied by the user as an attached file. Its `[cite:N]` markers point to Perplexity's internal source list, which was not exported, so the citations cannot be traced from this file.

---

# Null Models Used in Hypergraph Clustering Research

## Executive summary

The most common null model in the hypergraph-clustering literature reviewed is a **degree-preserving random hypergraph model**, usually a hypergraph analogue of the configuration model.[cite:433][cite:3] It preserves important low-level properties of the observed hypergraph—especially node degrees and often hyperedge sizes—while randomising which nodes participate together, so it provides an expected baseline for how many within-cluster hyperedges would occur by chance.[cite:433][cite:3]

For the temporal knowledge-hypergraph problem, that standard structural null should be extended with semantic and temporal controls, because structure-only nulls do not test whether gains come from the semantic signal or from persistence across snapshots.[cite:24][cite:605]

## Main null-model families

| Null model | What it preserves | What it tests | Relevance to the problem |
|---|---|---|---|
| Uniform random hypergraph | Number of nodes, hyperedges, and sometimes hyperedge sizes | Whether clusters outperform completely random structure | Too weak for a knowledge hypergraph |
| Hypergraph configuration model | Node degrees and often hyperedge-size sequence | Whether clustering exceeds degree-driven structure | Strong default baseline[cite:433][cite:621] |
| Degree-corrected hypergraph SBM | Degree heterogeneity plus community-generation parameters | Whether detected groups explain structure beyond heterogeneous activity | Useful for synthetic benchmarking[cite:259][cite:589] |
| Microcanonical degree-corrected model | Exact degree sequence and hyperedge–community intersection counts | Whether a partition compresses structure better than a constrained random model | Strong for information-theoretic evaluation[cite:605] |
| Attribute-preserving null model | Structural properties plus shuffled or conditionally preserved attributes | Whether semantic coherence exceeds what structure or attribute frequencies explain | Important for structure–semantics experiments[cite:24] |
| Temporal null model | Snapshot sizes, degree distributions, and possibly persistence rates | Whether temporal stability exceeds random persistence | Needed for temporal evaluation, but less standard[cite:365] |

## Hypergraph configuration model

The most direct analogue to the graph configuration model is a random hypergraph that preserves node participation counts and, depending on the formulation, hyperedge sizes.[cite:433][cite:621] In the hypergraph modularity literature, the null model is explicitly designed as the random expectation against which within-community hyperedges are compared.[cite:433][cite:621]

A practical interpretation is:

1. Preserve each node’s hyperdegree.
2. Preserve the multiset of hyperedge cardinalities.
3. Randomly rewire node memberships.
4. Reject invalid or duplicate hyperedges if needed.
5. Repeat many times.
6. Compare the observed clustering statistic with the null distribution.

This is typically the strongest default baseline for scientific knowledge hypergraphs because it controls for hub nodes and uneven participation frequency, both of which can otherwise make community structure appear stronger than it really is.[cite:433][cite:3]

A generic modularity-style comparison can be written as:

\[
Q(H, P)
=
S_{\text{observed}}(H,P)
-
\mathbb{E}_{H' \sim \mathcal{N}(H)}
\left[
S_{\text{random}}(H',P)
\right]
\]

## Degree-corrected hypergraph block models

Several papers use a **degree-corrected hypergraph stochastic block model** as a generative reference rather than a pure null model.[cite:259][cite:589] The DCHSBM generates clustered hypergraphs with heterogeneous node degrees and hyperedge sizes and leads to likelihood-based community objectives.[cite:259][cite:589]

This matters because the DCHSBM is usually not the “no-structure” null. Instead, it is a community-generating model used for theory, benchmarking, or deriving objectives.[cite:259][cite:611] In synthetic studies, researchers often generate data from an HSBM or DCHSBM with known labels and then compare recovery quality using ARI, NMI, or misclassification error.[cite:611][cite:622]

## Microcanonical degree-corrected nulls

Information-theoretic hypergraph methods often use a **microcanonical degree-corrected model**, which preserves constraints such as degree sequences and the structure of community–hyperedge intersections while randomising the remaining detail.[cite:605] This creates a stronger reference than a simple rewiring baseline because it conditions on the partition-relevant statistics directly.[cite:605]

For the current problem, this kind of null is useful when evaluating whether a hierarchy truly explains the incidence structure better than a constrained random alternative, rather than merely looking organised by eye.[cite:605]

## Uniform random hypergraph

A weaker baseline is the uniform random hypergraph model, which may preserve the number of nodes, the number of hyperedges, and possibly the hyperedge-size distribution, but not node degrees.[cite:616][cite:615] It is acceptable as a sanity check, but usually too weak for real data with heterogeneous participation patterns.[cite:615][cite:616]

For scientific knowledge hypergraphs, this model tends to overstate significance because high-degree entities naturally induce more apparent internal structure even without meaningful communities.[cite:433][cite:615]

## Attribute-preserving nulls

Because the target method combines structure and semantics, a structural null alone is not sufficient for evaluation.[cite:24] The literature directly supports using node attributes jointly with structure, which implies that structure-only controls cannot explain whether semantic gains are genuine or incidental.[cite:24][cite:25]

The most relevant semantic-control nulls are:

- **Structure-preserving, semantic-shuffled null:** preserve the hypergraph and node types, but permute text embeddings or descriptions.
- **Semantic-preserving, structure-shuffled null:** preserve embeddings and node metadata, but rewire hyperedges.
- **Type-preserving null:** shuffle only within entity types so that clustering does not get undeserved credit for obvious category grouping.

These are not always the published default in classical hypergraph papers, but they are the most appropriate extension for a structure–semantics abstraction task.[cite:24][cite:581]

## Temporal nulls

Temporal null models are less standard in the reviewed hypergraph-clustering literature than static structural nulls.[cite:365] Still, they are necessary for evaluating whether cluster persistence across time is genuine or simply caused by stable marginal statistics.[cite:365]

Useful temporal controls include:

- **Independent-snapshot null:** randomise each snapshot independently while preserving node count, hyperedge count, degree distribution, and hyperedge-size distribution.
- **Degree-preserving temporal rewiring:** preserve the basic snapshot statistics but rewire memberships within each timestamp.
- **Persistence-matched null:** preserve the observed rate of node or hyperedge persistence while randomising which entities remain grouped together.

A stability comparison can then be framed as:

\[
\text{stability}_{\text{observed}}
-
\mathbb{E}
\left[
\text{stability}_{\text{null}}
\right]
\]

## What is not a null model

Several comparisons often appear in empirical sections but should not be confused with null models. Standard graph Louvain on a projection, spectral clustering, semantic-only clustering, or k-means are **baseline algorithms**, not random reference models.[cite:273][cite:568]

For the final report, it is important to distinguish clearly between:

- **null model:** a randomised data-generating reference;
- **baseline algorithm:** a competing clustering method;
- **ablation:** the proposed method with one signal removed.

That distinction makes the evaluation design methodologically clearer and easier to defend.[cite:24][cite:605]

## Recommended null-model suite

For the assignment, the most defensible setup is a layered null-model suite rather than a single baseline.[cite:433][cite:24] The minimum recommended set is:

1. **Degree- and hyperedge-size-preserving configuration model** as the primary structural null.[cite:433][cite:621]
2. **Semantic-shuffle control** to test whether semantic coherence exceeds what structure alone explains.[cite:24]
3. **Temporal rewiring control** to test whether stability exceeds what static snapshot statistics imply.[cite:365]

A fuller evaluation suite is shown below.

| Null model | Preserve | Purpose |
|---|---|---|
| N0: Uniform random | Node count, hyperedge count, size distribution | Basic sanity check |
| N1: Degree-preserving configuration | Node hyperdegrees and hyperedge sizes | Main structural null[cite:433][cite:621] |
| N2: Type-preserving configuration | N1 plus node types | Controls for entity-type composition |
| N3: Semantic shuffle | N1 plus shuffled embeddings | Tests whether semantics add value[cite:24] |
| N4: Structure shuffle | Embeddings and types, rewired hyperedges | Tests whether structure adds value[cite:24] |
| N5: Temporal rewiring | Snapshot statistics and timestamps | Tests temporal stability[cite:365] |
| N6: Persistence-matched null | Snapshot statistics plus persistence rates | Strongest temporal control |

## Evaluation protocol

For each null model, generate multiple randomised instances, run the same clustering and evaluation pipeline, keep the algorithmic parameters fixed, and compare the observed score with the null distribution.[cite:433][cite:605] This makes the significance of improvements much more defensible than reporting a single observed metric in isolation.[cite:433][cite:605]

A standardised effect size for a metric \(M\) can be written as:

\[
z_M
=
\frac{
M_{\text{observed}}
-
\operatorname{mean}(M_{\text{null}})
}{
\operatorname{std}(M_{\text{null}})
}
\]

An empirical one-sided p-value can be estimated as:

\[
p
=
\frac{
1 + \sum_{r=1}^{R}
\mathbf{1}
\left[
M_r^{\text{null}}
\geq M_{\text{observed}}
\right]
}{
R+1
}
\]

where \(R\) is the number of null samples.

## Practical recommendation

For the hypergraph-clustering methods reviewed, the answer is straightforward: the **typical default null model** is a **degree-preserving, often hyperedge-size-preserving random hypergraph**, i.e. a hypergraph configuration-style null.[cite:433][cite:621][cite:3] For the problem at hand, that should be treated as the structural baseline and then extended with semantic-shuffle and temporal-rewiring controls so that gains in semantic coherence and temporal stability can be attributed correctly.[cite:24][cite:365]
