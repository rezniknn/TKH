# Concepts primer: Perplexity Deep Research output (raw, unverified, TRUNCATED)

Tool: Perplexity Deep Research with the Academic connector enabled. The task brief was uploaded as an attachment.

Prompt: "Explain in detail all the concepts referenced in the research assignment to someone with good Data Science fundamentals but rusty in the knowledge graph domain to help prepare getting started on the implementation and analysis of the temporal hyper graph following the assignment"

The output is kept close to verbatim. Citations that pointed to the uploaded brief (temporary pre-signed S3 links) have been removed.

**Truncated:** the copy pasted into Claude Code was cut at the 50,000-character message limit, partway through §9 "Over-claim rate". Anything after that point (the rest of §9 and any later sections) is missing. Paste it again if it's needed.

**Things to keep in mind when reading** (notes added in Claude Code, not part of the output):
- Perplexity saw only the brief, not `data/tkh_collection10.json`. Its example field and relation names (`member_ids`, `method_dataset_metric`, `comparison_table`, the provenance fields `source_section` / `extraction_method` / `confidence`) are made up for illustration. The real export uses `members`, has relation types `addresses`, `authored_by`, `cites`, `claims`, `evaluated_on`, `extends`, `presents`, `proposes_future_work`, `solves`, `uses_component` and `uses_technique`, and has provenance fields `source`, `collection_id`, `articles`, `entity_id`, `article_id` and `article_year`.
- §6 "internal fraction" = 1 − (distinct coarse endpoints / original arity). The name doesn't fit what the formula measures. An arity-4 edge collapsed fully into one super-node scores 0.75, not 1. An edge spread across 3 super-nodes, with only one pair sharing a super-node, scores 0.25. It is really a collapse ratio. Define our own measure for T4.
- §8 temporal penalty 1[c_t(v) ≠ c_{t−1}(v)]: this only works if cluster ids are first matched across snapshots, and it isn't defined for nodes that are new at t.

---

# Concepts and Implementation Guide

The assignment asks you to build a **multi-resolution semantic abstraction of an evolving temporal knowledge hypergraph**. In practical terms, you receive scientific entities and multi-entity relations at several time points, group related entities into progressively coarser clusters, preserve the meaning of the original hypergraph, maintain stable cluster identities over time, and evaluate whether the resulting hierarchy is genuinely useful and trustworthy.

A useful mental model is:

> **A temporal knowledge hypergraph is a versioned scientific knowledge map; your method builds a stable, navigable hierarchy over that map.**

The assignment is not primarily asking for a sophisticated production system. It is testing whether you can define the problem precisely, implement a defensible method, and evaluate it without accidentally measuring your own assumptions.

## 1. Knowledge Graph Basics

### Entities and relations

A conventional knowledge graph represents knowledge using:

- **Nodes**, also called entities or vertices.
- **Edges**, also called relations or links.
- **Attributes**, such as type, name, date, source, or confidence.

```text
Node A: BERT
Node B: GLUE
Node C: accuracy

Edge: BERT --evaluated_on--> GLUE
Edge: BERT --measured_by--> accuracy
```

A knowledge graph is usually more structured than a normal document collection because the system explicitly stores entities and relationships rather than only raw text.

In this assignment, nodes can represent scientific methods; datasets; concepts; entities; papers or other knowledge objects, depending on the supplied export. Each node has metadata such as `id`, `type`, `surface_form`, `year`, `provenance`.

The **surface form** is the text used to name or mention the node. The **provenance** records where the node came from—for example, a paper, table, abstract, extraction system, or source document.

### Knowledge graphs versus document collections

A document collection might store:

```text
Paper 1: "BERT achieves strong performance on GLUE."
Paper 2: "RoBERTa improves BERT on several benchmarks."
```

A knowledge graph attempts to extract something closer to:

```text
BERT --evaluated_on--> GLUE
RoBERTa --improves_on--> BERT
RoBERTa --evaluated_on--> GLUE
```

This enables graph-based operations such as finding related methods; following method–dataset–metric connections; identifying communities of scientific concepts; navigating from broad topics to individual papers; retrieving supporting evidence for a claim.

The assignment assumes that this extraction has already happened, at least in Option A. Your task is mainly to reason about and abstract the resulting structure, not to build a complete information-extraction pipeline.

### Provenance

**Provenance** means information about the origin of a node or relation. A provenance record might say:

```json
{
  "source_paper": "paper_123",
  "source_section": "results",
  "extraction_method": "rule_based",
  "confidence": 0.87
}
```

Provenance matters because a generated cluster label should be supported by actual source evidence. If a super-node contains methods extracted from papers published only up to 2022, its label should not imply knowledge of developments after 2022.

Provenance also helps diagnose errors: Was a node extracted from an abstract or a table? Did multiple papers support it? Was it generated by an LLM? Was the relation explicitly verified or merely inferred from co-occurrence?

## 2. Hypergraphs

### Ordinary graphs

In an ordinary graph, one edge usually connects exactly two nodes: $e = (u, v)$. This is useful when the relation is inherently pairwise.

### Hypergraphs

A **hypergraph** generalises an ordinary graph. A hyperedge can connect any number of nodes: $e = \{v_1, v_2, \ldots, v_n\}$. For example `{BERT, GLUE, accuracy}` can represent a single scientific context involving a method, a dataset and a metric.

The assignment explicitly uses hyperedges because scientific relations are often naturally higher-order. A method-comparison table may jointly connect multiple methods, a dataset, a metric, and perhaps a task. Replacing that relation with separate pairwise edges loses information about which entities participated in the same event or claim.

### Hyperedge arity

The **arity** of a hyperedge is the number of distinct nodes it contains (`{A, B}` = 2, `{A, B, C}` = 3, …). The assignment requires reporting the hyperedge arity distribution for each snapshot. This tells you whether the data mainly contains pairwise relations or genuine higher-order relations.

```python
arity = len(set(edge["member_ids"]))
```

You should remove duplicate node IDs before calculating arity. Otherwise, malformed data could make an edge appear to have a higher arity than it actually does.

### Hyperedge types

The `relation_type` field describes what kind of multi-way relation the hyperedge represents. Examples: `method_dataset_metric`, `paper_entities`, `comparison_table`, `co_occurrence`.

Different relation types may have different semantics. A hyperedge extracted from a comparison table is not necessarily equivalent to one created merely because several words co-occurred in an abstract. Inspect: counts by relation type; arity distribution by relation type; temporal distribution by relation type; whether some relation types are noisy or ambiguous.

### Why pairwise projection is lossy

A common simplification is to convert a hyperedge into a clique: `{A, B, C}` → `A–B, A–C, B–C`. This preserves pairwise connectivity but loses the fact that all three nodes participated in one common hyperedge. Distortions:

1. **Multiplicity inflation:** one hyperedge becomes several pairwise edges.
2. **Semantic ambiguity:** every pair appears related, although the original relation may only be meaningful jointly.
3. **Arity loss:** the algorithm can no longer distinguish a 3-way relation from three independent pairwise relations.
4. **Weight distortion:** large hyperedges create many pairwise links.
5. **Community distortion:** dense large hyperedges can artificially merge otherwise distinct clusters.

The assignment does not prohibit a pairwise baseline. It requires you to quantify what the projection loses compared with your hypergraph-native method.

## 3. Temporal Knowledge Hypergraphs

### Static versus temporal hypergraphs

A static hypergraph is $H = (V, E)$. A temporal hypergraph is a sequence $H(t_1), H(t_2), \ldots, H(t_T)$ where nodes and hyperedges may appear, disappear, or change over time.

In the assignment, the graph grows as new scientific papers enter the corpus. A snapshot might contain all knowledge available up to a cutoff (≤2020, ≤2022, ≤2024). These are **cumulative snapshots**. The 2024 graph generally contains the earlier graph plus new information, although extraction and cleaning may also create changes or deletions.

### Snapshot cutoff

For a 2022 snapshot: nodes supported only by 2024 papers must not appear; hyperedges created only after 2022 must not appear; labels must not refer to future developments. A 2022 super-node cannot be labelled "Emerging transformer architectures introduced in 2024" because that violates temporal honesty.

### Snapshot-level analysis

For each snapshot, compute at least: number of nodes; number of hyperedges; number of nodes by type; hyperedge arity statistics; relation-type counts; temporal range; newly added nodes; newly added hyperedges; removed or modified entities; percentage of persistent nodes and edges.

$$\text{node growth}_{t \rightarrow t+1} = \frac{|V_{t+1}| - |V_t|}{|V_t|} \qquad \text{edge persistence} = \frac{|E_t \cap E_{t+1}|}{|E_t|}$$

The precise definition of "same edge" must be stated. It might mean identical edge IDs, identical endpoint sets, or matching endpoint sets plus relation type.

### Data quality problems

Actively inspect for: duplicate node IDs; duplicate surface forms; inconsistent capitalisation; aliases treated as separate entities; missing node types; hyperedges referring to missing nodes; repeated members inside one hyperedge; empty or singleton hyperedges; relations with unreliable dates; future-dated information appearing in earlier snapshots; extraction artefacts; hyperedges representing co-occurrence rather than verified relations.

The assignment specifically asks you to separate **verified facts** from **assumptions**:

```text
Verified: the export contains 1,240 hyperedges in the 2022 snapshot.
Assumption: two nodes with the same normalised surface form refer to the same concept.
```

## 4. Multi-Resolution Semantic Abstraction

### What is an abstraction?

An abstraction replaces many detailed objects with fewer higher-level objects while preserving the information needed for the intended task (e.g. BERT, RoBERTa, ALBERT, ELECTRA, T5 → "Transformer language models"). The coarse node is called a **super-node**. It does not replace the underlying nodes; it summarises them.

### Resolution

Fine: individual methods and datasets. Medium: families of methods or related research topics. Coarse: broad scientific areas.

```text
Level 0: approximately 10–15 macro-concepts
Level 1: more detailed scientific themes
Level 2: finer groups
...
Level K: individual nodes
```

$P_0$ is the coarsest partition; $P_K$ is the finest partition; the finest partition should contain one original node per cluster.

### Partition

A **partition** divides the node set into non-overlapping clusters, e.g. `{A, B}, {C, D}, {E}`. Every node belongs to exactly one cluster. The assignment excludes overlapping clusters.

### Super-node

```json
{
  "id": "sn_001",
  "level": 1,
  "member_ids": ["method_bert", "method_roberta"],
  "parent_id": "sn_000",
  "label": "Transformer encoders",
  "gloss": "Encoder-based transformer methods used for language representation."
}
```

The super-node should preserve: its members; its position in the hierarchy; its temporal identity; its label; its evidence; its aggregate hyperedges.

### Laminar hierarchy

A hierarchy is **laminar** when clusters at adjacent levels are nested rather than arbitrarily overlapping. Level 0 `{A,B,C,D}`; Level 1 `{A,B},{C,D}`; Level 2 `{A},{B},{C},{D}` is laminar. Level 1 `{A,B},{B,C}` is invalid because B belongs to two clusters at the same level.

A practical representation is a parent pointer: level 2 node → level 1 parent → level 0 parent. The hierarchy can be represented as a forest if the coarsest level contains several disconnected roots, although the assignment likely expects a set of top-level super-nodes constrained by the budget.

### Refinement direction

"$P_k$ refines $P_{k-1}$" means every cluster at the finer level is contained in exactly one cluster at the coarser level: for every $C \in P_k$ there exists exactly one $D \in P_{k-1}$ with $C \subseteq D$. Level 0 is coarser and level $K$ is finer, so the parent of a level-$(k+1)$ node is at level $k$.

## 5. The Six Required Properties

### P1: Laminar refinement

Guarantee it **by construction** by generating the hierarchy from a dendrogram, recursive splitting process, or explicit parent-child assignment. Do not produce independent clusterings at each level and attempt to align them afterward unless you have a robust repair step.

Validation should check: (1) every node occurs exactly once per level; (2) every level-$(k+1)$ super-node has one parent at level $k$; (3) every child's members are a subset of its parent's members; (4) the finest level covers all valid nodes; (5) no clusters overlap at one level.

### P2: Size budget

$|P_k| \leq N_k$. At level 0, $N_0$ may be around 10–15. This is a **hard constraint**, not merely a penalty in an objective function.

If your clustering creates too many clusters, use a deterministic strategy: continue merging until the budget is met; choose merges that incur the smallest objective increase; use a constrained agglomerative algorithm; split only when the resulting number of clusters remains within the budget. A method that produces excellent semantic clusters but violates the display budget does not satisfy P2.

### P3: Semantic coherence

Semantic coherence means members of a super-node represent a recognisable scientific idea—not merely that they have many graph connections. Two methods may be heavily cited together because one compares against the other, but that does not necessarily mean they belong to the same semantic category.

Semantic signals: text embeddings of descriptions; title or abstract embeddings; method and dataset type; extracted definitions; shared scientific terminology; external taxonomy membership; LLM or human judgements.

Structural signals: hyperedge co-membership; shared relation types; hypergraph conductance; hypergraph modularity; effective resistance; citation or reference structure.

### Structure–semantics trade-off

$$J(P) = \lambda J_{\text{structure}}(P) + (1-\lambda) J_{\text{semantic}}(P)$$

$\lambda = 1$ structure only; $\lambda = 0$ semantics only. The exact definition of each term is your research choice (e.g. structural quality = hyperedge purity or cut cost; semantic quality = similarity between members using an embedding model not used for evaluation). Explain: what each signal captures; where each signal is unreliable; how the weight is selected; whether the weight is constant across levels; whether structural constraints override semantic preferences.

### P4: Hyperedge fidelity

The hyperedge structure must affect the actual clustering or coarsening algorithm. It is not sufficient to (1) convert all hyperedges to pairwise edges, (2) cluster the graph, (3) mention hyperedges in the report. If you use a graph projection as a baseline, implement a second native or hyperedge-aware method and compare the results.

### P5: Temporal stability

A stable hierarchy should preserve the identity of unchanged scientific regions; avoid unnecessary global rearrangements; update mainly where new or changed evidence appears; record meaningful events such as births, merges, and splits. Temporal stability does not mean clusters can never change; the objective is to distinguish meaningful changes from algorithmic noise.

### P6: Faithful labels

Each super-node requires a short label and a one-sentence gloss. A faithful gloss must be supported by the member nodes and available evidence. It should not claim: a method is state of the art unless the evidence supports that; causality from simple co-occurrence; a publication date beyond the snapshot cutoff; that all members share a property when only some do; a relation that exists only in a projected graph. A safer label is often narrower and more descriptive than an impressive but unsupported one.

## 6. Hyperedge Coarsening

### What coarsening means

`e = {A, B, C, D}` with `A→X, B→X, C→Y, D→Z` becomes `{X, Y, Z}`. This is **hyperedge collapse** or **hyperedge coarsening**.

### Case 1: all endpoints in one super-node

`{X}`: an internal hyperedge. Decide whether to retain it as an internal evidence/count attribute; drop it from the inter-super-node hypergraph; keep it with a flag such as `internal=True`. Dropping it from inter-cluster connectivity is reasonable, but retaining its count can help measure how much evidence exists inside the cluster.

### Case 2: endpoints in two super-nodes

`{A,B,C,D} → {X,Y}`:

```json
{
  "coarse_members": ["X", "Y"],
  "original_arity": 4,
  "endpoint_counts": {"X": 2, "Y": 2},
  "internal_fraction": 0.5
}
```

$$\text{internal fraction}(e) = 1 - \frac{\text{number of distinct coarse endpoints}}{\text{original arity}}$$

This is only one possible definition. State yours explicitly.

### Case 3: endpoints in three or more super-nodes

`A→X, B→Y, C→Z, D→Z` gives `{X, Y, Z}`. Do not automatically split it into pairwise edges; its multi-way nature is exactly what P4 asks you to preserve. Retain endpoint counts `{"X": 1, "Y": 1, "Z": 2}`.

### What is lost during collapse?

Which original members participated; the exact endpoint multiplicity unless explicitly retained; distinctions between different original hyperedges that collapse to the same coarse endpoint set; relation-specific details; within-cluster structure. Preserve summary metadata such as original edge IDs; relation types; endpoint counts; number of collapsed edges; fraction of internal endpoints; temporal support.

### Recommended implementation

```python
from collections import Counter

def collapse_hyperedge(member_ids, assignment):
    coarse_ids = [assignment[node_id] for node_id in member_ids]
    counts = Counter(coarse_ids)
    unique_coarse_ids = sorted(counts)

    return {
        "members": unique_coarse_ids,
        "endpoint_counts": dict(counts),
        "original_arity": len(set(member_ids)),
        "coarse_arity": len(unique_coarse_ids),
        "is_internal": len(unique_coarse_ids) == 1,
    }
```

This function must be used by the actual method, not merely included as unused utility code.

## 7. Clustering and Coarsening

### Community detection

A **community** is a group of nodes with stronger internal relationships than external relationships. In ordinary graphs: Louvain; Leiden; spectral clustering; hierarchical agglomerative clustering; modularity maximisation. For hypergraphs, the objective must account for group relations rather than only pairwise edges.

### Hypergraph modularity

$Q$ = observed within-community structure − expected within-community structure. For hypergraphs, "within-community structure" depends on how a multi-node hyperedge contributes when all endpoints lie in one community; most endpoints lie in one community; endpoints are distributed across several communities. Different definitions imply different notions of what it means for a hyperedge to be internally coherent.

### Spectral hypergraph methods

Construct a hypergraph operator (e.g. Laplacian) → compute a low-dimensional spectral embedding → cluster. Verify: which hypergraph representation is used; whether the method expands hyperedges into a graph; whether weights and relation types are preserved; computational scaling; whether the embedding captures semantic rather than only structural similarity.

### Agglomerative hierarchy

Starts with individual nodes and repeatedly merges clusters (Level K individual nodes → … → Level 0 macro-clusters). Naturally laminar, attractive for P1. However, ordinary agglomerative clustering may use pairwise rather than hypergraph relations; be sensitive to early greedy decisions; create semantically incoherent clusters; produce unstable dendrograms under small data changes. A practical approach: agglomeration with a joint score of semantic similarity; hyperedge cohesion; temporal continuity; cluster-size constraints.

## 8. Temporal Identity and Events

### Why cluster identity is difficult

If 2020 has super-node A "convolutional models" and an independent 2022 run creates X "convolutional architectures" with almost the same nodes, different IDs hide that they are the same evolving concept. You need **persistent super-node identities**.

### Matching clusters across snapshots

$$J(A, B) = \frac{|A \cap B|}{|A \cup B|}$$

Rules: if $J(A,B) \geq \tau$ preserve the old ID; several new matching one old → split; several old matching one new → merge; no predecessor → birth; no successor → death; node set grows but concept remains coherent → growth.

### Event types

- **Birth:** `{"event": "birth", "snapshot": 2022, "super_node_id": "sn_2022_07"}`
- **Growth:** `{"event": "growth", "from": "sn_2020_03", "to": "sn_2022_03", "added_members": ["method_x"]}`
- **Merge:** A + B → C
- **Split:** A → B + C
- **Death:** a super-node disappears or no longer has sufficient evidence.

### Warm starts

Use the previous snapshot's clustering as the initial state. Advantages: faster optimisation; encourages continuity; reuses persistent structure. Risks: old mistakes persist; new topics forced into old clusters; overly stable.

### Temporal regularisation

$$J_{\text{total}} = J_{\text{current}} + \gamma J_{\text{temporal}}, \qquad J_{\text{temporal}} = \sum_{v \in V_t} \mathbf{1}[c_t(v) \neq c_{t-1}(v)]$$

Low $\gamma$ adapts quickly but may reshuffle; high $\gamma$ remains stable but may miss real scientific change.

### Localised updates

Ideally recompute only clusters containing newly added nodes; clusters incident to changed hyperedges; nearby clusters affected by merges or splits. For a short assessment, full recomputation plus identity matching may be acceptable, provided you acknowledge that it does not enforce local computation. A stronger method uses previous assignments as initialisation and restricts changes to affected regions.

## 9. Label Generation and Faithfulness

### Label versus gloss

Label = short name for navigation ("Transformer encoders"); gloss = short explanatory sentence for interpretability.

### Safe labelling pipeline

1. collect member-node metadata;
2. collect supporting hyperedges;
3. restrict evidence to the snapshot cutoff;
4. summarise the evidence deterministically;
5. ask an LLM to propose a label and gloss;
6. validate the output against the evidence;
7. reject or revise unsupported claims.

The LLM should not receive unrestricted future context. Its input should be explicit and reproducible.

```text
Snapshot cutoff: 2022

Member nodes:
- BERT, type=method, sources=[paper_1, paper_4]
- RoBERTa, type=method, sources=[paper_2, paper_5]

Supporting relation types:
- method_family
- evaluated_on

Generate:
1. a label of at most five words;
2. one sentence of at most 25 words;
3. no claims about performance, causality, or dates unless directly supported.
```

### Over-claim rate

The assignment asks you to quantify unsupported labels rather than inspect a few e

**[TRUNCATED HERE: the rest was lost to the paste limit]**
