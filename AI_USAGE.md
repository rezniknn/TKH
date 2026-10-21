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
- A digest is kept outside the repo, as working notes. The first paste of the output
  was cut off at the message limit; the full report was then supplied as an
  attachment.
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

## Case where the AI was wrong (§6a)

_To be filled in. It must describe one concrete case where the assistant produced wrong
code or a wrong claim, how it was caught, and what was changed. "None" is acceptable
only if it says how the work was checked._

Candidates so far:
- Entry 13: the first validator passed its own tests, but adversarial agents found
  crashes disguised as failures and invalid outputs it accepted. Every finding was
  reproduced on a concrete fixture and fixed, and each became a regression fixture.
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
