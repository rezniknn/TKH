# Data investigation: repo/data (TKH collection 10)

Produced by a Claude Code workflow: 5 parallel investigators, each followed by an independent verifier that re-ran the numbers with its own code. The numbers below are the verifiers' corrected values where they differed (22 of 79 headline claims were corrected, none refuted). Scripts are in the session scratchpad (`scratchpad/data_investigation/*`) and are not part of the repo.

Labels: **[V]** computed and verified · **[I]** interpretation or recommendation.

## 1. Files

| File | What it is | Role in the task |
|---|---|---|
| `tkh_collection10.json` | The TKH export: `meta`, 5,798 `nodes`, 1,429 `hyperedges` | Option A input (§4) for T1–T5 |
| `collection10_articles.csv` | 52 papers: id (MVKG), year, arxiv_id, status, title | The time axis and provenance join |
| `questions.csv` | 18 domain questions (`;`-separated). Q1–Q14 type A ("which methods…"), Q15–Q18 type B (evidence questions) | Queries for the T6 extrinsic task |
| `ground_truth.json` | Per-question gold answers: expected methods, claims, evidence quotes, false-positive categories, sources | Targets and negatives for T6; an independent reference for coherence and faithfulness |

Domain [I]: ML for atomistic and materials modelling. Main themes: ML interatomic potentials (17 papers), DFT databases (7), GNN architectures (7), discovery and benchmarks (7), electronic structure / DFT Hamiltonians (5), multiscale (5), reviews (4). This grouping comes from titles only and is useful only as a weak sanity check.

## 2. Structure [V]

- **Integrity is clean.** No duplicate ids, no dangling members, no repeated members within an edge, no arity-1 edges, no isolated nodes. The counts in `meta` match the data.
- **Node types:** technique 962, component 855, task 732, claim 690, problem 634, cited_work 580, method 448, author 318, dataset 259, future_topic 178, metric 90, article 52.
- **Undocumented field:** `aliases` is present on 80 method nodes, for example meth_00199 has aliases=['xDeepH'].
- **Relation types:** claims 690, evaluated_on 301, presents 52, addresses 51, solves 51, uses_technique 51, authored_by 51, extends 50, uses_component 50, proposes_future_work 45, cites 37.
- **Arity:** 279 edges have arity 2, 751 arity 3, maximum 65; mean 6.25, median 3. claims edges are always arity 2 or 3, presents always 2, evaluated_on has median 3 (max 32). The per-paper "bundle" relations are large: addresses median 14, uses_technique 16, uses_component 17, cites 24, solves 10, extends 11.5, authored_by 7.
- **The graph is 52 article-local stars.** `members[0]` is always a hub. For authored_by, cites, claims, presents and proposes_future_work the hub is the article itself (875 of 875 edges). For addresses, solves, extends, uses_*, and evaluated_on it is the method that article presents (554 of 554). Each article has at most one edge of each bundle relation. Only claims (6–60 per paper) and evaluated_on (0–33) repeat. `attributes.n_targets` equals arity − 1.
  → [I] Most hyper-edges mean "these appear in the same paper", not n-ary scientific facts. A clique projection turns 6,661 star pairs into about 70k pairs, which is how much a pairwise projection would distort the structure (relevant to P4 and T2).
- **Cross-paper overlap is thin.** 92.9% of nodes appear in exactly one article. Only about 413 nodes connect papers: cited_work 122, method 95, task 73, author 42, technique 30, and smaller counts for other types.
- **Generic hubs dominate the shared nodes:** task_00003 'materials science' (51 of 52 articles), 'computational chemistry' (23), 'computational physics' / 'molecular dynamics' / cite MACE (13 each), SchNet and 'computational materials science' (12).
- **Connectivity.** The graph is one component up to the ≤2023 snapshot. From ≤2024 it has two: article 5405 forms a 24-node island because it has no method-rooted edges. Removing the 'materials science' hub does not split anything.

## 3. Time and snapshots [V]

- **Article years** (CSV, identical on the article nodes): 2013:3, 2015:1, 2016:1, 2017:3, 2018:2, 2019:2, 2020:4, 2021:1, 2022:5, 2023:10, 2024:6, 2025:8, 2026:6. Cumulative: ≤2020 16, ≤2022 22, ≤2024 38, ≤2026 52.
- **The year looks like the venue year, not the preprint year.** 10 of the 36 arXiv-dated papers lag their arXiv id by 1–2 years (OMat24: arXiv 2410, year 2026). With the brief's cutoffs, three papers would change snapshot if the arXiv year were used. The year 2026 is only partly covered: the export is dated 2026-08-15. `ingested_at` / `extracted_at` are pipeline dates (June–August 2026) and cannot serve as a time axis.
- **The node year fields leak, so do not slice by them:**
  - `node.year` (origin_year when known) adds 364 nodes at ≤2020, almost all isolated, such as old methods first mentioned in later papers.
  - `first_seen_year` contradicts its documented meaning for 127 nodes (73 claims, 31 datasets, 23 metrics). In all 127 it equals the earliest incident `edge.year`. For example metr_00005 has first_seen 1997 although its earliest paper is from 2021. Slicing by it adds 30 to 70 isolated nodes per cutoff, and it also drops a few nodes.
  - `edge.year` is the year of the evaluation or claim row. It differs from the paper's year on 154 edges and is later than the paper on 20. Slicing by it leaks 31 to 80 edges from later papers.
- **Provenance gaps.** For 36 claims-edge memberships, the member node's `provenance.articles` does not list the edge's article. All 36 involve meth_00169 GNoME, meth_00037 M3GNet or meth_00058 NequIP. 14 dataset/metric nodes have the same gap.
- **Recommended snapshot rule [I]:**
  - An edge is in snapshot c iff `provenance.article_year ≤ c`.
  - A node's entry year is the minimum year over `provenance.articles ∪ {article_id of its incident edges}`.
  - This gives 0 closure violations at every cutoff.
  - State the rule in the report and make validate.py check it.
- **Recommended cutoffs [I]:** {≤2020, ≤2022, ≤2024, ≤2026}.
  - It contains the brief's examples, uses all 52 papers (the brief's three cutoffs alone would leave out 29% of nodes), and gives 3 transitions for the confidence intervals.
  - Sensitivity check: {≤2020, ≤2023, ≤2026}.

| Snapshot | Articles | Nodes | Edges |
|---|---|---|---|
| ≤2020 | 16 | 1,475 | 374 |
| ≤2022 | 22 | 2,144 (union rule) | 554 |
| ≤2024 | 38 | 4,094 | 983 |
| ≤2026 | 52 | 5,798 | 1,429 |

- **Temporal attachment is weak.** Only 15–30% of new edges touch any node from the previous snapshot, and only about 2.5–9% of old nodes are mentioned again. Almost every new paper shares at least one non-hub node with the earlier snapshot.
  → [I] Stability of old nodes will look high almost for free. Report stability separately for old nodes and for where new paper stars attach. Include a "freeze old assignments, add new nodes greedily" baseline so the data's own inertia does not inflate the stability numbers.

## 4. Data-quality issues to report in T1 [V unless marked]

1. **Year semantics** (§3): first_seen_year is inconsistent for 127 nodes; edge.year is not the paper year on 154 edges; publication year is the venue year.
2. **Provenance gaps** for GNoME, M3GNet, NequIP and 14 dataset/metric nodes.
3. **Entity resolution is incomplete.** There are 0 exact duplicates within a type. After punctuation and hyphen normalisation there are 47 groups (48 redundant ids), and about 90–100 candidates with plural stripping (counts depend on the rule). Examples: Behler-Parrinello NNP ×3; 'Tensor Field Networks' / 'TensorField' / 'Tensor-Field'; 'Matbench Discovery' / 'Matbench-Discovery'. Some normalised matches are false (DimeNet vs DimeNet++).
4. **The same name appears under several types.** 277 lowercased names occur under two or more types, mostly cited_work/method (about 167 pairs). MACE exists as a method only as 'MACE-MP-0' (and through aliases); bare 'MACE' is cite_00048. GNoME and Matbench each span 4 types.
5. **Character noise.** 1,028 surface forms contain non-ASCII characters, including 1,376 U+2011 non-breaking hyphens and 268 U+202F narrow spaces. Normalise with NFKC.
6. **Misplaced types [I].** 17 dataset nodes are bare element symbols. Some datasets and reviews are typed as method (meth_00292 'OMat24 dataset', meth_00107 a review title). 30 of the 90 metrics are not obviously metrics.
7. **Uneven extraction per paper.** cites is missing for 15 papers and evaluated_on for 16; those papers also have no cited_work, dataset or metric nodes. Article 5405 has only presents, claims, authored_by and future-work edges. Claims per paper range from 6 to 60 (5453, a review).
8. **evaluated_on attributes.** The metric string is free text (95 distinct values; 16 edges differ from the member only in case), and value is null in 93 of 301 edges.
9. **Authors.** Some names collide and are probably the same person (Tess Smidt / Tess E. Smidt). The authored_by order is not first-author order.
10. **origin_year back to 1901** (PCA), 1908 (Voronoi) and 1910 (Lindemann) are genuine historical dates, not noise.

## 5. Questions and ground truth: how they fit the task [V]

**Type A (Q1–Q14):**
- Fields: expected_methods, method_claims (2–4 sentences each), method_evidence (source, location, quote), required_citations, and fp_categories with three groups: wrong_domain, outdated_as_main, valid_but_unlisted.
- 63 target slots covering 50 unique names. Q14's targets are datasets and benchmarks. Q9 and Q11 name method families rather than single methods.

**Type B (Q15–Q18):**
- Fields: as_of 2026-02, sources, required_claims (36 in total, with coverage, locations and evidence).

**Mapping to graph nodes:**
- 35 of 50 names match strictly (48 of 63 slots); about 37 of 50 also match by token. The `aliases` field resolves xDeepH.
- Truly absent: 'Bead-mapping', 'physics-informed', 'hybrid frameworks'.
- 33 targets map to several nodes (median 5, max 23 for Matbench), because names are split across types.

**Sources and citations:**
- Type B sources map to article nodes for 14 of 20. 32 of the 36 required claims have a source paper in the graph.
- Type A citations: 24–27 of 50 map to a unique article, depending on the matching rule.

**Time:**
- Most targets do not exist yet in the ≤2020 or ≤2022 snapshot. Only the full ≤2026 snapshot matches "as of Feb 2026".
- Q6, Q12 and Q14 need 2025–2026 papers to be complete.

**Flat lexical baseline:**
- TF-IDF of question text against node names has hit@10 of 2/63 and hit@50 of 6/63. No question names its targets literally, so retrieval needs semantics.

**Leakage warning:**
- Pairs of targets from the same question share a hyper-edge 85% of the time, against 44% for random target pairs and 6% for expected vs wrong_domain pairs.
- Most of that comes from `cites` edges. Without cites and cited_work, the rates drop sharply (e.g. Q12 from 78 of 78 pairs to 21).
- So ground truth is independent of the clustering only if cites edges are kept out of the clustering signal.

**Uses [I]:**
- **T6 extrinsic task:** type A questions are the queries; the strict- and token-matched node sets are the targets.
  - Count a hit when the drill-down reaches any node of the target set, or its super-node.
  - Core set: Q1, Q2, Q3, Q12, Q13, Q14; Q4–Q11 as a secondary, article-level set.
  - Count only targets that exist in the snapshot.
  - Use wrong_domain items (36, all of them other questions' expected methods) as hard negatives. Treat valid_but_unlisted as neutral.
  - Baseline: a flat ranking with the same encoder.
- **Faithfulness reference:** type A method_claims (188 sentences) and type B required_claims are human-written text, independent of the graph. Use them for NLI checks of glosses. Lexical overlap with claim nodes is low (best Jaccard about 0.36), so an entailment model or a blind judge is needed.
- **Semi-independent coherence check:** same-question pairs should be clustered together more often than expected-vs-wrong_domain pairs, compared against a null model. This holds only with cites edges held out of clustering.
- **Caveat:** the questions were probably curated from these same 52 papers, so the task is in-distribution. Do not claim the results generalise.

## 6. Semantic signal and the circularity hazard [V/I]

- **Available text.** There are no abstracts in the graph or the CSV. The only text is surface forms, method aliases, article titles and edge attributes. ground_truth.json contains 188 evidence quotes, 35 of them from abstracts, but that file is evaluation material.
- **Rich text:** claim (median 174 characters), titles (87), future_topic (60), problem (40).
- **Short names:** method, dataset, metric and cited_work have medians of 1–3 tokens.
- **Edge attributes:**
  - claims carry claim_type (15 values), evidence_type (12; 143 citation_only), evidence_strength (strong 421 / medium 243 / weak 26), confidence, and 'contested' on 3 edges.
  - evaluated_on carry metric, value, task, domain (mixed case), split and delta_vs_baseline.
- **Methods:** 52 presented methods have the full set of relations. 393 of 448 methods (88%) appear only as members of `extends` edges. evaluated_on covers only 36 methods (8%).
- **Citations as a held-out signal:**
  - 37 citing papers and 580 cited works; 122 are cited by two or more papers.
  - 47% of citing-paper pairs share a cited work: 65% when they also overlap structurally, 35% when they do not. So citations are correlated with structure but not identical to it.
  - The signal is thin early on: at ≤2020 there are only 9 citing papers and 9 shared cited works, so confidence intervals will be wide.
- **Recommended split [I]:**
  - **Nodes to cluster:** the concept types method, task, problem, technique, component, dataset and metric (3,980 nodes).
  - **Attach as text attributes:** claim and future_topic, to their paper or presented method.
  - **Leave out:** author, kept as metadata. Use the article as the provenance unit.
  - **cited_work:** either hold it out entirely for evaluation, or merge it into method by entity resolution, but not both.
  - **Down-weight:** hubs present in 10 or more papers.
  - **Coherence rulers:** (i) co-citation and bibliographic coupling, held out of clustering; (ii) ground-truth co-membership; (iii) a different embedding family, secondary only, because short names make two embedding families agree trivially. Compare each against a degree/arity-preserving shuffle and a within-type label shuffle.
  - **Claims cannot play both roles:** if claim text feeds clustering, it cannot also be the faithfulness reference. In that case use ground-truth method_claims instead.
- **Open question:** fetching arXiv abstracts for 36 papers would give a strong independent text signal. It needs an external call, and the brief doesn't say whether that is allowed.

## 7. Decisions this forces (for T2 and Deliverable 0)

1. **Snapshot rule and cutoffs:** §3 above.
2. **Which node types to cluster, and how to treat hubs:** §6.
3. **Entity resolution:** whether to merge near-duplicates and cross-type aliases (cited_work ↔ method) before clustering, and log every merge.
4. **T4 collapse rule:** it should respect the hub-and-target star structure. It also needs to say how a per-paper bundle edge collapses, because bundles mostly mean "same paper".
5. **Signal roles:** which held-out signal measures coherence, given that cites edges explain most ground-truth co-occurrence.
6. **Article 5405:** the 24-node island has to be handled explicitly in any spectral method.
