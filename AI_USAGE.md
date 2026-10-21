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

## Case where the AI was wrong (§6a)

_To be filled in. It must describe one concrete case where the assistant produced wrong
code or a wrong claim, how it was caught, and what was changed. "None" is acceptable
only if it says how the work was checked._

Candidates so far:
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
