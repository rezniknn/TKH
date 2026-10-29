# Hypergraph clustering methods: Perplexity Deep Research output (verbatim, unverified)

Tool: Perplexity Deep Research with the Academic connector enabled. The task brief was uploaded as an attachment.

Prompt: "Make a comprehensive literature review of different methods of hyper graph clustering that could be used to create super nodes to enable creating different resolutions of a hyper graph that combine semantic and structural information or use either of the two signals only. For each method, list papers where that method was studied, brief summary of results, evaluate applicability of that approach to my problem statement at hand, list assumptions and limitations of  the method"

The full report below is verbatim, as supplied by the user as an attached file. Its `[web:N]` / `[file:1]` markers point to Perplexity's internal source list, which was not exported. Paper titles, venues, links and claimed results have not been checked.

---

# Literature Review: Hypergraph Clustering for Multi-Resolution Semantic Abstraction

## Executive assessment

For the temporal knowledge-hypergraph assignment, the most promising design is a **hybrid hierarchical method** combining:

1. **Hypergraph-native structural clustering**, preferably hypergraph modularity or a spectral/coarsening objective.
2. **Semantic node representations**, derived from scientific text or node descriptions.
3. **Temporal coupling**, using previous-snapshot assignments or cluster matching.
4. **Explicit hyperedge collapse**, preserving coarse multi-way relations.
5. **Hard level budgets**, enforced during hierarchy construction.

The strongest practical candidates are:

- **Attributed hypergraph stochastic block models** for principled structure–semantics integration.
- **h-Louvain / generative hypergraph modularity** for scalable hypergraph-native community detection.
- **Spectral hypergraph coarsening** such as HyperEF, HyperSF, and SHyPar for structural super-node creation.
- **Hypergraph neural-network clustering** when semantic features are rich and sufficient training data exists.
- **Hierarchical agglomerative clustering with hypergraph-aware similarities** as the simplest implementation route.

No individual method directly satisfies all requirements P1–P6. The assignment requires an integration of clustering, semantic representation, temporal identity tracking, hierarchy construction, label faithfulness, and independent evaluation.

## 1. Problem formulation

The input at time \(t\) is a hypergraph:

\[
H_t = (V_t, E_t)
\]

where:

- \(V_t\) is the set of nodes;
- \(E_t\) is the set of hyperedges;
- a hyperedge \(e \in E_t\) may contain two or more nodes;
- nodes and hyperedges have attributes such as type, text, date, and provenance.

The desired output is a sequence of partitions:

\[
P_0, P_1, \ldots, P_K
\]

where:

- \(P_0\) is the coarsest level;
- \(P_K\) is the finest level;
- each finer partition refines the previous one;
- the number of clusters at each level obeys a hard budget;
- each cluster becomes a super-node.

The assignment requires semantic coherence, hyperedge fidelity, temporal stability, and faithful labels in addition to ordinary clustering quality.

## 2. What “creating super-nodes” means

Suppose the fine-level nodes are:

```text
BERT
RoBERTa
ALBERT
T5
GLUE
SQuAD
accuracy
```

A clustering method could produce:

```text
Super-node A: Transformer language models
Members: BERT, RoBERTa, ALBERT, T5

Super-node B: NLP benchmarks
Members: GLUE, SQuAD

Super-node C: Evaluation metrics
Members: accuracy
```

At a coarser level, Super-node A and Super-node B might be grouped into:

```text
Super-node X: Language-model research
```

The crucial distinction is that a super-node is not simply a randomly sampled subset. It should represent a coherent scientific idea and preserve enough structural information to support navigation and retrieval.

## 3. Method taxonomy

| Method family | Main signal | Hypergraph-native | Naturally hierarchical | Uses node semantics | Temporal support | Suitability |
|---|---|---:|---:|---:|---:|---|
| Hypergraph modularity | Structure | Yes | Partly | No | No | High as structural baseline |
| Hypergraph stochastic block models | Structure | Yes | No | Sometimes | No | High, especially for principled clustering |
| Spectral hypergraph clustering | Structure | Usually | Partly | No | No | Medium–high |
| Spectral hypergraph coarsening | Structure | Yes | Yes | No | No | High for super-node construction |
| Flow-based clustering | Structure and random walks | Yes | Partly | No | Not inherently | Medium–high |
| Hypergraph neural networks | Structure plus features | Yes or semi-native | No | Yes | Sometimes | Medium |
| Attributed probabilistic models | Structure plus attributes | Yes | No | Yes | No | Very high conceptually |
| Pairwise projection plus clustering | Projected structure | No | Depends | Possibly | No | Useful baseline only |
| Hypergraph-aware agglomeration | Combined similarity | Can be | Yes | Yes | Can be added | High for the assignment |
| Information-theoretic clustering | Structure | Yes | Not inherently | No | No | Medium |
| Hypergraph partitioning | Structure and cut objectives | Yes | Yes | No | No | High for constrained grouping |

The most relevant methods are discussed below.

# 4. Hypergraph modularity methods

## 4.1 Basic idea

Modularity-based clustering searches for communities containing more internal hypergraph structure than expected under a null model.

For ordinary graphs, modularity rewards edges whose endpoints fall within the same community. For hypergraphs, the method must define how a hyperedge contributes when:

- all endpoints are inside one cluster;
- most endpoints are inside one cluster;
- the endpoints span multiple clusters.

This choice is central. A strict “all-or-nothing” objective treats a hyperedge as internally coherent only if every endpoint belongs to one cluster. A majority-based objective gives partial credit when most endpoints fall together.

## 4.2 Relevant papers

### Generative hypergraph clustering: From blockmodels to modularity

**Paper:** Chodrow, Veldt, and Benson, *Generative hypergraph clustering: From blockmodels to modularity*, Science Advances, 2021.  
[Paper](https://www.science.org/doi/10.1126/sciadv.abh1303) [web:130][web:589]

The paper introduces a degree-corrected hypergraph stochastic block model with heterogeneous node degrees and hyperedge sizes. Approximate maximum-likelihood inference produces a modularity-like objective and Louvain-style algorithms, including an All-or-Nothing variant for hyperedges expected to remain entirely within communities. [web:130][web:589]

The authors report that hypergraph-specific detection regimes differ from those obtained after dyadic graph projection and demonstrate scalability on synthetic and empirical data, including a synthetic hypergraph with one million nodes. [web:589]

### Modularity Based Community Detection in Hypergraphs

**Paper:** Kamiński, Misiorek, Prałat, and Théberge, *Modularity Based Community Detection in Hypergraphs*, Journal of Complex Networks, 2024.  
[Paper](https://academic.oup.com/comnet/article/12/5/cnae041/7829128) [web:126][web:273]

The paper proposes h-Louvain, an adaptation of Louvain for hypergraph modularity. A direct optimisation often fails to find meaningful communities, so the method uses a dynamically tuned combination of ordinary graph modularity on the two-section graph and the target hypergraph modularity, with Bayesian optimisation of hyperparameters. [web:273][web:126]

The reported experiments on synthetic and real networks show improved results across multiple regimes compared with directly applying the hypergraph modularity objective. [web:273]

### Comparison of modularity-based approaches for node clustering in hypergraphs

**Paper:** Kamiński et al., *Comparison of modularity-based approaches for nodes clustering in hypergraphs*, 2024.  
[Paper](https://peercommunityjournal.org/articles/10.24072/pcjournal.404/) [web:537]

This study provides a unified comparison of hypergraph modularity criteria and available optimisation algorithms. It evaluates ground-truth recovery, runtime, objective maximisation, and the number of detected clusters under controlled synthetic settings. [web:537]

## 4.3 Applicability to the assignment

**Applicability: high for structural clustering; medium for the complete problem.**

Modularity is attractive because it:

- operates directly on hyperedge participation;
- naturally produces hard, non-overlapping communities;
- can be optimised at multiple levels;
- supports comparison between strict, majority, and soft hyperedge treatments;
- provides a clear structural baseline.

It is particularly suitable for building a hierarchy if the algorithm is run in a multilevel fashion:

```text
fine nodes
→ first community partition
→ aggregate communities into super-nodes
→ cluster the coarse hypergraph
→ repeat
```

However, standard modularity does not use semantic descriptions, temporal information, label faithfulness, or hard budgets automatically.

## 4.4 Assumptions

Typical assumptions include:

- nodes belong to discrete communities;
- within-community hyperedge density is meaningfully higher than expected;
- the selected null model is an appropriate representation of random structure;
- one partition is acceptable rather than overlapping memberships;
- hyperedge semantics can be summarised by the chosen modularity function.

## 4.5 Limitations

- **Resolution limit:** modularity can fail to detect small but meaningful communities.
- **Objective ambiguity:** different hypergraph modularities encode different interpretations of an internally coherent hyperedge.
- **No semantic signal:** co-occurrence or citation structure does not necessarily equal meaning.
- **No temporal mechanism:** independent snapshots may reshuffle communities.
- **Potential projection dependence:** h-Louvain uses the two-section graph during its initial stage, so the implementation must be examined carefully if strict native hypergraph processing is required. [web:273]
- **No natural label generation:** cluster labels require a separate evidence-grounded process.

## 4.6 Recommended use

Use hypergraph modularity as:

1. a strong structural baseline;
2. a candidate component of a joint structure–semantic objective;
3. an ablation against semantic-only clustering;
4. a comparison against a pairwise projection baseline.

For your assignment, compare at least:

```text
structure-only: hypergraph modularity
semantic-only: embedding clustering
joint: weighted hypergraph modularity + semantic coherence
```

# 5. Hypergraph stochastic block models

## 5.1 Basic idea

A stochastic block model assumes that nodes belong to latent communities and that the probability of a hyperedge depends on the communities of its endpoints.

A degree-corrected model additionally accounts for highly active nodes or heterogeneous participation rates.

A mixed-membership model allows a node to belong partially to several communities:

\[
\theta_i = (\theta_{i1}, \ldots, \theta_{iK})
\]

where \(\theta_{ik}\) represents node \(i\)'s membership in community \(k\).

## 5.2 Relevant papers

### Generative hypergraph clustering

The DCHSBM of Chodrow, Veldt, and Benson models heterogeneous node degrees and hyperedge sizes, and derives a hypergraph modularity objective from likelihood maximisation. It supports hard clusters and provides a probabilistic interpretation for structural communities. [web:589]

### Community detection in large hypergraphs

**Paper:** Ruggeri, Contisciani, Battiston, and De Bacco, *Community Detection in Large Hypergraphs*, Science Advances, 2023.  
[Paper](https://www.science.org/doi/10.1126/sciadv.adg9159) [web:584][web:231]

This framework uses a mixed-membership stochastic block model for higher-order interactions. Nodes may belong to multiple groups, and the model supports assortative, disassortative, hard, and overlapping community structures. The authors report high recovery accuracy on synthetic benchmarks and scalability to hypergraphs with millions of nodes and interactions. [web:584][web:231]

### Structure and inference in hypergraphs with node attributes

**Paper:** Badalyan, Ruggeri, and De Bacco, *Structure and inference in hypergraphs with node attributes*, Nature Communications, 2024.  
[Paper](https://www.nature.com/articles/s41467-024-51388-5) [web:24][web:25]

This paper combines hypergraph structure with node attributes in a probabilistic model. It learns how much the attributes contribute and can down-weight or discard them when they are uninformative. The model supports weighted or unweighted hypergraphs, categorical or binary attributes, and overlapping communities. [web:24][web:581]

## 5.3 Applicability to the assignment

**Applicability: very high conceptually, but implementation complexity is medium to high.**

The attributed model is one of the closest conceptual matches to your problem because:

- the hypergraph remains native;
- node attributes can represent semantic features;
- structural and semantic evidence are integrated probabilistically;
- the relative contribution of attributes is learned rather than manually fixed;
- uncertainty can be interpreted through model likelihood or membership probabilities.

This is more principled than simply concatenating text embeddings with graph features.

However, there are important mismatches:

- the model is designed for community detection, not necessarily a laminar hierarchy;
- mixed or overlapping memberships conflict with the assignment’s non-overlapping partition requirement;
- temporal evolution is not automatically handled;
- hard per-level budgets are not naturally enforced;
- labels still require a separate procedure.

## 5.4 Assumptions

- communities generate hyperedges according to a specified probabilistic model;
- node attributes have a meaningful statistical relationship to latent communities;
- the selected likelihood family is appropriate;
- the number of communities is known or can be selected;
- observations are sufficiently informative for parameter estimation.

## 5.5 Limitations

- **Model misspecification:** scientific knowledge graphs may contain extraction artefacts and relation types that do not follow the assumed distribution.
- **Overlapping output:** mixed membership is scientifically attractive but must be converted to hard assignments for this task.
- **Computational complexity:** likelihood inference can be more difficult than modularity optimisation.
- **Hierarchy gap:** one model fit gives one partition; repeated fitting does not automatically produce a valid laminar hierarchy.
- **Temporal gap:** a separate temporal prior or sequential inference mechanism is required.
- **Interpretability:** probabilities are useful diagnostically but do not directly produce readable labels.

## 5.6 Recommended use

If you have time for only one sophisticated structure–semantics method, use the attributed hypergraph model as a conceptual reference and possibly as a research-inspired baseline.

For a five-to-seven-day assessment, a full reproduction may be risky. A simpler approximation could use:

\[
J =
\lambda J_{\text{hypergraph}}
+
(1-\lambda)J_{\text{semantic}}
+
\gamma J_{\text{temporal}}
\]

while explicitly explaining that this is an engineering approximation rather than a full generative model.

# 6. Spectral hypergraph clustering

## 6.1 Basic idea

Spectral clustering maps nodes into a low-dimensional representation using eigenvectors of a graph or hypergraph operator, then applies a conventional clustering algorithm such as \(k\)-means.

For hypergraphs, the operator may be based on:

- a hypergraph Laplacian;
- a nonlinear \(p\)-Laplacian;
- a nonbacktracking matrix;
- a Bethe Hessian;
- a tensor operator;
- an incidence-matrix construction.

The basic workflow is:

```text
hypergraph
→ hypergraph operator
→ eigenvectors
→ node embedding
→ clustering
```

## 6.2 Relevant papers

### Learning with Hypergraphs: Clustering, Classification, and Embedding

**Paper:** Zhou, Huang, and Schölkopf, NeurIPS 2006.  
[Paper](https://papers.neurips.cc/paper/3128-learning-with-hypergraphs-clustering-classification-and-embedding.pdf) [web:568]

This foundational work generalises spectral clustering to hypergraphs using a hypergraph Laplacian. It develops methods for hypergraph embedding, clustering, and transductive inference. [web:568]

### Hypergraph Random Walks, Laplacians, and Clustering

**Paper:** Chitra and Raphael, 2020.  
[Paper](https://arxiv.org/html/2006.16377) [web:570]

The paper develops a flexible framework based on random walks and Laplacians for hypergraph clustering. It discusses multiple formulations, including clique-expanded clustering, and analyses how hyperedge-size bias and random-walk choices affect detected communities. [web:570]

### Nonbacktracking Spectral Clustering of Nonuniform Hypergraphs

**Paper:** Chodrow, Eikmeier, and Haddock, SIAM Journal on Mathematics of Data Science, 2023.  
[Paper](https://arxiv.org/abs/2204.13586) [web:569][web:566]

This method addresses nonuniform hypergraphs using a nonbacktracking operator defined on edge-node pairs. It provides an Ihara–Bass-type reduction for eigenpair computation and proposes a spectral clustering algorithm for inference in nonuniform hypergraph stochastic block models. [web:569]

### Higher-order trade-offs in hypergraph community detection

**Paper:** Contisciani, Battiston, and De Bacco, Science Advances, 2023.  
[Paper](https://www.science.org/doi/10.1126/sciadv.aef2184) [web:365]

This work derives a Bethe Hessian operator for nonuniform hypergraphs and studies the trade-offs involved in higher-order community detection. It provides an efficient spectral formulation and model-selection perspective. [web:365][web:591]

### Hypergraph \(1\)-spectral clustering with general submodular weights

This method uses a hypergraph 1-Laplacian and an inverse power method for clustering general submodular hypergraphs. Experiments on real-world data show effective clustering under more general hyperedge weighting schemes. [web:560]

## 6.3 Applicability to the assignment

**Applicability: medium to high for structure; medium for the full assignment.**

Spectral methods are useful because:

- they preserve global structural information;
- they produce continuous representations that can be combined with semantic embeddings;
- they support hierarchical clustering after embedding;
- they can reveal global structure missed by local greedy algorithms.

A promising design is:

\[
z_i =
[
z_i^{\text{spectral}}
\|
z_i^{\text{semantic}}
]
\]

followed by constrained hierarchical clustering.

However, concatenating the two representations is not automatically principled. You need to normalise the spaces and justify their relative weights.

## 6.4 Assumptions

- a suitable hypergraph operator captures community structure;
- leading eigenvectors contain information about the desired communities;
- the number of clusters is known or selected;
- numerical eigensolvers are stable enough for the graph size;
- the selected hypergraph Laplacian reflects the semantics of the application.

## 6.5 Limitations

- **Operator dependence:** different Laplacians can produce materially different results.
- **Nonuniform hyperedges:** operators designed for uniform hypergraphs may be inappropriate.
- **Spectral ambiguity:** eigenvectors may encode connectivity but not scientific meaning.
- **Repeated eigenvalues:** cluster orientations can change across snapshots, harming temporal identity matching.
- **No natural hard budget:** the number of clusters must be selected or constrained externally.
- **No native labels:** semantic interpretation is a separate problem.
- **Computational cost:** eigendecomposition can become expensive for large hypergraphs.

## 6.6 Recommended use

Use a spectral method as:

- a structural representation for a hybrid method;
- an alternative to modularity;
- a source of globally informed node similarity;
- a baseline for evaluating whether semantic features add value.

For a small assignment dataset, a conventional incidence-based Laplacian may be adequate, provided you document exactly how hyperedges are represented.

# 7. Spectral hypergraph coarsening

## 7.1 Basic idea

Hypergraph coarsening contracts groups of strongly related nodes into super-nodes while attempting to preserve structural properties.

The output is naturally a sequence of smaller hypergraphs:

```text
H_0 → H_1 → H_2 → ... → H_K
```

This makes coarsening one of the most directly relevant method families for the assignment.

## 7.2 Relevant papers

### HyperSF: Spectral Hypergraph Coarsening via Flow-based Local Clustering

**Paper:** Aghdaei, Zhao, and Feng, ICCAD 2021.  
[Paper](https://arxiv.org/abs/2108.07901) [web:567]

HyperSF uses strongly local max-flow-based clustering to identify vertex sets that minimise ratio cut. It also uses spectral clustering of bipartite representations for efficiency. Experiments on real-world VLSI hypergraphs show improvements in multi-way conductance and runtime compared with existing coarsening methods. [web:567]

### HyperEF: Spectral Hypergraph Coarsening by Effective-Resistance Clustering

**Paper:** Aghdaei and Feng, ICCAD 2022.  
[Paper](https://arxiv.org/abs/2210.14813) [web:527]

HyperEF uses hyperedge effective resistance to find low-resistance-diameter groups and coarsen large hypergraphs. The paper reports preservation of structural and spectral properties, with substantial speedups over hMETIS and HyperSF on VLSI benchmarks. [web:527][web:105]

### SHyPar: A Spectral Coarsening Approach to Hypergraph Partitioning

**Paper:** Sajadinia, Aghdaei, and Feng, 2024.  
[Paper](https://arxiv.org/abs/2410.10875) [web:598][web:530]

SHyPar combines effective-resistance-based merging with flow-based local clustering in a multilevel partitioning framework. It aims to generate partitions with low conductance and small cut sizes, reporting strong results on VLSI design benchmarks. [web:598][web:530]

### HyperEF 2.0

**Paper:** *HyperEF 2.0: Spectral Hypergraph Coarsening via Krylov Subspace Expansion and Resistance-Based Local Clustering*, 2025.  
[Paper](https://ieeexplore.ieee.org/document/11240836/) [web:427]

The method improves effective-resistance approximation using expanded Krylov subspaces and combines resistance-based weighting with local clustering. The reported experiments show improved conductance and cut quality, with up to a 4.5-fold speedup over HyperSF in the cited benchmark setting. [web:427][web:531]

### Multilevel hypergraph partitioning

KaHyPar is a prominent practical framework using repeated coarsening, initial partitioning, uncoarsening, and local refinement. Its extreme \(n\)-level approach contracts very few vertices at each level and aims to produce high-quality partitions. [web:599][web:600]

## 7.3 Applicability to the assignment

**Applicability: high for P1, P2, and P4; low to medium for P3, P5, and P6.**

These methods are particularly attractive because they already produce a hierarchy of progressively smaller hypergraphs. They can therefore provide:

- explicit super-node construction;
- native hyperedge collapse;
- multilevel structure;
- structural preservation;
- efficient aggregation.

They are less suitable as complete solutions because they generally optimise structural objectives from circuit or partitioning applications. They do not know that a cluster should represent a semantic scientific concept.

## 7.4 Assumptions

- low effective resistance indicates strong structural coupling;
- preserving conductance or spectral properties preserves useful information;
- hyperedges with low cut contribution should be contracted;
- structural similarity is a useful proxy for semantic relatedness.

## 7.5 Limitations

- **Domain mismatch:** VLSI hypergraphs are not scientific knowledge hypergraphs.
- **No textual semantics:** node labels and descriptions are ignored.
- **Potential semantic mixing:** structurally adjacent methods may belong to different scientific concepts.
- **No temporal persistence:** coarsening is generally static.
- **No automatic labels:** labels require a separate process.
- **Hard budget mismatch:** the coarsening ratio is not necessarily the same as a display budget of 10–15 macro-concepts.
- **Expansion issues:** some spectral calculations use clique or star expansions internally, which may complicate claims of fully native higher-order processing.

## 7.6 Recommended use

Use spectral coarsening as the structural backbone if:

- you want a naturally hierarchical output;
- P4 is a priority;
- you can add a semantic penalty or semantic-aware merge restriction;
- you can implement a simple version rather than reproduce the full VLSI partitioning framework.

A practical adaptation is:

\[
\text{merge score}(A,B)
=
\alpha \cdot \text{structural affinity}(A,B)
+
(1-\alpha)\cdot \text{semantic affinity}(A,B)
\]

subject to the level budget and hierarchy constraints.

# 8. Flow-based hypergraph clustering

## 8.1 Basic idea

Flow-based methods define a random walk over a hypergraph and identify groups in which the walk remains for a long time.

Two common approaches are:

- **Markov stability**, which searches for partitions stable over a time scale;
- **map equation**, which compresses the description of a random walk using module structure.

## 8.2 Relevant paper

### Flow-Based Community Detection in Hypergraphs

**Paper:** Eriksson, Carletti, Lambiotte, Rojas, and Rosvall.  
[Paper](https://arxiv.org/pdf/2105.04389.pdf) [web:546]

The authors adapt Markov stability and the map equation to hypergraphs and compare them under different random-walk models, hyperedge-size biases, and representations. They find that map equation is more sensitive to time-scale changes, while Markov stability is more sensitive to hyperedge-size biases. Both identify communities in which random-walk flow remains concentrated. [web:546]

HyperSF also uses flow-based local clustering as a component of spectral coarsening. [web:567]

## 8.3 Applicability to the assignment

**Applicability: medium to high for structural multi-resolution; medium for semantic abstraction.**

Flow-based methods have a natural connection to multi-resolution because the Markov stability time parameter can act as a resolution parameter:

- short time scale: small local communities;
- long time scale: larger macro-communities.

This is conceptually appealing for the requested hierarchy.

They also offer a useful interpretation:

> a super-node is a region of the hypergraph in which information flow tends to remain.

However, flow persistence is not identical to scientific semantic coherence.

## 8.4 Assumptions

- a random walk is a meaningful model of information flow;
- hyperedge traversal probabilities reflect the intended semantics;
- communities should trap flow;
- the selected time scale corresponds to a meaningful resolution.

## 8.5 Limitations

- **Random-walk ambiguity:** several valid transition rules exist for hyperedges.
- **Hyperedge-size sensitivity:** large hyperedges can dominate or distort flow.
- **Semantic blindness:** flow does not directly represent textual meaning.
- **Hierarchy consistency:** partitions at different time scales may not automatically be exactly nested.
- **Temporal distinction:** Markov time is a resolution parameter, not necessarily calendar time.
- **Hard budgets:** the number of modules may not equal the requested budget.

## 8.6 Recommended use

Use flow-based clustering as:

- a structural baseline;
- a candidate multi-resolution mechanism;
- a way to inspect whether different resolutions correspond to meaningful scientific scales.

If used for the assignment, enforce laminarity explicitly rather than assuming that partitions from different Markov times form a valid tree.

# 9. Information-theoretic hypergraph clustering

## 9.1 Basic idea

Information-theoretic methods seek community assignments that compress the hypergraph efficiently. A good partition captures regularities in how nodes and hyperedges intersect.

This is related to the map equation but can also use hypergraph-specific microcanonical descriptions.

## 9.2 Relevant paper

### Community Detection in Hypergraphs via Mutual Information Maximization

**Paper:** *Community Detection in Hypergraphs via Mutual Information Maximization*, 2024.  
[Paper](https://www.nature.com/articles/s41598-024-55934-5) [web:605][web:7]

The method formulates hypergraph community detection as an information-theoretic compression problem involving community labels and community–edge intersections. It incorporates degree-correction ideas and reports competitive cluster recovery on hypergraph datasets. [web:7][web:605]

## 9.3 Applicability to the assignment

**Applicability: medium.**

The method is attractive when you want a principled structural objective without committing to a particular geometric embedding.

It can help answer:

- How much information about the hypergraph is retained by a coarse partition?
- Does a hierarchy provide a compact representation?
- Which clustering best compresses the hyperedge incidence structure?

It is less directly suitable for semantic scientific abstraction because compression does not necessarily imply interpretability.

## 9.4 Assumptions

- the best abstraction is one that compresses the observed structure;
- community assignments explain regularities in hyperedge incidence;
- the selected information criterion reflects the downstream goal.

## 9.5 Limitations

- compression quality is not semantic quality;
- no direct text-feature integration;
- no inherent temporal mechanism;
- labels and glosses remain external;
- hierarchy and hard budgets require additional constraints.

## 9.6 Recommended use

Use as an alternative structural objective or as a diagnostic:

```text
Does the proposed hierarchy compress the hyperedge structure better than a random or projected baseline?
```

Do not use information gain alone as evidence that clusters represent scientific concepts.

# 10. Hypergraph neural-network clustering

## 10.1 Basic idea

Hypergraph neural networks propagate information through hyperedges rather than only pairwise neighbours.

A typical model:

1. starts with node features;
2. aggregates information through hyperedges;
3. learns node embeddings;
4. clusters the embeddings;
5. optionally uses contrastive, reconstruction, or self-training losses.

This family is useful for combining semantic node features with structural hypergraph information.

## 10.2 Relevant papers

### Hypergraph convolutional neural network-based clustering technique

**Paper:** Tran, Trinh, and Tran, 2022.  
[Paper](https://arxiv.org/abs/2209.01391) [web:534]

The method uses a hypergraph autoencoder to jointly transform a feature matrix and hypergraph incidence matrix into a lower-dimensional representation, followed by \(k\)-means clustering. Experiments on Cora and Citeseer report better performance than classical clustering methods. [web:534]

### Co-clustering Interactions via Attentive Hypergraph Neural Network

**Paper:** *Co-clustering Interactions via Attentive Hypergraph Neural Network*, 2022.  
[Paper](https://dl.acm.org/doi/10.1145/3477495.3531868) [web:544]

CIAH models interactions as hyperedges and uses attention to identify important attributes. It jointly clusters interactions and attribute-selection distributions, and reports improvements over comparison methods in interaction-clustering tasks. [web:544]

### Hypergraph Network Embedding for Community Detection

**Paper:** *Hypergraph network embedding for community detection*, 2024.  
[Paper](https://link.springer.com/article/10.1007/s11227-024-06003-1) [web:608]

The framework combines hypergraph convolution, dual contrastive learning, and self-training clustering for unsupervised community detection. [web:608]

### Open-domain event schema induction via weighted attentive hypergraph neural network

This work constructs event hypergraphs and uses an attentive hypergraph neural network to model high-order participant relationships before clustering event representations into schemas. Experiments on three datasets report improved event-schema induction quality. [web:541]

## 10.3 Applicability to the assignment

**Applicability: medium.**

Neural methods can integrate:

- text embeddings;
- node type;
- graph or hypergraph structure;
- relation-type information;
- contrastive semantic objectives.

They are therefore attractive for P3.

However, they are a questionable first choice for a short research assignment because:

- training introduces additional randomness;
- model selection can dominate the experiment;
- results may be difficult to interpret;
- hierarchy construction is not automatic;
- temporal stability requires extra architecture or regularisation;
- reproducibility depends on random seeds and library versions;
- small scientific corpora may not provide enough data for reliable training.

## 10.4 Assumptions

- node features contain enough information for representation learning;
- message passing through hyperedges is meaningful;
- the training objective aligns with clustering quality;
- the dataset is sufficiently large or a pretrained encoder provides useful features;
- learned embeddings are stable across snapshots.

## 10.5 Limitations

- **Over-smoothing:** repeated aggregation can make node representations too similar.
- **Over-squashing:** information from many nodes may be compressed into limited representations.
- **Training sensitivity:** results depend on architecture, loss, and seed.
- **Evaluation leakage:** if the same features drive clustering and coherence evaluation, scores become circular.
- **No guaranteed hierarchy:** clustering the final embeddings yields one partition.
- **Limited interpretability:** attention weights are not automatically explanations.
- **Temporal instability:** retraining independently can rotate or reshape the embedding space.

## 10.6 Recommended use

Use a hypergraph neural network only if:

- semantic features are central;
- you have a reliable pretrained encoder;
- you can keep the model small;
- you compare it against simpler baselines;
- you can explain its training and verify stability.

For the assignment, a frozen text embedding plus a hypergraph structural method is probably more defensible than training a new hypergraph neural network.

# 11. Attributed hypergraph methods

## 11.1 Basic idea

Attributed hypergraph clustering explicitly combines:

- hypergraph structure;
- node attributes.

Attributes may be:

- node type;
- surface form;
- text embeddings;
- publication year;
- domain labels;
- provenance categories.

This is the most direct formal match to the structure–semantic trade-off in the assignment.

## 11.2 Main paper

The strongest directly relevant paper is *Structure and inference in hypergraphs with node attributes*. It models higher-order interactions and node covariates jointly and learns how informative the attributes are for community detection. [web:24][web:25][web:581]

## 11.3 Applicability

**Applicability: very high for P3; medium for P1, P2, P5, and P6.**

This family offers a principled response to the assignment’s central question:

> What should happen when semantic similarity and structural connectivity disagree?

Rather than choosing an arbitrary fixed weight, the model can infer the contribution of attributes from the data.

Possible adaptation:

- use text embeddings as continuous attributes;
- use node types as categorical attributes;
- use temporal metadata as covariates;
- fit one partition per snapshot;
- match or regularise partitions over time;
- convert the resulting partitions into a hierarchy.

## 11.4 Assumptions

- node attributes are measured consistently;
- semantic attributes are sufficiently informative;
- the relation between attributes and community membership can be modelled;
- communities explain both hyperedge structure and attribute distributions.

## 11.5 Limitations

- the published formulation permits overlapping communities, whereas the assignment excludes overlap;
- a single model fit does not generate a hierarchy;
- temporal coupling must be added;
- model complexity may be excessive for a 5–7-day implementation;
- text embeddings may contain noise or domain-specific bias.

## 11.6 Recommended use

Use the paper as the primary theoretical reference for the combined method, even if the implementation is a simpler constrained approximation.

A practical approximation could define:

\[
\mathcal{L}(P)
=
\mathcal{L}_{\text{hypergraph}}(P)
+
\lambda \mathcal{L}_{\text{semantic}}(P)
+
\gamma \mathcal{L}_{\text{temporal}}(P)
\]

and clearly state that:

- \(\lambda\) is selected by validation or sensitivity analysis;
- \(\gamma\) controls temporal continuity;
- the hard hierarchy and budget constraints are enforced outside the objective.

# 12. Pairwise projection methods

## 12.1 Basic idea

The hypergraph is converted into an ordinary graph, after which standard graph clustering is applied.

Common projections include:

### Clique expansion

Every hyperedge becomes a clique.

For:

```text
{A, B, C}
```

create:

```text
(A,B), (A,C), (B,C)
```

### Star expansion

Introduce an auxiliary node representing each hyperedge:

```text
A -- e1
B -- e1
C -- e1
```

This preserves the identity of the hyperedge more explicitly than clique expansion but changes the optimisation problem.

### Incidence graph

Represent the hypergraph as a bipartite graph:

- one partition for original nodes;
- one partition for hyperedges.

## 12.2 Relevant papers

The spectral hypergraph literature discusses clique, star, and related reductions extensively. The comparison between reductions and native hypergraph operators is covered in surveys and hypergraph random-walk work. [web:533][web:570]

h-Louvain also uses a two-section graph during its initial stage while ultimately targeting a hypergraph modularity objective. [web:273]

## 12.3 Applicability

**Applicability: low as the primary method; high as a baseline.**

Projection methods are:

- easy to implement;
- compatible with mature graph libraries;
- useful for debugging;
- useful for comparison.

They violate the spirit of P4 if used as the only method, because the projection can lose higher-order information. [file:1]

## 12.4 Assumptions

- pairwise relationships are a sufficient approximation;
- hyperedge size effects can be corrected with weights;
- projected connectivity remains meaningful for the application.

## 12.5 Limitations

- loses explicit hyperedge arity;
- may overcount large hyperedges;
- can create artificial pairwise relations;
- can distort community boundaries;
- makes it difficult to claim native hypergraph fidelity.

## 12.6 Recommended use

Implement one projection baseline and report:

- how many hyperedges become pairwise edges;
- graph size inflation;
- clustering differences;
- coarse-edge arity loss;
- coherence and retrieval differences;
- changes in temporal stability.

# 13. Hypergraph-aware hierarchical agglomerative clustering

## 13.1 Basic idea

Hierarchical agglomerative clustering starts with singleton nodes and repeatedly merges clusters.

For the assignment, define a merge score using:

- semantic similarity between cluster centroids;
- shared hyperedge evidence;
- hyperedge cut reduction;
- temporal similarity to previous clusters;
- type compatibility.

One possible score is:

\[
s(A,B)
=
\alpha s_{\text{semantic}}(A,B)
+
\beta s_{\text{hypergraph}}(A,B)
+
\gamma s_{\text{temporal}}(A,B)
-
\delta s_{\text{incompatibility}}(A,B)
\]

At each step, merge the best compatible pair, subject to:

- the target level budget;
- type or semantic constraints;
- temporal restrictions;
- optional maximum cluster diameter.

## 13.2 Relevant papers

### Online Level-wise Hierarchical Clustering

This KDD 2023 work studies online hierarchical clustering, which is relevant to maintaining hierarchical representations as new data arrive. [web:478]

### DynHAC: Fully Dynamic Approximate Hierarchical Agglomerative Clustering

**Paper:** DynHAC, 2025.  
[Paper](https://epubs.siam.org/doi/10.1137/1.9781611978520.24) [web:476][web:479]

DynHAC maintains an approximate average-linkage hierarchy under insertions and deletions, updating affected portions rather than rebuilding everything. [web:499]

### Multi-stage hierarchical clustering based on hypergraph partition and Chameleon

This work combines hypergraph partitioning with hierarchical clustering and Chameleon-style similarity criteria for multi-stage clustering. [web:604]

## 13.3 Applicability

**Applicability: very high as an implementation strategy.**

This approach is probably the safest for the assignment because it naturally provides:

- a laminar hierarchy;
- explicit control over cluster counts;
- straightforward integration of semantic and structural scores;
- understandable merge decisions;
- simple temporal warm starts;
- easy implementation within a few days.

The method can be fully hypergraph-aware if the merge score directly uses hyperedges and if coarse hyperedges are actually rebuilt after every merge.

## 13.4 Assumptions

- pairwise merge scores can adequately represent cluster compatibility;
- greedy local decisions produce a useful hierarchy;
- cluster centroids or summaries represent their members;
- semantic and structural similarities can be normalised to comparable scales.

## 13.5 Limitations

- greedy early merges cannot easily be undone;
- sensitive to the initial similarity definition;
- may create chains or unbalanced clusters;
- can be computationally expensive if every candidate merge is rescored;
- dynamic updates may propagate widely;
- no theoretical guarantee of optimal semantic clustering.

## 13.6 Recommended use

This is the strongest practical choice for your assessment if implemented carefully.

Recommended design:

1. initialise each valid node as a singleton;
2. calculate a hypergraph-aware merge score;
3. merge only compatible clusters;
4. record the merge tree;
5. select level cuts satisfying the budget;
6. collapse hyperedges after each selected cut;
7. match clusters over time;
8. evaluate independently.

This gives a clear explanation of what the method does and which properties are guaranteed by construction.

# 14. Hypergraph partitioning methods

## 14.1 Basic idea

Hypergraph partitioning divides nodes into \(k\) blocks while minimising a cut objective, often subject to balance constraints.

Common objectives include:

- cut-net metric;
- connectivity metric;
- \((\lambda - 1)\)-metric;
- hyperedge cut count;
- conductance;
- balanced partition size.

Partitioning is closely related to super-node creation because a partition directly defines the members of each super-node.

## 14.2 Relevant papers and systems

### High-Quality Hypergraph Partitioning

KaHyPar uses a multilevel coarsening–partitioning–uncoarsening pipeline with highly localised refinement and flow-based techniques. It reports strong quality and speed relative to established partitioners. [web:600]

### Scalable High-Quality Hypergraph Partitioning

Mt-KaHyPar parallelises components of high-quality hypergraph partitioning and uses multilevel schemes with logarithmic levels. It reports strong performance across more than 800 graph and hypergraph instances. [web:601]

### SpecPart and K-SpecPart

These methods use supervised spectral embeddings and partitioning refinements to address limitations of local coarsening and local minima. SpecPart reports substantial cut-size improvements on some benchmarks. [web:593][web:595]

## 14.3 Applicability

**Applicability: high for hard budgets and hyperedge fidelity; low to medium for semantic abstraction.**

Partitioners are useful when you must guarantee:

- a fixed or bounded number of groups;
- balanced cluster sizes;
- low hyperedge cuts;
- native hyperedge processing;
- multilevel coarsening.

They are less appropriate if the primary goal is semantic meaning rather than structural separation.

## 14.4 Assumptions

- minimising hyperedge cuts produces useful groups;
- balance constraints reflect the intended display or computational budget;
- structurally cohesive nodes should form the same super-node;
- cut quality is a meaningful proxy for abstraction quality.

## 14.5 Limitations

- semantic similarity is absent;
- balanced blocks may be semantically unnatural;
- hard balance can split meaningful concepts;
- many partitioners optimise one target \(k\), not an entire hierarchy;
- temporal identity and labels are not provided.

## 14.6 Recommended use

Use a partitioner as:

- a structural baseline;
- a constrained coarse-level generator;
- a source of initial clusters for semantic refinement;
- a candidate implementation if your data is large enough to require specialised tooling.

# 15. How methods map to the assignment requirements

| Requirement | Most suitable method families | Main issue |
|---|---|---|
| P1 laminarity | Agglomerative clustering, multilevel coarsening | Independent partitions do not guarantee nesting |
| P2 hard size budget | Partitioning, constrained agglomeration | Modularity and spectral methods need external enforcement |
| P3 semantic coherence | Attributed models, hypergraph neural networks, joint objectives | Must avoid evaluation circularity |
| P4 hyperedge fidelity | Hypergraph modularity, spectral coarsening, partitioning | Verify that coarse hyperedges are actually used |
| P5 temporal stability | Dynamic HAC, warm-started agglomeration, temporal regularisation | Most static methods need an added mechanism |
| P6 faithful labels | Evidence-grounded labelling plus NLI/human evaluation | No clustering method solves this automatically |

# 16. Recommended method variants for your experiment

You should compare several deliberately different variants rather than tuning a single model.

## Variant A: semantic-only

1. Represent each node using text or description embeddings.
2. Apply hierarchical agglomerative clustering.
3. Ignore hyperedges during clustering.
4. Use it as a semantic baseline.

Purpose:

- measures how much meaning can be captured without graph structure;
- exposes cases where semantic similarity conflicts with scientific relations.

## Variant B: structure-only native hypergraph

Use one of:

- h-Louvain;
- hypergraph modularity;
- spectral hypergraph clustering;
- HyperEF-style structural coarsening.

Purpose:

- measures the value of native higher-order structure;
- provides a baseline against pairwise projection.

## Variant C: pairwise projection

1. Convert hyperedges to a clique or incidence graph.
2. Apply standard hierarchical clustering.
3. Reconstruct coarse relations.

Purpose:

- quantifies the cost of projection;
- establishes a familiar baseline.

## Variant D: joint semantic–structural method

Use constrained agglomeration with:

\[
s(A,B)
=
\alpha s_{\text{semantic}}
+
(1-\alpha)s_{\text{hypergraph}}
\]

Optionally add temporal continuity:

\[
s'(A,B)
=
s(A,B)
+
\gamma s_{\text{temporal}}
\]

Purpose:

- is the likely method to ship;
- directly addresses P3;
- is easier to explain and implement than a full neural or probabilistic model.

## Variant E: joint method with temporal coupling

Add:

- warm starts;
- previous-cluster membership overlap;
- a penalty for unnecessary reassignment;
- identity matching and event tracking.

Purpose:

- evaluates whether temporal coupling reduces churn;
- tests the core temporal requirement rather than treating snapshots independently.

# 17. Recommended final method

The best balance between scientific defensibility and implementation risk is:

## Hypergraph-aware constrained agglomeration with semantic and temporal terms

### Step 1: Node representation

For each node, create:

- semantic embedding;
- node-type indicator;
- publication-time metadata;
- optional provenance features.

### Step 2: Hypergraph structural similarity

For two nodes \(u\) and \(v\), compute a similarity based on:

- shared hyperedge count;
- weighted shared hyperedges;
- relation-type agreement;
- hyperedge arity;
- hypergraph spectral proximity, if available.

For example:

\[
s_{\text{hypergraph}}(u,v)
=
\sum_{e \ni u,v}
w_e
\]

where \(w_e\) can down-weight very large or noisy hyperedges.

### Step 3: Semantic similarity

Use cosine similarity between node embeddings:

\[
s_{\text{semantic}}(u,v)
=
\frac{x_u^\top x_v}{\|x_u\|\|x_v\|}
\]

Normalise structural and semantic scores before combining them.

### Step 4: Merge objective

Define:

\[
s(A,B)
=
\alpha s_{\text{semantic}}(A,B)
+
\beta s_{\text{hypergraph}}(A,B)
+
\gamma s_{\text{temporal}}(A,B)
\]

where cluster-level similarities can be calculated using average linkage, centroid similarity, or aggregate hyperedge evidence.

### Step 5: Hierarchy and budgets

Build the merge tree from fine to coarse. Select level cuts that satisfy:

\[
|P_k| \leq N_k
\]

If a cut exceeds the budget, merge the pair causing the smallest reduction in the combined objective.

### Step 6: Hyperedge collapse

After each selected cut, map every original endpoint to its super-node and reconstruct each coarse hyperedge:

```text
original edge:
{A, B, C, D}

assignments:
A -> X
B -> X
C -> Y
D -> Z

coarse edge:
{X, Y, Z}
```

Retain:

- original edge IDs;
- relation types;
- endpoint counts;
- internal-edge flag;
- temporal metadata.

### Step 7: Temporal matching

Match current clusters to previous clusters using weighted Jaccard similarity:

\[
J(A,B)
=
\frac{|A \cap B|}{|A \cup B|}
\]

Use thresholds to detect:

- persistence;
- growth;
- birth;
- death;
- merge;
- split.

### Step 8: Label generation

Generate labels from:

- member surface forms;
- node types;
- supporting hyperedges;
- source-paper evidence;
- cutoff-restricted metadata.

Then evaluate label entailment or human-rated faithfulness.

# 18. Evaluation design by method family

## Structural coherence

Use an independent structural signal, such as:

- held-out hyperedges;
- citation links not used during clustering;
- edge prediction likelihood;
- conductance or hyperedge cut quality.

Do not evaluate with exactly the same hypergraph statistic used to optimise the clustering without also providing an independent measure.

## Semantic coherence

Use:

- a different embedding model;
- held-out textual evidence;
- blinded expert or LLM ratings;
- cluster-level topic consistency.

Compare against a null model preserving node degrees and hyperedge arities.

## Stability

For each method:

- remove 10% of hyperedges;
- run five random seeds;
- compare partitions using ARI or a hierarchy-aware analogue;
- report confidence intervals;
- compare real temporal changes separately from perturbation instability.

## Label faithfulness

Measure:

- over-claim rate;
- unsupported date claims;
- unsupported performance claims;
- entailment of glosses by member evidence;
- rate of vague but safe labels.

## Extrinsic utility

Use the hierarchy in a retrieval task:

- hierarchical drill-down;
- flat search;
- compare hit rate;
- compare number of inspected nodes;
- compare steps-to-target.

# 19. Main assumptions to state explicitly

Regardless of the chosen method, document the following assumptions:

- a node represents one coherent entity;
- duplicate surface forms are either merged or intentionally kept separate;
- hyperedge co-occurrence has a defined interpretation;
- node embeddings capture useful semantic similarity;
- relation types are comparable or appropriately weighted;
- older snapshots do not contain future information;
- a hard non-overlapping partition is acceptable;
- a super-node can be represented by one label and one gloss;
- Jaccard overlap is an adequate first approximation for temporal identity;
- a null model preserves the relevant structural properties.

# 20. Main limitations to acknowledge

The most important limitations are:

1. **Semantic ambiguity:** a method can be structurally related to a dataset without belonging to the same semantic concept.
2. **Extraction noise:** the quality of the abstraction cannot exceed the quality of the input knowledge extraction.
3. **Hyperedge ambiguity:** co-occurrence hyperedges do not necessarily represent verified scientific relations.
4. **Hierarchy dependence:** greedy merges can make early mistakes difficult to correct.
5. **Temporal uncertainty:** changes in the corpus may reflect extraction changes rather than genuine scientific evolution.
6. **Label uncertainty:** generated glosses can sound plausible while exceeding the evidence.
7. **Evaluation leakage:** using the same embeddings or relations for clustering and evaluation inflates results.
8. **Budget distortion:** forcing roughly 10–15 macro-concepts may merge scientifically distinct themes.
9. **Projection bias:** graph projections may create relationships absent from the original hypergraph.
10. **Model mismatch:** methods designed for circuits, social networks, or recommendation systems may not transfer directly to scientific knowledge graphs.

# 21. Final recommendation

For the assignment, use **hypergraph-aware constrained hierarchical agglomeration with semantic similarity and temporal matching**, and position it against:

- hypergraph modularity / h-Louvain;
- spectral hypergraph coarsening such as HyperEF or HyperSF;
- semantic-only clustering;
- pairwise projection clustering.

This choice is preferable to a full hypergraph neural network because it is:

- implementable within the available time;
- naturally compatible with laminar hierarchies;
- easy to constrain to hard budgets;
- transparent enough to explain;
- capable of using native hyperedges;
- straightforward to extend with temporal identity matching;
- suitable for ablation studies.

Use attributed hypergraph stochastic block models as the main theoretical reference for the structure–semantics integration, but treat a simpler joint objective as the practical implementation unless you have enough time to reproduce the probabilistic model faithfully. [web:24][web:581]

The most defensible claim is not that the selected method is universally optimal. It is that it provides a transparent, hypergraph-aware, semantically informed, temporally trackable hierarchy whose strengths and weaknesses can be evaluated against clearly defined alternatives.
