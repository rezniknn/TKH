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

## Case where the AI was wrong (§6a)

_To be filled in. It must describe one concrete case where the assistant produced wrong
code or a wrong claim, how it was caught, and what was changed. "None" is acceptable
only if it says how the work was checked._

Candidates so far:
- Entry 3: the misnamed "internal fraction" formula in Perplexity's primer, found by
  working through the m = n case by hand. Still open: checking entry 2's paper details
  and technical claims.
