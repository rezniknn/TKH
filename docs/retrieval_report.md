# Extrinsic utility (T6): drill-down retrieval vs flat search

The brief's T6 asks for an extrinsic check: "a retrieval/agent that starts at a coarse level and drills down to find
target nodes, versus a flat baseline, scored on hit-rate or steps-to-target". This report covers that agent, its
evaluator and the result on the 18 questions in `data/questions.csv`, scored against `data/ground_truth.json`.

All numbers come from `out/metrics.json["retrieval"]`. The per-question answers, traces and gold resolution are in
`out/retrieval_answers.json`.

**Result.** On this question set the hierarchy does not help retrieval. The flat search reaches a target on every
question that has one (16/16). The drill-down reaches one on 6/16, because on 10 of them the beam drops every target
on the way down, 6 of them already at L0. Hit-rates are lower or equal on every item kind:

| | Hierarchical | Flat |
|---|---|---|
| Type-A methods (n = 12 with attainable methods) | 0.056 | 0.056 |
| Type-A citations (n = 14) | 0.124 | 0.311 |
| Type-B claims (n = 4) | 0.188 | 0.441 |
| Type-B citations (n = 4) | 0.208 | 0.396 |

Every paired hit-rate CI includes zero; the type-B ones only reach it at their upper bound. Both steps-to-target CIs
exclude zero: the drill-down needs more steps on type A (+1361.3 [762.9, 1956.3]) and on type B (+368.8 [51.0,
686.5], n = 4, descriptive). Read with n = 18, this is a negative result for the shipped hierarchy as a retrieval index,
not evidence that hierarchies cannot help.

## 1. Task and protocol

- **Input.** `data/questions.csv` (`question_id;question;type`) holds:
  - 14 type-A questions ("which methods … best suited for …"), whose answer is a list of methods plus their citations;
  - 4 type-B questions (open challenges, mechanisms, evidence), whose answer is a list of claims plus their citations.
- **Ground truth.** `data/ground_truth.json` gives, per question:
  - type A: `expected_methods` and `required_citations` ("Batatia et al. 2022");
  - type B: `required_claims`, each with its `sources`, a `sources` table, and `required_citations`, which are
    source keys.
- **Systems.** Both systems share the snapshot, leaf texts, encoder, answer kinds and answer length; only the search
  differs.
  - **Hierarchical:** the agent drills down the run's hierarchy, `out/<cutoff>/hierarchy.json`, with labels and
    glosses at L0–L1.
  - **Flat:** the same scorer ranks every leaf of the answer kinds.
- **Command.** `make retrieval`, i.e. `python -m eval retrieval --run out`.
  - It is part of `make all` and writes the `retrieval` section of `out/metrics.json`.
  - It needs no LLM and no rebuild, and runs in about 2 s.
  - Rerunning gives a byte-identical `metrics.json`.

## 2. The agent (`tkh/retrieve.py`)

1. **Question type** comes from the question's metadata (the CSV `type` column).
   - Type A answers with methods; type B with claims.
   - The answer kinds are fixed per type:
     - A: method, technique, component and dataset nodes. The GT field `expected_methods` also lists datasets and
       benchmarks (Q14).
     - B: claim nodes.
2. **Snapshot** (`choose_snapshot`):
   - The agent takes the latest cutoff not after the year the question names: "by Feb 2026" → 2026, "by March 2023"
     → 2022.
   - A question without a date gets the latest cutoff. Only Q16 has no date; it is recorded as `default_latest`.
   - All 18 questions map to 2026, which is consistent with the type-B `as_of: "2026-02"`.
   - From then on, only that snapshot's nodes, edges and hierarchy are used.
3. **Semantic content of a node.**
   - **Leaf text:**
     - name and aliases;
     - the names of the leaf's relation neighbours (`addresses`, `solves`, `extends`, `uses_*`, `evaluated_on`);
     - `evaluated_on` metric and task;
     - the title of the article that presents the leaf (presented methods, once) or makes it (claim nodes).
     - All of it comes from the snapshot's own edges.
   - **Encoder.** Word TF-IDF is fitted on the snapshot's leaf texts. The texts overlap with both clustering signals:
     the names, and the neighbours over the clustering relations. But the encoder is not the char-n-gram LSA of names
     that built the tree, and it adds titles and `evaluated_on` attributes. The question is encoded with its template words
     removed ("which methods … best suited for", "(by Feb 2026)").
   - **Super-node scores.** An L0 or L1 super-node scores 0.5·cos(q, label + gloss) + 0.5·cos(q, centroid of its
     members). An unlabelled L2 node scores its centroid.
4. **Drill-down** (`descend`):
   - Every L0 super-node is scored and the best 3 are kept.
   - Their L1 children are scored and the best 4 kept; then those nodes' L2 children are scored and the best 5 kept.
   - The pool is the leaves of the kept L2 nodes that have the answer kinds, ranked by cos(q, leaf).
   - The trace records each super-node scored, with its label, its score and whether it was kept. `closest` gives the
     best match at L0, L1, L2 and leaf level, and `top_leaves` gives the top-k leaves with their scores. The flat
     answer has `closest["leaf"]` only.
5. **Answer** (`extract`, k = 10), in the ground-truth format for the fields that are scored. The GT-only annotation
   fields (`method_claims`, `method_evidence`, `fp_categories`, `coverage`, `locations`, `evidence`, `caveat`, `venue`,
   `doi`, `evidence_type`) are not produced. Dates are years, and claim ids are R1…Rk.
   - **Type A:** `expected_methods` holds the top 10 distinct names (by `name_key`). `required_citations` holds
     "Surname et al. YYYY" for the articles those leaves come from: "A & B YYYY" for two authors, and "Anon. YYYY"
     when the export has no author for the article.
   - **Type B:** `as_of`, plus `required_claims` with the top 10 claims as `{id, text, node_id, sources}`. `sources`
     maps a key to `{key, title, date, article_id}`, and `required_citations` lists the keys.
   - Both types also carry the node and article ids the answer was read from, so the answer can be scored without
     string matching.

## 3. The evaluator (`eval/retrieval.py`)

Only the evaluator reads ground truth. A test (`test_agent_does_not_see_ground_truth`) cuts every question's expected
methods or required claims down to one item and checks that neither system's answers change.

### Gold resolution

Each ground-truth item is mapped to graph nodes of the question's snapshot, and the tier it matched on is recorded:

- **Methods** take the first tier that matches:
  - exact `name_key` match on the name or an alias ("DeepH-E3"; "DeepH" via an alias);
  - an acronym in parentheses ("GAP" → "Gaussian approximation potential (GAP) for silicon");
  - a leading segment of at least 3 characters ("Orb" → "Orb-v2", "PET" → "PET-MAD", "UMA" → "UMA-S").

  GT names that match no tier are unattainable. These include conceptual names ("physics-informed", "hybrid
  frameworks", "CE→MC→NN→PF") and specific methods absent from the graph (HamGNN, MACE-F, DeePMD+AL).
- **Type-A citations** match articles whose author set contains every listed surname (diacritics folded), with the
  year within ±1 and the exact year preferred. A parenthetical hint ("(DeepH)") narrows ambiguous matches by title or
  presented method. When candidates stay ambiguous, any of them counts.
- **Type-B citations** match source titles by `name_key` equality or word Jaccard ≥ 0.8.
- **Type-B claims.** The GT claims are paraphrased summaries, not graph sentences. A required claim is attainable if
  one of its sources resolves to an article with claims in the snapshot, and hit if the answer returns a claim of such
  an article.

### Metrics

- **Hit-rate**, per question: hits ÷ attainable GT items in the top-k answer. A GT method is hit if the answer contains
  one of its resolved nodes, or a node with the same `name_key` as one of them. Methods (A), claims (B) and citations
  (both) are scored separately. Questions with no attainable item of a kind are left out of that kind's mean.
- **Steps-to-target**, per question: one step is one node the agent inspects.
  - **Hierarchical:** the super-nodes scored on the way down, plus the rank of the first target in the pool.
  - **Flat:** the first target's rank among all leaves of the answer kinds (N = 2524 for A, 690 for B).
  - A target that is not in the hierarchical pool is censored at N + 1.
  - Targets are the resolved method nodes (A) or the claims of resolved source articles (B).
- **Summary:**
  - means over questions, per type and system;
  - the paired hierarchical − flat difference with a bootstrap 95% CI over questions (B = 2000, seed 0);
  - for steps, also the median and the number of questions that reached a target.
- **Diagnostic** `lost_at_level`: the first level at which no kept super-node holds a target.

### Ceilings

These are attainable / total GT items on the 2026 snapshot:

| | Attainable / total |
|---|---|
| Type-A methods | 49 / 63 |
| Type-A citations | 65 / 71 |
| Type-B claims | 26 / 36 |
| Type-B citations | 13 / 19 |

- Q5 and Q11 have no attainable method, so they have no type-A targets and are not part of the type-A methods and
  steps means.
- The type-B shortfall comes from sources that are not among the 52 articles, e.g. li2025_ood, jakob2025 and
  deng2025_softening (Q15).

## 4. Results

### Summary (means over questions; 95% bootstrap CI)

| Type | Metric | n | Hierarchical | Flat | Hier − flat |
|---|---|---|---|---|---|
| A | method hit-rate | 12 | 0.056 [0.000, 0.145] | 0.056 [0.000, 0.145] | 0.000 [−0.125, 0.125] |
| A | citation hit-rate | 14 | 0.124 [0.048, 0.215] | 0.311 [0.154, 0.493] | −0.187 [−0.403, 0.008] |
| A | steps-to-target, mean | 12 | 1700.8 [1082.3, 2319.2] | 339.6 [62.6, 640.8] | +1361.3 [762.9, 1956.3] |
| A | steps-to-target, median | 12 | 2525 | 53.5 | |
| A | questions reaching a target | 12 | 4 | 12 | |
| B | claim hit-rate | 4 | 0.188 [0.000, 0.375] | 0.441 [0.313, 0.540] | −0.254 [−0.508, 0.000] |
| B | citation hit-rate | 4 | 0.208 [0.000, 0.417] | 0.396 [0.292, 0.500] | −0.188 [−0.375, 0.000] |
| B | steps-to-target, mean | 4 | 371.8 [52.5, 691.0] | 3.0 [1.5, 5.0] | +368.8 [51.0, 686.5] |
| B | steps-to-target, median | 4 | 373 | 2.5 | |
| B | questions reaching a target | 4 | 2 | 4 | |

- Type B (n = 4) is descriptive only.
- The mean steps are dominated by the censored misses: 2525 for A and 691 for B.

### Per question

Snapshot: 2026 for all (Q16 by default, the others stated). Columns: targets / pool / super-nodes scored; item
hit-rate as hier | flat; citation hit-rate as hier | flat; steps as hier | flat; and the level at which the
hierarchy lost its targets ("–" means reached, "n/a" means no targets).

| Q | Type | Targets / pool / scored | Item hit (attainable / total) | Citation hit (attainable / total) | Steps | Lost at |
|---|---|---|---|---|---|---|
| Q1 | A | 15 / 43 / 42 | 0.00 \| 0.00 (7/7) | 0.14 \| 0.14 (7/7) | 2525 \| 109 | L2 |
| Q2 | A | 3 / 36 / 49 | 0.50 \| 0.00 (2/3) | 0.00 \| 0.43 (7/7) | 51 \| 26 | – |
| Q3 | A | 2 / 35 / 48 | 0.00 \| 0.50 (2/2) | 0.00 \| 1.00 (2/2) | 2525 \| 8 | L0 |
| Q4 | A | 2 / 6 / 41 | 0.00 \| 0.00 (1/3) | 0.33 \| 0.00 (3/3) | 2525 \| 108 | L0 |
| Q5 | A | 0 / 29 / 41 | – (0/2) | 0.00 \| 0.00 (1/2) | n/a | n/a |
| Q6 | A | 1 / 67 / 45 | 0.00 \| 0.00 (1/3) | 0.33 \| 0.33 (3/3) | 2525 \| 30 | L0 |
| Q7 | A | 1 / 38 / 41 | 0.00 \| 0.00 (1/2) | 0.00 \| 1.00 (2/2) | 2525 \| 1254 | L0 |
| Q8 | A | 1 / 20 / 44 | 0.00 \| 0.00 (1/2) | 0.50 \| 0.50 (2/2) | 55 \| 19 | – |
| Q9 | A | 2 / 62 / 51 | 0.00 \| 0.00 (1/3) | 0.00 \| 0.50 (2/2) | 2525 \| 1191 | L0 |
| Q10 | A | 1 / 23 / 42 | 0.00 \| 0.00 (1/2) | 0.25 \| 0.00 (4/4) | 2525 \| 1239 | L2 |
| Q11 | A | 0 / 71 / 41 | – (0/2) | 0.00 \| 0.00 (1/3) | n/a | n/a |
| Q12 | A | 32 / 6 / 45 | 0.08 \| 0.08 (13/13) | 0.07 \| 0.21 (14/15) | 46 \| 9 | – |
| Q13 | A | 18 / 27 / 42 | 0.00 \| 0.00 (8/8) | 0.00 \| 0.13 (8/8) | 2525 \| 77 | L2 |
| Q14 | A | 24 / 23 / 51 | 0.09 \| 0.09 (11/11) | 0.11 \| 0.11 (9/11) | 58 \| 5 | – |
| Q15 | B | 25 / 21 / 48 | 0.50 \| 0.50 (6/10) | 0.50 \| 0.50 (2/5) | 50 \| 2 | – |
| Q16 | B | 48 / 41 / 45 | 0.00 \| 0.44 (9/9) | 0.00 \| 0.25 (4/4) | 691 \| 3 | L1 |
| Q17 | B | 65 / 22 / 42 | 0.00 \| 0.57 (7/7) | 0.00 \| 0.50 (4/5) | 691 \| 6 | L0 |
| Q18 | B | 41 / 68 / 54 | 0.25 \| 0.25 (4/10) | 0.33 \| 0.33 (3/5) | 55 \| 1 | – |

Of the 16 questions with targets, the hierarchy lost them all at L0 on 6, at L1 on 1 and at L2 on 3, and reached a
target on 6.

### Worked traces

**Q2, where the hierarchy finds a method the flat search misses.** "…accelerating electronic structure calculations when self-consistent field
iterations become prohibitively expensive…"

- The closest match is "High-throughput DFT methods" at L0 and "Density functional techniques" at L1.
- A target-bearing L0 node, "Graph Neural Networks", ranks 3rd and is kept. Under it, L1 "Deep Hamiltonian Models"
  is kept, and that leads to DeepH ("deep neural network approach to represent DFT Hamiltonian") at step 51.
- The hierarchical answer contains DeepH (hit-rate 0.50). The flat top 10 holds none of the expected methods: it is
  filled with leaves that match the question's words literally ("self-consistent field", "Self-consistent training",
  "twisted bilayer graphene").
- Here the hierarchy filtered out lexical distractors that the flat ranking could not. On the other two metrics the
  flat search still does better on Q2: citations 0.43 vs 0.00 and steps 26 vs 51.

**Q3, a routing failure at L0.** "…learning DFT Hamiltonians when dealing with twisted van der Waals
heterostructures containing thousands of magnetic atoms?"

- The kept L0 nodes are "Long-range interaction models", "Graph Neural Networks" and "High-throughput DFT methods".
- The only L0 node holding a target, "E(3)-equivariant methods" (xDeepH and DeepH-E3), ranks 4th and falls outside
  the beam of 3.
- The L1 node "Deep Hamiltonian Models" is reached but holds neither target. Flat search ranks xDeepH 8th.

## 5. Failure analysis

- **Targets are spread across coarse clusters.**
  - Q1's 15 target nodes (MACE, M3GNet, CHGNet, GAP, NequIP, ACE, EquiformerV2) sit in 5 of the 15 L0 super-nodes,
    so a beam of 3 cannot keep them all.
  - This is consistent with the intrinsic finding that coherence is not supported at L0 (`docs/evaluation_report.md`
    §3). The questions ask along a use-case axis (scale, accuracy, task) that the L0 grouping does not follow.
- **The L0 scores are weak and close together.** In Q3 the kept third node scores 0.037 and the target-bearing fourth
  0.036 (trace in `out/retrieval_answers.json`). A one-place swap at L0 loses every target.
- **Small pools.** The kept L2 nodes hold 6–71 leaves of the answer kinds. On 2 of the 18 questions (Q4 and Q12, pools
  of 6) the pool is smaller than k = 10, and the answer has only 6 and 5 distinct names.
- **Lexical encoder.** The flat ranking also fails, by preferring leaves that echo the question's words. Method
  hit-rates are low for both systems (≈0.06): the question's wording rarely names the expected methods.
- **Citations follow the retrieved leaves.** Citation hit-rates track how many distinct articles the top-k leaves
  come from (`n_articles` per question). The flat answers cite more articles on 13 of 14 type-A questions and on all 4
  type-B questions: leaves of one L2 cluster often share a paper.

## 6. Threats to validity

- **Small n:** 18 questions, all on the 2026 snapshot. Type B has 4 questions, and its CIs are wide.
- **Lexical encoder.** Word TF-IDF is weak on paraphrase. A sentence-embedding model could change both systems'
  absolute numbers. The comparison is fair because both systems share the scorer.
- **Gold matching** depends on name normalisation and acronym and prefix tiers. Ambiguous citations count if any
  candidate is returned.
- **Claims are matched by source,** not by content. A returned claim of a source article counts even if it states
  something else.
- **Author order** is not in the export: displayed citations use the first listed author, but scoring uses the author
  set.
- **Yearly snapshots:** "by Feb 2026" cannot exclude papers from later in 2026.
- **One configuration.** Beam (3, 4, 5) and k = 10 were fixed before the first run and not tuned on these questions.
  A wider beam would trade steps for reach.

## 7. Design decisions

| # | Decision | Rationale | Rejected alternative |
|---|---|---|---|
| 1 | Question type from the CSV metadata | It is given with the question; type detection is not the object of evaluation | Regex or LLM type classifier |
| 2 | Snapshot = latest cutoff ≤ the stated year; no date → latest | It never uses content after the question's date (P6). It matches the GT `as_of` | Always the latest snapshot (would leak for earlier dates) |
| 3 | Only the snapshot's edges build node text | `tkh.semantic.attached_text` reads all edges and would leak later facts into earlier snapshots | Reusing `node_texts(mode="context")` |
| 4 | Word TF-IDF on leaf texts | It is not the char-n-gram LSA of names that built the tree, though it overlaps with both clustering signals (names, and clustering-relation neighbours). Offline, deterministic, no new dependency | Char-n-gram LSA (circular); an embedding model (needs a model download and a new pinned dependency) |
| 5 | Article titles in leaf text: once for a presented method, and for claim nodes | A method's own paper title describes it, and claims carry little context alone. Clustering excludes titles to avoid re-encoding "same paper"; retrieval has no such concern | Names only |
| 6 | No LLM in the agent | Deterministic, offline and fast enough for `make all` | LLM query rewriting or re-ranking (adds a component with its own accuracy to evaluate) |
| 7 | L0/L1 score = 0.5 label + 0.5 centroid; L2 = centroid | It uses the labels where they exist and hedges against vague labels. L2 has no labels | Label only (L2 unscorable); centroid only (ignores T5) |
| 8 | Beam (3, 4, 5), k = 10, fixed in advance | With n = 18, tuning would fit the test set. A beam limits the damage of a single wrong choice | Greedy descent (beam 1); tuned beam |
| 9 | Same scorer, leaf texts, answer kinds and k for both systems | Only the search differs, so the difference is the hierarchy's | A separate flat retriever |
| 10 | One step = one node inspected; hier pays for every super-node scored | It charges the hierarchy for its routing cost | Counting only leaves (favours the hierarchy) |
| 11 | Missed targets censored at N + 1 | A routing miss is worse than any flat rank, and the step count stays finite for means and CIs | Dropping misses (hides routing failures) |
| 12 | Ground truth only in the evaluator; leakage test | Keeps the agent blind to the answers | Agent-side alias lists from the GT |
| 13 | Method gold by tiers: exact → acronym → prefix; conceptual = unattainable | GT names are often acronyms or family names of graph nodes. Stopping at the first tier that matches avoids loose matches | Substring matching (would make "ACE" match "surface") |
| 14 | Citations by author set + year ±1 + title hint | Author order is lost in the export. Preprint and journal years differ | Exact "First author et al. YYYY" strings |
| 15 | Type-B claims hit by source article | GT claims are paraphrased summaries, not graph sentences. A source match is deterministic | Lexical threshold (arbitrary τ); LLM judge (needs live calls) |
| 16 | Datasets among type-A answer kinds | GT `expected_methods` lists datasets and benchmarks (Q14) | Methods, techniques and components only (Q14 unattainable) |
| 17 | Ceilings reported; unattainable items left out of hit-rates | The graph cannot answer what it does not contain. Separates retrieval failure from coverage | Raw recall against all GT items |
| 18 | Paired bootstrap CI over questions | Both systems answer the same questions; n is small | Unpaired CIs |
| 19 | Retrieval in `make all`, writing `metrics.json["retrieval"]` | Offline, about 2 s, no rebuild | A separate, manual step |

## 8. Reproduction

```
make retrieval                       # = .venv/bin/python -m eval retrieval --run out
.venv/bin/python -m pytest tests/test_retrieval.py -q
```

- **Options:** `--beam 3 4 5` (super-nodes kept per level, L0 first), `--k 10`, `--questions`, `--gt`.
- **Outputs:** `out/metrics.json["retrieval"]` (config, snapshots, summary, per_question) and
  `out/retrieval_answers.json` (per question: the gold resolution, plus both systems' answers in GT format with their
  traces).
