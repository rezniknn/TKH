# AI usage log

This file records how AI assistants were used in this assessment, as required by §9
(and the AI-error case required by §6a) of the task description.

For each major interaction it gives the tool, the task or module, the prompt, what was
accepted or changed, and what was checked.

## Tools

| Tool | Model / mode | Interface | Used for |
|---|---|---|---|
| Perplexity | Deep Research, Academic connector enabled | Web app | Finding candidate papers for §3 |
| Claude Code | Claude Opus 5.5 (`claude-opus-5-5`) | VS Code extension | Reading the brief and data, planning, code, writing |

## Log

### 1. Setting up this log (Claude Code)

- **Task/module:** §9 deliverable `AI_USAGE.md`
- **Prompt:** "Start AI_USAGE.md file in repo folder following the instructions in
  section 9 of the assignment. Keep a log of major prompts used throughout this session
  in that file according to what's specified in that section as we go through the
  assignment"
- **Accepted / modified:** Accepted the file structure.
- **Verified:** Checked against the list of required items in §9 and §6a.

### 2. Literature search for §3 (Perplexity)

- **Task/module:** §3 literature grounding (report: positioning against prior work)
- **Input:** The task brief, uploaded as an attachment.
- **Prompt:** "Find 3-4 best candidate papers most relevant to the research problem I
  will be solving based on proceed problem statement fully matching requested search
  criteria. Result should be 3-4 papers with links, brief summary and justification
  for why they are relevant to my research problem"
- **Output:** A four-paper shortlist, one paper for each strand §3 asks for:
  1. **Hypergraph clustering:** Kamiński, Misiorek, Prałat, Théberge, *Modularity
     Based Community Detection in Hypergraphs* (h-Louvain). Journal of Complex
     Networks, 2024.
  2. **Graph coarsening:** Kumar, Sharma, Saxena, Kumar, *Featured Graph Coarsening
     with Similarity Guarantees*. ICML 2023.
  3. **Dynamic hierarchical clustering:** Yu, Dhulipala, Łącki, Parotsidis, *DynHAC:
     Fully Dynamic Approximate Hierarchical Agglomerative Clustering*. SDM 2025.
  4. **Spectral hypergraph coarsening:** *HyperEF 2.0: Spectral Hypergraph Coarsening
     via Krylov Subspace Expansion and Resistance-Based Local Clustering*. IEEE, 2025.
     The output gave no authors.

  For each paper the output also gave a summary, the reason it is relevant, its main
  limitation for this task, and what to borrow from it. The raw output is kept outside
  the repo.
- **Accepted / modified:** Accepted as a candidate reading list, pending
  verification. The output's main framing is also accepted: none of the four papers
  meets P1–P6 alone, and the contribution is combining them and evaluating the result
  independently.
- **Verified:** Nothing yet.
- **Still to check:**
  - Each paper exists, with the stated authors, venue and year. HyperEF 2.0's authors
    still need to be found.
  - The links resolve to the stated papers.
  - The technical claims about each paper, checked against the paper itself. Examples:
    h-Louvain optimises using the two-section graph; DynHAC says small input changes
    can cause large dendrogram changes; HyperEF 2.0 uses clique and star expansions
    and reports results on VLSI benchmarks.
  - The fit with §3's suggested venues (KDD, NeurIPS, ICLR, WWW, TKDE). None of the
    four papers is from those venues, though all fall in the 2022–2026 window.

### 3. Concepts primer (Perplexity)

- **Task/module:** Background for all tasks, especially T1–T4 and T6
- **Input:** The task brief, uploaded as an attachment. Perplexity did not see the data.
- **Prompt:** "Explain in detail all the concepts referenced in the research
  assignment to someone with good Data Science fundamentals but rusty in the knowledge
  graph domain to help prepare getting started on the implementation and analysis of
  the temporal hyper graph following the assignment"
- **Output:** An explanatory guide covering:
  - knowledge-graph basics and provenance;
  - hypergraphs, arity, and what a pairwise (clique) projection loses;
  - temporal snapshots, cutoffs, growth measures and data-quality checks;
  - partitions, laminar hierarchies and refinement direction;
  - P1–P6;
  - hyper-edge collapse cases, with a sample `collapse_hyperedge` function;
  - hypergraph modularity, spectral methods and agglomerative clustering;
  - matching super-nodes across snapshots, and birth/growth/merge/split/death events;
  - warm starts and temporal regularisation;
  - a safe labelling pipeline.

  The raw output is kept outside the repo. Only the part up to the start of the
  "over-claim rate" section was saved; the rest was lost when pasting.
- **Accepted / modified:** Accepted as background explanation only. No design
  decision is taken from it without checking it against the brief and the data.
- **Verified (checked against the brief and `data/tkh_collection10.json` in Claude
  Code):**
  - The P1–P6 summaries and the level numbering (P_0 coarsest, P_K finest) match the
    brief.
  - The example field and relation-type names are generic, not the export's. The
    export uses `members` (not `member_ids`). Its 11 relation types are `addresses`,
    `authored_by`, `cites`, `claims`, `evaluated_on`, `extends`, `presents`,
    `proposes_future_work`, `solves`, `uses_component` and `uses_technique`. The
    examples given (`method_dataset_metric`, `comparison_table`, …) do not occur.
  - The proposed "internal fraction" (1 − distinct coarse endpoints / original arity)
    is badly named. An arity-4 edge collapsed fully into one super-node scores 0.75,
    not 1. It measures how much the edge shrinks, not what share of it is internal.
    Our own T4 statistic will be defined separately.
  - The temporal penalty 1[c_t(v) ≠ c_{t−1}(v)] only makes sense after cluster ids
    are matched across snapshots, and it is undefined for nodes that are new at t.
- **Not yet verified:** The general claims about hypergraph modularity and spectral
  methods; these are to be checked against the §3 papers.

### 4. Understanding provenance in the TKH export (Claude Code)

- **Task/module:** T1 (load and describe the data); background reading
- **Prompt:** "What does provenance mean in the context of this project?"
- **What the assistant did:** Read the brief. Ran ad-hoc Python over
  `data/tkh_collection10.json` to list the provenance fields by node type and
  relation type, and read the `meta.date_semantics` block.
- **Accepted / modified:** Accepted as a working understanding:
  - Node provenance is the list of MVKG source articles, plus `entity_id` for some types.
  - Edge provenance is one `article_id` plus its `article_year`.
  - Article nodes also carry `ingested_at` / `extracted_at`. These are pipeline dates
    from 2026, not publication dates, so they must not be used for snapshot cutoffs.
- **Verified:** The field names and per-type counts came from the assistant's script
  output, not from model recall. Example counts: 846/855 components and 690/690 claims
  have a single source article; datasets have `entity_id` for 220/259.
- **Not yet verified:**
  - The claim that "nodes sharing a source article usually also share a hyper-edge"
    (which would make same-article an unsafe independent coherence signal).
  - The claim that most entities were not merged across papers.
  - Both are to be checked in T1.

### 5. Repository skeleton (Claude Code)

- **Task/module:** §6 deliverables 1–7 and §6a (repository layout)
- **Prompt:** "Create repository structure matching deliverables creteria outlines in
  the assignment. Create empty files only for now with a frief comment at the top
  highlighting the purpose of that file"
- **What the assistant did:** Created placeholder files, each with a one-line purpose
  comment. They map to the deliverables as follows:
  - README, `requirements.txt`, `Makefile`: reproduction setup (deliverable 1, §6a.4).
  - `report.md` (deliverable 4).
  - `validate.py`, `schema/hierarchy.schema.json`, `make_tables.py` (§6a.1, §6a.3).
  - A `tkh/` package with one module per task (T1–T5). Evaluation modules (T6) sit in
    `tkh/evaluate/`: null models, independent coherence, stability, faithfulness and
    extrinsic.
  - Pipeline scripts in `scripts/`.
  - `out/` for the generated deliverables (deliverables 2–3) and `figures/`
    (deliverable 6).
  - `tests/` with one valid fixture and five broken fixtures (§6a.2).
- **Accepted / modified:** Accepted the layout. The module split is the assistant's
  proposal and may change once the method is designed.
- **Verified:**
  - Checked each §6 / §6a item against a file or folder.
  - `schema/hierarchy.schema.json` parses as JSON. JSON has no comments, so its
    purpose note uses the JSON Schema `$comment` keyword.
  - Generated JSON outputs are not pre-created; `out/README.md` describes them.

### 6. Commit after every change (Claude Code)

- **Task/module:** Repository workflow (deliverable 1: git repo)
- **Prompt:** "From now on: after every update done to the repository perform git add
  and git commit shortly describing what changed since the last iteration"
- **What the assistant did:** Made the first commit in the existing (empty) git
  repository. From this point, the assistant commits after each change with a short
  message. Commits made by the
  assistant carry a `Co-Authored-By: Claude` trailer, so the git history itself shows
  which changes were AI-assisted.
- **Accepted / modified:** Accepted.

### 7. Investigating the provided data (Claude Code)

- **Task/module:** T1 (describe the data); informs T2–T6 and the §6a validator
- **Prompt:** "Investigate what data is available in repo/data folder provided with
  the assignment and how it relates to the task at hand"
- **What the assistant did:** Ran a multi-agent workflow over the four files in
  `data/`. Five investigators each covered one area: structure and snapshots, data
  quality, questions and ground truth, semantic signal, and the article corpus. Each
  investigator was followed by a separate verifier that recomputed its headline
  numbers with fresh code. The consolidated findings are kept outside the repo, as
  working notes.
- **Accepted / modified:** Accepted as the basis for T1 and for the design decisions
  still open. The recommendations (snapshot rule and cutoffs, which node types to
  cluster, held-out signals) are proposals, not decisions yet.
- **Verified:** Each headline number was recomputed by an independent verifier agent.
  57 of 79 claims were confirmed, 22 were corrected and none were refuted. Where the
  two differed, the corrected values are used. The T1 numbers are still to be
  regenerated by the repo's own code (`tkh/describe.py`) before they go in the report.
- **AI errors caught here (candidates for §6a):**
  - The ground-truth investigator reported that `xDeepH` has no node in the graph. The
    verifier found an undocumented `aliases` field on 80 method nodes, and
    meth_00199 has aliases=['xDeepH'].
  - The same investigator recommended slicing snapshots by `first_seen_year`. Two
    other investigators showed that this field contradicts its documented meaning for
    127 nodes. It adds 30–70 isolated nodes from later papers to each early
    snapshot, so it was rejected in favour of a provenance-based rule.
  - A structural claim was described as "under 1 pp" when the real change was up to
    1.1 pp. A type breakdown ("tasks 149, cited works 127…") could not be reproduced
    under any definition and was discarded.

### 8. T1 notebook: loading and describing the evolving graph (Claude Code)

- **Task/module:** T1; `tkh/io.py`, `tkh/describe.py`, `notebooks/01_describe_graph.ipynb`
- **Prompt:** "Create a Jupyter notebook loading and describing the evolving graph (T1
  in the assignment)."
- **What the assistant did:**
  - Implemented loading and snapshot slicing in `tkh/io.py`, using the
    provenance-based rule from entry 7.
  - Implemented the T1 statistics in `tkh/describe.py`: counts, node and relation
    types, arity, hub structure, growth, leakage of the alternative year fields,
    components, shared nodes, and data-quality checks.
  - Built a notebook that calls these functions and saves static figures to
    `figures/`.
  - Created a Python 3.12 virtual environment and pinned the dependencies in
    `requirements.txt`.
- **Accepted / modified:** Accepted. Snapshot cutoffs are ≤2020, ≤2022, ≤2024 and ≤2026.
- **Verified:**
  - The notebook executes end to end with `nbconvert --execute`.
  - Its numbers match the independently verified values from entry 7: 2,144 nodes at
    ≤2022 under the union rule; 70,022 clique pairs vs 6,661 star pairs; 413 shared
    nodes; 127 / 154 / 36 year and provenance inconsistencies.
  - A closure assertion (every edge member is in its snapshot) passes at all four
    cutoffs.
  - The figures were inspected visually. Overlapping log-axis tick labels and
    fractional year ticks were found this way and fixed.
- **Bug caught:** The first execution failed because `Axes.boxplot(labels=...)` was
  renamed to `tick_labels` in the installed matplotlib (3.11). The assistant
  wrote code for an older API.

### 9. Parametrised input paths (Claude Code)

- **Task/module:** Reproducibility (deliverable 1, §6a.4); `tkh/config.py`,
  `configs/default.toml`, `tkh/io.py`, `tkh/describe.py`, notebook 01
- **Prompt:** "Make all input paths parametrised throughout this repo, do not assume
  that the same input files will be used when assessors will be executing the code,
  so make it easy to provide input paths as a configuration"
- **What the assistant did:**
  - Added a TOML config holding input paths (graph, articles, questions, ground
    truth), snapshot cutoffs and output directories.
  - Config selection, in order of precedence: an explicit `--config` path, then the
    `TKH_CONFIG` environment variable, then `configs/default.toml`. Scripts also
    accept per-value command-line overrides.
  - Relative paths are resolved against the config file's directory.
  - Removed hardcoded file names and cutoffs from the code.
  - Made the articles CSV optional: without it, publication years are derived from
    hyper-edge provenance.
  - Made the T1 checks skip optional fields (`first_seen_year`, `origin_year`, edge
    `year`) when an export lacks them, and replaced the hardcoded relation list with
    all relation types present.
  - Inputs are validated: missing files, missing CSV columns, fewer than 3 cutoffs,
    and article years that disagree with hyper-edge provenance all raise errors.
- **Accepted / modified:** Accepted.
- **Verified:**
  - The notebook executes with the default config.
  - It also executes with an alternative config: the graph renamed and moved to
    another folder, no articles CSV, cutoffs {2019, 2023, 2026}, and figures written
    elsewhere. Its numbers match the earlier verified values (e.g. 1,060 nodes at
    ≤2019).
  - Loading with the CSV and without it gives identical node entry years for all
    5,798 nodes.
  - Command-line overrides work, and the error paths for a missing input and for too
    few cutoffs were exercised.
- **Caveat:** The interpretive text in the notebook describes the provided export. The
  notebook says so; with other inputs, only the code outputs are recomputed.

### 10. Notebook failed on matplotlib < 3.10 (Claude Code)

- **Task/module:** T1 notebook; environment reproducibility (`requirements.txt`,
  README)
- **Prompt:** "The notebook has the following error when executed in Python 3.11.5
  environment: TypeError: Axes.boxplot() got an unexpected keyword argument
  'orientation'. Fix the notebook, make sure it can execute end to end without errors
  in Python environment recommended for this project"
- **Cause:** In entry 8, the assistant fixed a `boxplot(labels=...)` error by moving to
  the newest API, `orientation=` / `tick_labels=`. Those keywords exist only from
  matplotlib 3.9–3.10, so the notebook broke on older matplotlib. The user's
  environment had matplotlib 3.7.2. The fix had been tested only in the assistant's
  own venv.
- **Fix:**
  - The boxplot now passes `orientation=` on matplotlib ≥ 3.10 and `vert=False`
    otherwise, and sets the tick labels with `set_yticks(ticks, labels)`, which works
    on 3.5 and later.
  - The setup cell prints the Python, pandas and matplotlib versions.
- **Second issue found while verifying:** `requirements.txt` could not be installed on
  Python 3.11, because `numpy==2.5.4` requires Python ≥ 3.12. It is now pinned to
  2.4.6. The README states that Python 3.11 and 3.12 are supported, gives a uv
  alternative, and says to run the notebook with the project's `.venv`.
- **Verified:** A multi-agent check ran the notebook in three environments, each
  writing to a separate output folder:
  - a clean Python 3.12 venv built from `requirements.txt` only;
  - a clean Python 3.11 venv with the same pins and numpy 2.4.6;
  - the user's Anaconda environment (Python 3.11.5, matplotlib 3.7.2, pandas 2.2.2).

  All three ran end to end with no error outputs. The only warning was a pandas
  `bottleneck` version warning that comes from the Anaconda install itself. A
  separate audit agent checked the code against matplotlib 3.7–3.11, pandas 2.2–3.0,
  numpy 1.26–2.x and Python 3.11–3.12, and found no further issues. The notebook was
  then re-executed in the project `.venv` with no errors and no stderr output.

### 11. Growth visualisations, T1 section 5 (Claude Code)

- **Task/module:** T1 (how the graph grows and changes between snapshots);
  `tkh/describe.py`, notebook 01 §5
- **Prompt:** "Ceate visualisations of hypergraph growth over snapshots (section 5)"
- **What the assistant did:** Added computation helpers to `tkh/describe.py`:
  - `entry_period_layers`: snapshot contents split by entry period.
  - `new_nodes_by_type`: node types added per step.
  - `article_links`: pairs of papers sharing nodes, with a hub cutoff and a minimum
    number of shared nodes.
  - `growth`: now also reports the share of new nodes that share an edge with an old
    node.

  It also added three static figures (`figures/t1_growth_layers.png`,
  `t1_growth_steps.png`, `t1_article_links.png`) and a table of link counts.
- **Accepted / modified:** The first version of the paper-link diagram was rejected
  after visual inspection. Counting every shared node links about 95–100% of paper
  pairs, and even with hubs over 50% removed it is 55%, so the diagram was a solid
  tangle. The final figure excludes nodes found in more than 20% of papers and draws
  only pairs sharing at least 3 nodes. The thresholds are stated on the figure, and
  the table reports link counts at all three filtering levels.
- **Verified:**
  - An independent agent recomputed every plotted number from the raw JSON and CSV
    with its own stdlib-only code, without reading `tkh/`. All were confirmed
    exactly: period layers, new nodes by type, the three attachment rates, and link
    counts at each threshold.
  - The notebook executes end to end in the project `.venv` with no error or stderr
    outputs.
  - The figures were inspected for legibility. Overlapping labels and the misplaced
    figure caption were fixed.

### 12. Literature review of hypergraph clustering methods (Perplexity)

- **Task/module:** §3 literature grounding; method choice for T2
  (Deliverable 0: the alternative to reject)
- **Tool:** Perplexity Deep Research with the Academic connector enabled. The task
  brief was uploaded as an attachment.
- **Prompt:** "Make a comprehensive literature review of different methods of hyper
  graph clustering that could be used to create super nodes to enable creating
  different resolutions of a hyper graph that combine semantic and structural
  information or use either of the two signals only. For each method, list papers
  where that method was studied, brief summary of results, evaluate applicability of
  that approach to my problem statement at hand, list assumptions and limitations of
  the method"
- **Output:** A 21-section review.
  - **Method families (11).** For each: cited papers, reported results,
    applicability, assumptions and limitations. The families are:
    - hypergraph modularity (incl. h-Louvain and the Chodrow–Veldt–Benson DCHSBM);
    - hypergraph SBMs (incl. the attributed SBM of Badalyan, Ruggeri & De Bacco 2024);
    - spectral clustering;
    - spectral coarsening (HyperSF, HyperEF, SHyPar, HyperEF 2.0);
    - flow-based and information-theoretic methods;
    - hypergraph neural networks;
    - attributed models;
    - pairwise projection;
    - hypergraph-aware hierarchical agglomerative clustering (incl. DynHAC);
    - partitioning (KaHyPar, Mt-KaHyPar, SpecPart).
  - **Requirement map.** Which families suit each of P1–P6. It states that no single
    method satisfies all of them.
  - **Five experiment variants:** semantic-only, structure-only native,
    pairwise-projection baseline, joint, and joint with temporal coupling.
  - **Recommended final method:** constrained hierarchical agglomeration that is
    aware of the hypergraph. The merge score is
    s = α·s_semantic + β·s_hypergraph + γ·s_temporal. The merge tree is cut to meet
    the level budgets, hyper-edges are collapsed at each cut, and super-nodes are
    matched across snapshots by Jaccard similarity. The attributed SBM serves as the
    theoretical reference.
  - **An evaluation design and lists of assumptions and limitations to state.**
- The full report is kept verbatim outside the repo, as working notes. The first paste
  of the output was cut off at the message limit; the full report was then supplied as
  an attachment.
- **Accepted / modified:** Accepted as a candidate list of methods and papers, and as
  one proposal for T2. No design decision is taken from it yet.
- **Verified:** Nothing yet.
- **Still to check:**
  - That each cited paper exists, with the stated authors, venue and year. Several
    items have no authors, or descriptions the assistant could not confirm from memory
    (e.g. the "Bethe Hessian" paper in Sci. Adv. 2023, the 1-spectral and
    mutual-information papers).
  - The claimed results, e.g. HyperEF 2.0's "up to 4.5× speedup".
  - **Fit to this dataset,** checked against the data investigation (entry 7):
    - The review assumes rich node text, but TKH nodes are short surface forms with
      no abstracts.
    - Its structural similarity sums shared hyper-edges. Here the hyper-edges are
      per-paper bundles and about 93% of nodes appear in a single paper, so that term
      would mostly mean "same paper" unless the bundles are down-weighted.
    - Its §18 suggests conductance or cut as a coherence measure. That would be
      circular if the method optimises a cut or modularity objective.

### 13. Output validator, schemas and broken fixtures, §6a.1–2 (Claude Code)

- **Task/module:** §6a.1 (`validate.py`, `schema/`), §6a.2 (`tests/`); deliverable 2
  output layout (`tkh/export.py`)
- **Prompt:** "Let's start the algorythm implementation work by creating a validator
  described in section 6a. Create a mock output of multi-resolution representation
  algorythm matching specified requirements for the output structure (section 6).
  Create a validator that would check that the output passes all required creteria.
  Create a mutation of that output for each corner case that the validator needs to
  be able to detect, run the validator on those mutations and confirm that the
  validator catches broken fixtures that it's supposed to catch"
- **What the assistant did:**
  - **Output contract.**
    - Layout: `out/<cutoff>/hierarchy.json` per snapshot, plus
      `out/temporal_events.json`.
    - JSON Schemas for both files.
    - The per-level budgets N_k live in the run config, so an output cannot relax
      them.
    - The finest level (one node per cluster) is implicit.
  - **`validate.py`.** It prints one coded line per violation, with exit codes
    0/1/2/3. It checks:
    - the schema;
    - P1 laminarity (coverage, uniqueness, parent level, nesting);
    - P2 budgets;
    - the snapshot cutoff for member ids;
    - labels at levels 0–1;
    - event references and arity;
    - lineage completeness;
    - the id namespace.
  - **Test material.**
    - A synthetic graph.
    - A hand-built valid output that deliberately sits on the edges: a level exactly
      at its budget, and every event type.
    - 47 single-defect mutations, each committed as a fixture with its expected
      violation codes.
    - A deterministic mock generator that works on any input graph
      (`tests/mock_output.py`).
    - A pytest suite (`make test`).
- **Accepted / modified:**
  - Two rules were chosen by the assistant, and they are stricter than the brief:
    lineage is one fate per super-node per transition, and ids are global across
    levels and snapshots.
  - Both are documented in `validate.py` and the schema.
  - The cost: a mixed absorb-and-shed history must be logged by each super-node's
    dominant fate, and the member transfer itself is lost.
- **Verified:**
  - `make test`: 65 tests pass. They include:
    - every mutation rejected with exactly its expected codes;
    - the valid fixture passing;
    - the committed fixtures matching the generator;
    - a mock built from the full real graph passing;
    - 4 mutations of that mock being caught;
    - runtime tests for unreadable files, integer ids, undated nodes, duplicate
      cutoffs and an internal error (exit 3).
  - Where a mutation triggers more than its own code, each extra code was reviewed and
    kept only if it is a genuine consequence of the single defect. One example: a
    growth label that no longer matches the changed members.
- **AI errors caught (candidates for §6a):** The first version of the validator passed
  its own 42 tests, but two rounds of adversarial agents found real holes. Every claim
  was backed by a fixture the agent actually ran, then re-run by an independent
  checker.
  - **Round 1:**
    - **Crashes that looked like ordinary failures (exit 1):**
      - `"levels": 2.0`, which JSON Schema counts as an integer;
      - an unbounded `levels` value that hangs the validator;
      - deeply nested JSON;
      - unreadable files;
      - non-ASCII digit folder names;
      - integer node ids in the input graph.
    - **Invalid outputs accepted:**
      - a stray `02020/` snapshot folder that was never checked;
      - duplicate cutoffs in the config;
      - contradictory or empty event logs;
      - mislabelled continue/growth events.
  - **Round 2:**
    - an unrelated cluster could take over a surviving id (split source survives,
      merge into an existing id);
    - `change` events with zero member overlap were accepted;
    - the existence checks were not level-aware;
    - a one-level hierarchy made the level-1 label check vacuous.
  - All of these were fixed, and each is now a fixture or a test.
  - One validator bug was found while reviewing the fixtures themselves: the fallback
    index used for schema-invalid files dropped super-nodes with a malformed level,
    which produced false "dangling reference" reports.
- **Not verified / known limits:**
  - The checks cover the rules listed in the `validate.py` docstring, not the quality
    of the abstraction.
  - Many-to-many lineage cannot be expressed.

### 14. Illustrative unit of each entity and relation, T1 notebook §1 (Claude Code)

- **Task/module:** T1; `tkh/describe.py`, notebook 01 (new §1; former §1–7 renumbered
  §2–8)
- **Prompt:** "Update 01_describe_graph notebook to give an ilustrative example of what
  an ilustrative unit of each data entity and each relation between entities look
  like before diving into snapshot statistics, sizes, spans, evolution etc."
- **What the assistant did:**
  - Added helpers to `tkh/describe.py`: `example_article`, `article_nodes`,
    `node_examples`, `relation_examples` and `article_star`.
  - Added a new first section that walks through one paper. The paper is chosen by
    code: the one covering the most relation and node types, with ties going to the
    smallest. Here that is the MEGNet paper (2019), covering 11/11 relation types and
    12/12 node types.
  - The section shows the raw JSON of one node and one hyper-edge, one example node
    per type, and one example hyper-edge per relation type with its hub, members and
    attributes.
  - It adds a star diagram (`figures/t1_example_article.png`) and a short list of what
    this unit implies for the analysis.
  - The node examples prefer nodes shared with other papers but present in no more
    than 20% of them. The first version picked generic hubs such as 'materials
    science', which was changed after inspection.
- **Accepted / modified:** Accepted.
- **Verified:**
  - The notebook executes end to end in `.venv` with no error or stderr outputs.
  - The section numbers and the cross-references inside the notebook were updated
    together.
  - The statements in the new text were checked against computed values: only
    `claims` and `evaluated_on` carry descriptive attributes and repeat within a
    paper, and 76% of the example paper's nodes appear in no other paper.
  - The star diagram went through three layout iterations after visual inspection,
    because of overlapping boxes and arrows crossing other boxes.
- **Note:** The notebook-building script from earlier sessions was a scratch file and
  has been lost. The notebook is now edited in place.

### 15. Null models used in hypergraph clustering research (Perplexity)

- **Task/module:** T6 evaluation design (coherence vs a null model; the stability
  baseline)
- **Tool:** Perplexity Deep Research with the Academic connector enabled, as a
  follow-up in the same thread as entry 12.
- **Prompt:** "In the research papers studied earlier, what is typically used as a null
  model to compare results of more advanced algorithms against?"
- **Output:** A report on null models.
  - **Default structural null:** a degree- and hyperedge-size-preserving random
    hypergraph (configuration model).
  - **Other families:** uniform random hypergraph; DCHSBM, described as a
    community-generating reference rather than a no-structure null; microcanonical
    degree-corrected nulls; attribute-preserving nulls; temporal nulls.
  - **Proposed suite N0–N6:** uniform; degree-preserving; type-preserving; semantic
    shuffle; structure shuffle; temporal rewiring; persistence-matched.
  - **Protocol:** an effect size z and an empirical one-sided p-value,
    (1 + #{M_null ≥ M_obs}) / (R + 1).
  - **Terminology:** null model, baseline algorithm and ablation are distinct things.
  - The full report is kept outside the repo, as working notes.
- **Accepted / modified:**
  - Accepted the terminology and the protocol: z-score and empirical p-value over R
    null samples, with the pipeline and parameters held fixed.
  - Accepted the idea of a layered null suite, with structure, semantic and temporal
    controls, as input to the T6 design.
  - No specific null has been chosen yet.
- **Verified:**
  - The empirical p-value formula is the standard add-one permutation estimate, so it
    is never exactly 0.
  - The brief's §5 T6 itself asks for a "degree/arity-preserving hypergraph shuffle, or
    random labels", which matches the report's main recommendation.
- **Not verified / caveats:**
  - **Citations cannot be traced.** The `[cite:N]` markers refer to Perplexity's
    internal source list, which was not exported, so no claim in the report can be
    traced to a paper from this output.
  - **Fit to this data** (from entries 7–8):
    - Every hyper-edge is a star: its first member is the article or the presented
      method, and its other members are of fixed types per relation (e.g.
      `authored_by` → authors).
    - A plain configuration-model rewiring (N1) that ignores types and roles would
      give an author `uses_technique` membership and the like. That null is easy to
      beat, and beating it says little.
    - A useful structural null must preserve at least the relation type, the hub
      position and the member type of each slot, i.e. a type- and role-preserving
      variant of N2.
  - **Stability nulls need more care.** Snapshots are cumulative and old nodes are
    rarely touched again (entry 8: only 4–7% of old nodes are mentioned again per
    transition). Temporal nulls (N5/N6) therefore need care, and a "freeze old
    assignments" baseline is needed so that stability is not inflated by the data's
    own inertia.
  - **The coherence null is a different object.** For coherence (T6), the null is
    over partitions (random labels with cluster sizes preserved, per level), measured
    with a signal independent of clustering. The report's N3/N4 shuffles instead
    re-run the clustering on perturbed inputs. Both are useful, but they answer
    different questions.

### 16. Persistent super-node ids and event log across snapshots (Claude Code)

- **Task/module:** T3 identity bookkeeping; `tkh/temporal.py`, `tests/test_temporal.py`
- **Prompt:** None of its own. The matcher was written as one component of a larger
  request; the other outputs of that request were later removed from the repository at
  the user's request, and the matcher was kept.
- **What the assistant did:** Implemented `match_and_name`, which assigns persistent
  super-node ids to independently built per-snapshot clusters by member overlap.
  - Each old cluster points to its successor (largest overlap) and each new cluster to
    its predecessor.
  - Components of this pointer graph resolve into persist (continue / growth / change),
    split, merge, birth or death.
  - The resulting event log satisfies the validator's lineage rules: one fate per
    super-node per transition, and global ids that are never reused.
  - It only does identity bookkeeping. It does not regularise stability.
- **Accepted / modified:** Accepted.
- **Verified:** A property test runs 300 random sequences of nested partitions over 4
  snapshots, including many-to-many overlaps. Every event log must pass the validator's
  `check_events` and `check_id_namespace`.

### 17. Stability evaluator, T6 (Claude Code)

- **Task/module:** T6 stability; `tkh/evaluate/stability.py`, `tests/test_stability.py`
- **Prompt (abridged; the remainder concerned work that was later removed):** "Implement
  Stability evaluator from T6 strictly following outlined requirements"
- **What the assistant did:** Implemented both parts of the T6 stability text, for any
  `build` function that maps an input hypergraph to per-snapshot, per-level partitions.
  - **ARI:** per snapshot or transition and per level.
  - **Perturbation stability:**
    - remove 10% of the hyper-edges (5 seeds), stratified by publication period so that
      every cumulative snapshot loses about 10%;
    - rebuild with the same `build`;
    - ARI against the unperturbed partition, with a 95% t-interval.
  - **Cross-snapshot stability:**
    - ARI between consecutive snapshots on the nodes present in both;
    - a 95% interval over half-subsamples of the nodes;
    - a permutation p-value against random labels that keep cluster sizes (floor 0.001
      with 999 permutations).
  - **Giant-cluster share:** reported with every ARI, because a giant cluster dominates
    pair-counting ARI.
  - **Pooling:** `pool_over_runs` pools per-run values with a t-interval across
    independent runs.
- **Accepted / modified:** Four changes were made after an independent review:
  1. Edge removal is stratified by period instead of global. Global removal let the
     earliest snapshot lose only 6.7–10.4% depending on the seed.
  2. Subsampling without replacement replaced a bootstrap with replacement. Duplicated
     nodes create agreeing pairs and bias ARI upwards.
  3. p-values at the floor are reported as such. The random-labels null is documented as
     weak: the informative comparison is method vs null model.
  4. The largest-cluster share is reported next to every ARI.
- **Verified:**
  - The ARI implementation matches `sklearn.metrics.adjusted_rand_score` to 1.1e-16 on
    500 random cases, and matches scikit-learn's documented reference values.
  - The tests cover the per-period 10% removal, a builder that ignores edges giving
    ARI = 1 under perturbation, the t-interval formula, and permutation-p behaviour.
- **Not verified / limits:**
  - Not yet run on a method's hierarchy.
  - Only level-wise ARI is computed, with no hierarchy-aware (laminar) ARI. The brief
    allows this.
  - The id matcher is not evaluated, because ARI ignores ids.

### 18. Investigation of the semantic signal in the metadata (Claude Code)

- **Task/module:** P3 / T2 input analysis; `notebooks/02_semantic_signal.ipynb`,
  `tkh/semantic.py`, `tkh/evaluate/groundtruth.py`, `tests/test_semantic.py`
- **Prompt:** "Create a notebook with an investigation of semantic information that we
  have available in the graph's metadata and if it can be meaningfully used by a
  clustering algorithm"
- **What the assistant did:**
  - **Inventory.** Text fields by node type, their length, aliases, attached text and
    noise.
  - **Representations.** Lexical only, with no downloads: word and character n-gram
    TF-IDF over the name, or the name plus attached claim/evaluation text, each raw and
    with LSA. That gives 8 representations.
  - **What similarity encodes.** Node type, paper identity, links across papers and
    duplicates.
  - **Agreement with the ground truth.** Same-question vs wrong-domain method pairs,
    scored by AUC against a within-type shuffle null (99 permutations), with a z-score
    and an empirical p-value.
  - **Trial clustering.** Average linkage on semantics alone.
  - **New code.** Text and vector helpers in `tkh/semantic.py`; strict name and alias
    matching to ground truth in `tkh/evaluate/groundtruth.py`.
- **Findings:**
  - **Text is thin.** Concept nodes have only short names (median 2–5 tokens) and no
    descriptions.
  - **Lexical similarity partly regroups by type:** 10-NN share the node's type 0.43 of
    the time, against 0.18 by chance.
  - **It partly re-encodes the paper:** neighbours share a paper 0.23 of the time,
    against 0.03 for random pairs.
  - **It still adds links across papers,** for about half of the nodes with a strong
    neighbour. Many of those are duplicates of the same entity across types (276 pairs
    with cosine ≥ 0.9).
  - **No detectable ground-truth separation** beyond the null in any representation
    (p ≥ 0.21). Attached context text makes it worse.
  - **Raw TF-IDF chains** into one cluster: 99.6% of nodes at k=15. LSA reduces this to
    about 7% at k=60.
- **Accepted / modified:** Accepted.
- **Verified:**
  - An independent agent reimplemented everything from the raw JSON without the repo
    code and confirmed all headline numbers: 3,980 concept nodes; 42/63 matched slots;
    121/56 pairs; AUC 0.581 with null mean about 0.54 and p about 0.3; the 10-NN type
    and paper shares; the 99.6% giant cluster.
  - Following its points, the notebook now states the test's low power (about 26
    expected and 11 wrong-domain targets) and the LSA clustering's sensitivity to the
    SVD seed.
  - Two runs of the notebook give identical outputs.
  - 399 tests pass.
- **AI errors caught (candidates for §6a):**
  1. **`clean()` normalised in the wrong order.** It replaced U+2011 after NFKC, but
     NFKC maps U+2011 to U+2010, so hyphens were never normalised. Hyphenated names had
     two spellings in the character n-grams. It was caught by an assertion in a
     self-check and fixed by mapping every Unicode dash after NFKC; a test now covers
     it. The near-duplicate count changed from 249 to 276.
  2. **The null model was not reproducible.** It iterated over `set(types)`, and the
     iteration order of a set of strings changes between runs (hash randomisation), so
     the permutations differed across runs despite a fixed seed. It was caught when the
     figure and the table of two runs disagreed; it now iterates in sorted order, and two
     runs are confirmed identical.
  3. **A prose claim was wrong.** The notebook said every observed AUC lies inside the
     null range, but one lies below it. Corrected.
- **Open:** Whether to bring in text from outside the export, such as arXiv abstracts or
  a pretrained embedding model. Both need a download, and neither is required by the
  brief.

### 19. Notebook 02 failed on matplotlib < 3.10 (Claude Code)

- **Task/module:** `notebooks/02_semantic_signal.ipynb`; `tests/test_notebook_compat.py`
- **Prompt:** "Error when executring the notebook: TypeError: Axes.boxplot() got an
  unexpected keyword argument 'orientation'"
- **Cause:** The same class of bug as entry 10, reintroduced by the assistant. The
  box-plot call tried to switch on the matplotlib version, but wrote
  `orientation="horizontal" if new else None`. On older matplotlib that still passes
  `orientation=None`, which the old API rejects. The notebook had been executed only in
  the project `.venv` (matplotlib 3.11).
- **Fix:**
  - The keyword dictionary is now built under the version check, as in notebook 01.
  - The near-duplicate example table differed between environments, because many pairs
    tie at cosine 1.0 and their order depended on library versions. It now sorts
    deterministically by rounded cosine and then by name.
- **Prevention:** A new static test (`tests/test_notebook_compat.py`) scans every
  notebook's code cells and fails on `orientation=` without a version check, or on
  `boxplot(labels=/tick_labels=)`. It flagged the old version of notebook 02 and passes
  the fixed one.
- **Verified:**
  - The notebook executes end to end in the project `.venv` (Python 3.12, matplotlib
    3.11, scikit-learn 1.9) and in the user's Anaconda environment (Python 3.11,
    matplotlib 3.7.2, scikit-learn 1.3.0, pandas 2.2.2). Neither run has error outputs;
    the only stderr is Anaconda's own `bottleneck` version warning.
  - All 15 text outputs are identical between the two environments.
  - 401 tests pass.

### 20. Can paper abstracts be retrieved from the metadata? Notebook 02 §5 (Claude Code)

- **Task/module:** P3 semantic-signal options; `tkh/abstracts.py`,
  `tests/test_abstracts.py`, `notebooks/02_semantic_signal.ipynb` §5
- **Prompt:** "Theoretically speaking, is it possible to download paper abstracts given
  the metadata available? Verify in the new section of the current notebook"
- **What the assistant did:**
  - **Offline route planning:** 36 of 52 articles have an arXiv id (and a DOI); 16 have
    only a title.
  - **An opt-in live check (`TKH_ONLINE=1`):**
    - arXiv API by id, requesting v1 (the abstract as first posted);
    - OpenAlex title search, falling back to an exact-phrase arXiv title search;
    - every record verified against the export's title (similarity ≥ 0.9).
  - **Politeness:** one arXiv request every 3 s and one OpenAlex request per second. Only
    arXiv ids and titles are sent, and nothing is stored.
- **Result:** 49/52 abstracts retrieved and verified.
  - 47 matched directly.
  - 2 papers were renamed after v1 (JARVIS, DeepH). The latest version's title matches
    the export, so the v1 abstract is kept.
  - 2 papers have a record but no abstract (OQMD 2013, fracture patterns 2020).
  - 1 has a wrong arXiv id in the export (5453: the id resolves to a different paper).
    This is an export data-quality issue.
  - No arXiv v1 abstract is dated after its export year. The 3 records dated a year
    later are OpenAlex publication dates.
- **Accepted / modified:** Accepted as a feasibility answer. Whether to use abstracts is
  still open: it needs a network call at build time or a cached copy, and abstracts
  relate papers and their presented methods, not every node.
- **User edits respected:** Before this change the user had removed the notebook's
  ground-truth section. The new section was fitted around that: it is numbered §5, has
  no ground-truth dependency, and leaves the user's cells untouched.
- **Verified:**
  - 6 offline unit tests pass (Atom parsing, OpenAlex abstract reconstruction, title
    matching including truncated titles, routes).
  - The notebook executes offline (the live cells print "skipped") and online, with no
    errors either way.
  - 407 tests pass.
- **AI errors caught:**
  1. The first version compared only the v1 title, which wrongly rejected two correct
     arXiv ids for renamed papers.
  2. The arXiv title fallback ANDed 12 words and found nothing.
  3. The first wording called OpenAlex publication dates "first-posted".

  All three were found by inspecting the failures and fixed before commit.

### 21. SHAC-T method: hypergraph-aware constrained agglomeration (Claude Code)

- **Task/module:** T2, T4; `tkh/coarsen.py`, `tkh/hierarchy.py`, `scripts/build.py`,
  `docs/formal_statement.md`, `tests/test_hierarchy.py`
- **Prompt (abridged):** "propose an implementation of hypergraph-aware constrained
  hierarchical agglomeration with semantic similarity and temporal matching as described
  in notes/hypergraph_clustering_review_perplexity.md report documenting all design
  decisions, assumptions and trade offs made. The implementation must be done in a way
  that would allow easily making changes to the key parameters [...] select and document
  the most optimal configuration providing empirical evidence [...] strictly adhere to
  creteria defined in T2 [...] Any final representation produced by the algorithm must
  adjere to P1 - P6 [...] in parallell with the implementation of the evaluation
  framework described in T6 [...] including the implementation of a null model [...]
  Circularity needs to be neutralised [...] Work only with the information available in
  the graph export (semantic, structural), don't use abstracts or paper text."
- **What the assistant did:** This is step 1 of an agreed plan; the evaluation, nulls
  and labels follow in later entries.
  - **Design.** Two independent design-review agents covered native vs projection,
    normalisation, the giant-cluster cap, anchoring and the temporal term.
  - **Structural score.** The degree-normalised λ−1 connectivity-cut reduction, computed
    on the collapsed incidence (T4 applied at every merge).
  - **Semantic score.** Centred character n-gram LSA of the names.
  - **Mixing and constraints.** Mid-rank CDF mixing with weight α, a temporal
    co-membership prior γ, and a size cap ρ with a feasibility lemma.
  - **Other nodes.** Non-concept nodes are anchored to concept nodes; citations are
    excluded from the clustering input.
  - **Configuration.** All parameters are in `[method]` and can be overridden with
    `--param`.
- **Accepted / modified:** The first build took 77 s. After profiling (CDF lookups and
  the weighted-incidence rebuild dominated), it takes 25 s with identical partitions.
  A claim in the formal-statement draft named "accuracy" and "classification" as hubs.
  Checking the data showed the real hubs are domain terms ("materials science",
  "molecular dynamics", ...) and "MAE", and the text was corrected.
- **Verified:**
  - `validate.py out/` exits 0 on the real graph (15/60/240 super-nodes per snapshot),
    and on the fixture graph.
  - Tests:
    - the T4 collapse cases;
    - the merge-gain identity (Prop. 1) on 50 random cases;
    - native = projection at singletons, and different after a merge;
    - the ρ = 2 feasibility on 40 random cases;
    - exact budgets, nesting and coverage;
    - determinism;
    - γ = 1 reproduces an unchanged snapshot;
    - anchors lie in the snapshot.
  - The draft's numbers were checked on the data: H = 0 for 99.4% of item pairs, and
    87.8% of concept nodes sit in at most one edge.
- **Not verified / limits:**
  - No quality claim yet: coherence, stability, labels and the extrinsic task are
    evaluated in later steps.
  - Labels are placeholders.

### 22. SHAC rewrite: simple constrained hypergraph agglomeration, null model, held-out P3 check (Claude Code)

- **Task/module:** T2, T4, P1–P3; `tkh/hierarchy.py`, `tkh/coarsen.py`, `tkh/null.py`, `tkh/p3.py`,
  `tkh/experiments.py`, `tkh/pipeline.py`, `tkh/__main__.py`, `docs/formal_statement.md`,
  `tests/test_hierarchy.py`, `tests/test_null.py`, `Makefile`, `README.md`
- **Prompt (abridged):** "Your objective is to propose a simple implementation of hypergraph-aware
  constrained hierarchical agglomeration with semantic similarity [...] documenting all design
  decisions, assumptions and trade offs made. The implementation must be done in a way that would allow
  easily making changes to the key parameters [...] select and document the most optimal configuration
  providing empirical evidence. The implementation must strictly adhere to creteria defined in T2 [...]
  Any final representation produced by the algorithm must adjere to P1, P2 and P3 [...] The fixtures
  produced by the method have to pass implemented validation described in 6a [...] Work only with the
  information available in the graph export (semantic, structural), don't use abstracts or paper text.
  Take into account conclusions from 01_descrive_graph.ipynb, 02_semantic_signal.ipynb and
  03_structural_signal.ipynb [...] The implementation is only considered done when 1. A formal statment
  is defined [...] 2. An implementation of the method in python is done in /thk folder 3. An
  implementation of a suitable null model [...] 4. When the implemented model is run on the input data
  provided producing graph representation that fullfilts P1, P2 and P3 creteira 5. When the output
  representation is validated by the implemented validator". Follow-up decisions by the user: P3 is
  shown with an independent held-out check; clean rewrite reusing proven parts; "make threashold for a
  node to be considered a hub a varying parameter"; "make sure no assumptions on the budget sizes drive
  the design decisions"; "include testing different hub_frac values around the default 0.2 value".
- **What the assistant did:**
  - **Grounding.** Parallel readers covered the brief, the literature notes, notebooks 01–03 and the
    existing code. A reviewer turned them into a compliance matrix. Three design reviewers (compliance,
    statistics, simplicity) and a synthesis then fixed the design before any code was written.
  - **Method (SHAC).**
    - The structural rank is positive-only (F_H(0) = 0), so unlinked pairs get no structural credit.
    - `relation_balanced` edge weights are the default; inverse_size gives evaluated_on 85% of the
      weight.
    - Parameters are strict (unknown keys are an error); `hub_frac` is a free parameter and 1.0 means
      no hubs.
    - Any budget list of length ≥ 2 works.
    - The T4 records come from the method's own incidence.
    - Removed: the γ prior, the projection variant and the null hooks. The label future-information
      leak is fixed.
  - **Null model.** The type- and period-preserving hypergraph configuration model: Curveball trades
    within (relation, cutoff interval, member type). Every snapshot keeps its node set, which is
    asserted. Null runs go through the same pipeline and validate. Random labels are a companion.
  - **Held-out P3 check.** Bibliographic coupling on paper pairs that share no concept node or name,
    with a residual filter; the ruler is fixed by the evaluator.
  - **Selection.** A sweep over 60 configurations, plus α = 0 and α = 1 ablations, with one-SE
    selection on 20 cited-work halves.
  - **Formal statement.** Rewritten in full.
- **Accepted / modified (an independent verification workflow: 5 finders, each finding checked by a
  skeptic; 32 of 35 survived):**
  - **Two majors in my code.**
    - The rank CDFs ran on raw floats, so last-digit round-off split ties and changed the 2022
      hierarchy. S and H are now rounded to 1e-12 before ranking.
    - The P3 no-overlap and residual filters ignored aliases, which the clustering sees. They now use
      surface forms and aliases.
  - **Minor code fixes.**
    - The sweep ignored the configured parameters.
    - The half split always gave odd strata's extra work to half A.
    - A claim-anchor edge case.
    - CLI arguments that were accepted but ignored.
    - A stale `metrics.json` after a rebuild.
    - A P3 check on a null run is now refused.
  - **Formal statement corrections.**
    - "Supports levels 0–1" overstated level 1.
    - The α = 1 ablation was called "lowest", which is false.
    - The SE scale was mis-paired with the criterion.
    - Runtime, cap and SVD wording.
    - Data numbers that do not come from `out/`.
  - All results were recomputed after the fixes.
- **Verified:**
  - `validate.py` passes on `out/` (15/60/240 super-nodes, 4 snapshots), on a null run validated
    against its own graph, and on runs with budgets (10, 40, 160, 640), (12, 3000) and (1, 2) …
    (1, 2, 4, 8, 16) on the fixture.
  - Tests: 430 pass, including the null invariants (degrees per relation, interval and type; arity;
    hubs; other relations untouched; node sets), F_H(0) = 0, Prop. 1, the cap lemma, exact level
    sizes for any budget list, determinism on the real ≤2020 snapshot, and an alias-aware no-overlap
    mask.
  - P3 at ≤2026 against 99 null rebuilds and 999 random labels:
    - level 0 beats both nulls (p = 0.01, 0.001);
    - level 1 beats the configuration null (p = 0.02), and random labels only under the fuzzy filter;
    - level 2 beats neither.
- **Not verified / limits:**
  - P3 holds at the coarse levels only, and only conditionally on the 37 citing papers. The bootstrap
    CIs over papers include 1.
  - The ruler cannot rank configurations: the half-A and half-B rankings correlate at a median ρ of
    −0.07. So the shipped default is "not distinguishable", not "optimal".
  - P5 and P6 are out of scope here; labels are placeholders.
  - `make_tables.py` and a full T6 evaluation are not part of this step.

### 23. Coherence per snapshot and level, controlling for publication period (Claude Code)

- **Task/module:** P3, T6 null comparison; `tkh/p3.py`, `tkh/experiments.py`, `tkh/semantic.py`,
  `tkh/__main__.py`, `tests/test_null.py`, `docs/formal_statement.md` §§6, 8
- **Prompts:**
  - "Exaplain what the failed check at Level 2 mean in detail"
  - "Evaluate model's coherence against null models controling for publication period as a confounder.
    Run evalution for each snapshot individually and report per-level coherence of the model compared to
    null models"
- **What the assistant did:**
  - **Diagnosis of the level-2 failure.**
    - Level 2 is mostly single-paper bundles: median paper purity 1.0, and only 52% of no-overlap pairs
      are co-assigned.
    - Both nulls keep period composition, and same-period papers are coupled more often (35% vs 20%).
    - So random labels gained from same-period mixing (61–65% of their co-assignment mass on same-period
      pairs, against 22% for SHAC).
  - **Period-adjusted lift.** Indirect standardisation: Σ a·c / Σ a·e, with e the mean coupling in the
    pair's period stratum.
  - **Per-snapshot check.** Every snapshot is evaluated on its own: the ruler, the nulls and the pairs are
    rebuilt at each cutoff, with 99 configuration-null rebuilds and 999 random labels per snapshot.
- **Accepted / modified (an independent recomputation and a method review):**
  - The recomputation reproduced every cell exactly.
  - **Period bins.** My first version used 2-year bins. The review showed they straddle the cutoff
    intervals, leave period structure in the random-label null, and that level 2's verdict flips with the
    binning. Changed: the primary strata are now the cutoff intervals (aligned with the null's
    permutation strata). 1-, 2- and 3-year bins and the year gap are reported as sensitivity, and only
    results that hold under every scheme are called robust.
  - **Name key.** It dropped Greek letters. It is now Unicode-aware.
  - **Output.** `metrics.json` held bare NaN literals; it is now strict JSON. Undefined bootstrap draws
    are counted. One null graph per seed instead of one per cutoff.
- **Verified:**
  - **Robust P3 evidence:** ≤2026 levels 0 (lift 1.46) and 1 (1.26). Both nulls are at about 1.0 and at
    their p floor under every period scheme.
  - **Not robust:** ≤2026 level 2 (1.04, p = 0.36).
  - **No robust evidence:** ≤2022 and ≤2024, with 11 and 21 coupled pairs.
  - **Not evaluable:** ≤2020, with 5 coupled pairs in one stratum.
  - 431 tests pass, including that the adjustment cancels a pure period effect.
- **Not verified / limits:**
  - The null tests are conditional on each snapshot's papers; the paper-bootstrap CIs include 1
    everywhere.
  - Citation coupling as a proxy for meaning is assumption A3.

### 24. Evaluation code moved out of the method package to eval/ (Claude Code)

- **Task/module:** `eval/p3.py`, `eval/experiments.py`, `eval/__main__.py`, `tkh/__main__.py`, `tkh/config.py`
- **Prompt:** "Move p3 coherence metric implementation and the source code supporting experiment runs to
  repo/eval folder"
- **What the assistant did:**
  - **Moved with `git mv`:** `tkh/p3.py` (the held-out ruler) and `tkh/experiments.py` (the per-snapshot
    check and the sweep), into a new `eval/` package.
  - **CLI split:** `python -m eval p3|sweep` is the evaluation; `python -m tkh build|null` stays the
    method. The `--param` parser moved to `tkh.config.parse_overrides`, so both CLIs share it.
  - **Dependency direction:** `tkh/` does not import `eval/`; `eval/` uses `tkh`.
  - **Kept in `tkh/`:** `tkh/null.py`, the null model that is part of the method deliverable and is used by
    `python -m tkh null`.
  - **Updated:** the Makefile, README, formal statement and test imports.
- **Verified:**
  - 431 tests pass.
  - `python -m eval p3` runs end to end; the committed `metrics.json` was restored unchanged.
  - A small sweep runs through the process pool.
  - No module in `tkh/` imports `eval`.

### 25. eval/p3.py renamed to eval/coherence.py (Claude Code)

- **Task/module:** `eval/coherence.py`
- **Prompt:** "Rename p3.py to coherence.py"
- **What the assistant did:** `git mv`, and updated the imports in `eval/experiments.py` and
  `tests/test_null.py` and the references in the README, formal statement, `eval/__init__.py` and
  `tkh/structure.py`. The CLI subcommand stays `python -m eval p3`.
- **Verified:** 431 tests pass; no reference to `p3.py` remains outside the AI usage log.

### 26. Formal statement brought in line with the implementation (Claude Code)

- **Task/module:** `docs/formal_statement.md`
- **Prompts:**
  - "Is T4 requirement satisfied already and well-documented in the formal statement?"
  - "Update the formal statement to reflect what is currently implemented"
- **What the assistant did:**
  - **Audit.** A workflow of 4 auditors, one per section group, checked every claim and number against the
    code and outputs, and 69 skeptic agents re-checked each discrepancy. 68 survived.
  - **Rewrite.** The statement was rewritten in full.
  - **§3 (T4):**
    - a disjoint class table (internal, partial, uncollapsed), with multi-way as a flag, mapped to the
      brief's m;
    - why presence rather than counts;
    - fixed weights; parallel edges kept separate; which edges are collapsed;
    - the record format and the complete list of losses.
  - **Elsewhere:** module table, hubs as items, exact text pipeline, anchoring rules, the validator's actual
    checks, determinism limits, complexity and memory, null and ruler details, and assumptions A6–A7.
- **Verified:**
  - A final independent fact-check reproduced every number.
  - It found one wrong figure (rescans 8340 → 7870), one understated memory peak (1.5 → about 2 GB), and
    three wording issues. All were fixed.
  - All tables have consistent column counts.

### 27. T3 temporal coupling (localised prior) and the T6 stability evaluator (Claude Code)

- **Task/module:** T3, T6 stability, P5; `tkh/hierarchy.py` (`gamma`, `stable_nodes`, `build_concept`),
  `tkh/null.py` (`intervals=`), `eval/stability.py`, `eval/experiments.py`, `eval/__main__.py`,
  `tests/test_hierarchy.py`, `tests/test_stability.py`, `docs/formal_statement.md` §§2, 6, 8, 9, 12, README,
  Makefile
- **Prompt (abridged):** "Your objective is to extend currently implemented coarsening method to ensure temporal
  stability across snapshots grounded in literature review [...] The implementation must strictly ahere to the
  requirements outlined in T3 [...] Simultaneously, implement an evaluator computing stability metric strictly
  adhere to the requirements outlined in T6 Stability [...] The implementation is only considered done when 1.
  The implementation is adjusted to satisfy temporal stability creteria 2. An implementation of stability
  evaluator is done and saved in repo/eval folder 3. Output graph representations are reconstructed and
  verified 4. Evaluation is run on the reconstructed graphs reporting the results". The user's design choices:
  a localised temporal prior; CIs, a new-paper null and variant comparisons; a γ sweep that reports the
  trade-off without selection.
- **What the assistant did:**
  - **Method.** The literature review's evolutionary-clustering term: s_t = (1 − γ)s + γΠ, where Π is the
    previous co-membership of *stable* old nodes, i.e. those not touched by a new paper's clustering edge and
    with unchanged hub status.
    - Snapshots are built as a chain; γ = 0 reproduces the old build exactly (tested).
    - This reuses the removed γ prior from git history, now restricted to the stable set.
  - **Evaluator.**
    - Perturbation: 10% of all hyper-edges, 5 seeds, full chain rebuild, ARI per level and HARI, t-intervals.
    - Cross-snapshot ARI and HARI with subsample intervals, against a new-paper null (only the new interval's
      edges rewired; 19 seeds).
    - Change localisation (touched vs untouched reassignment) and event counts.
    - A γ ∈ {0, 0.25, 0.5, 0.75, 1} trade-off, paired against γ = 0.
- **Results** (shipped γ = 0.5):
  - Cross-snapshot HARI is 0.83–0.95, up from 0.34–0.58 at γ = 0, and change concentrates on touched nodes
    (ratios 2.5–24).
  - The new-paper null is as stable, so the persistence comes from the mechanism, not from the data.
  - Robustness to perturbation halves at later snapshots (HARI 0.33 → 0.17 at ≤2026): path dependence.
  - P3 moves from level 0 to levels 1–2.
- **Verified:**
  - 441 tests pass.
  - `validate.py out --config out/run_config.toml` passes on the rebuilt `out/`.
  - All tables in the formal statement are generated from `out/metrics.json` and `out/gamma/gamma.json` by
    script.
- **Not verified / limits:**
  - An independent recomputation is pending; see the next commit.

## Case where the AI was wrong (§6a)

_To be filled in. It must describe one concrete case where the assistant produced wrong
code or a wrong claim, how it was caught, and what was changed. "None" is acceptable
only if it says how the work was checked._

Candidates so far:
- Entry 13: the first validator passed its own tests, but adversarial agents found
  crashes disguised as failures and invalid outputs it accepted. Every finding was
  reproduced on a concrete fixture and fixed, and each became a regression fixture.
- Entry 19: the same version-gating bug reappeared in notebook 02 despite entry 10. It is
  now caught statically by a test.
- Entry 10 (strongest, a real code bug): the assistant fixed a matplotlib API error by
  moving to the newest keyword arguments, testing only in its own environment. That
  broke the notebook on matplotlib 3.7 in the user's environment. It was caught when
  the user ran it, and fixed with a version-tolerant call plus execution checks in
  three environments.
- Entry 7: the `xDeepH` "no node" claim and the `first_seen_year` snapshot
  recommendation, both caught by independent verifier agents and cross-checking.
- Entry 3: the misnamed "internal fraction" formula in Perplexity's primer, found by
  working through the m = n case by hand. Still open: checking entry 2's paper details
  and technical claims.
