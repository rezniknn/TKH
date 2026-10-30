# AI usage

This is a summary of how AI assistants were used for each part of the assignment. Supporting material:

- **[prompts/](prompts/):** the major prompts per section, most with explicit completion or verification criteria.
- **[notes/](notes/):** the research outputs used for the literature review and the formal statement.

## Tools

| Tool | Used for |
|---|---|
| Perplexity Deep Research, academic connector | Literature search, hypergraph-clustering review, null-model survey (`notes/*_perplexity.md`) |
| Claude Code (Claude Opus 5.5, VS Code extension) | Data investigation, code, notebooks, evaluation, report and README. Larger tasks ran as multi-agent workflows that pair investigators with independent verifiers and adversarial reviewers. |
| Codex (GPT-6.1-Sol) | Independent evaluation of the repository and the final report: the feedback points on the report came from this review. |
| qwen2.5:7b-instruct and phi4 via Ollama | Part of the method, not assistants: qwen2.5 writes the L0–L1 labels, and phi4 (a different family) judges their faithfulness and rates abstracts. Every answer is cached (`data/llm_cache.json` for labels and judging, `eval/extra/llm_cache.json` for abstract ratings) and replays offline. |

## By stage

**Research.**
- **Literature.** Perplexity produced the shortlist that became the four positioning papers [1–4], a clustering
  review and a null-model survey. Its outputs were treated as reading lists.
  - Three of the four positioning papers (h-Louvain, DynHAC, HyperEF 2.0) were read against their arXiv text and
    code (`notes/prior_work_comparison.md`).
  - Citations that could not be confirmed were not used.
  - The output gave no authors for HyperEF 2.0. They, and the exact venue (ICCAD 2025), were completed from the
    arXiv paper.
- **Data.** Five investigator agents described `data/`, and five verifier agents recomputed every headline number
  with fresh code. Of 79 claims, 57 were confirmed, 22 corrected and none refuted. One recommendation was rejected:
  slicing snapshots by `first_seen_year`, a field that contradicts its documented meaning for 127 nodes.

**Formal statement and method (T1–T5).**
- **T1.** The data description comes from `tkh/describe.py` and notebook 01, with its numbers checked against the
  verified investigation.
- **SHAC (T2, T4).** The first design, SHAC-T, was replaced at the user's request by a simpler rewrite (prompt
  `prompts/T2_T4_T6c.md`). The rewrite dropped the temporal prior, the projection variant and the null hooks, and
  made the structural rank positive-only.
  - The T4 collapse rule is implemented in `tkh/coarsen.py`.
  - Its description was corrected twice to match the code (internal, partial and uncollapsed classes, with
    multi-way as a flag).
- **Temporal coupling, labels and retrieval.** These were built from `prompts/T3_T6s.md`, `prompts/T5_T6lf.md` and
  `prompts/T6e.md`.
- **Formal statement.** It was audited twice against the code, to keep it describing what the code does.

**Evaluation (T6).** These were the non-trivial design contributions, each proposed by the assistant and then
challenged by review agents:
- the held-out coherence ruler (citation coupling of concept-disjoint papers, a name-leak filter, period strata,
  two nulls);
- a new-paper null for cross-snapshot stability;
- held-out-evidence faithfulness with a judge from another model family;
- a five-value α sweep with a rule fixed before the results were read;
- an extra abstract-based coherence check (`prompts/Extra_abstracts.md`).

**Deliverables.**
- **Validator.** `validate.py`, with 48 broken fixtures.
- **Tables.** `make_tables.py` regenerates every table from `metrics.json`.
- **Report.** The report (`prompts/Report.md`) was cut from about 10,000 words to about 3,300 (about 2,600 of
  prose), with appendices, after Codex's evaluation.

**Independent evaluation by a second model.** Codex (GPT-6.1-Sol) evaluated the repository and the final report
independently of Claude Code. Its feedback points were checked against the code and either addressed or explicitly
scoped out. They included:
- the report exceeded the 3–5-page brief;
- Table 1 overstated temporal stability as guaranteed;
- the complexity statement and the h-Louvain description were incomplete;
- claim hit-rates in the retrieval evaluation were source-associated rather than content-checked;
- the faithfulness code did not apply its documented fallback.

## How AI output was verified

- **Recomputation, not recall.** Numbers in notes and reports come from scripts run on the data. For example, the
  T1 figures matched the verified investigation values.
- **Independent adversarial review.** Substantive changes were reviewed by agents told to refute them, and each
  finding was verified separately before it was fixed. These reviews confirmed 5–21 real findings each.
- **Cross-model review.** Codex's evaluation gave an independent second opinion from a different model family. Each
  of its points was verified against the code before it was acted on.
- **Generated tables.** `make_tables.py` rewrites every table from `metrics.json`, and `validate.py` must reject every
  broken fixture (`make test`).
- **Determinism and replay.** A rebuild from the shipped config is byte-identical to `out/`. LLM steps replay from
  the cache with zero live calls.
- **Rubric scoring.** A fresh agent scored the final report against the brief's §7 criteria, and its main finding
  was adopted.

## Where AI was wrong or led to an undesired result

**The main case (§6a): the α-sweep decision rule.**
- **What went wrong.** The assistant fixed the rule for choosing α before the results were read. Its stability guard
  excluded any variant distinguishably less robust than the *most* robust variant. Applied to the results, the rule
  recommended α = 1, a names-only build with no robust coherence cell.
- **Why.** Removing hyper-edges barely affects a grouping made from names (only the temporal prior's stable set
  depends on them). The names-only build was therefore robust for a reason unrelated to group quality, and its
  interval excluded every other variant.
- **How it was caught.** The assistant checked the recommendation against the per-criterion tables and the report's
  own stability reading, found the contradiction, and raised it with the user before changing anything. A 21-agent
  review then independently recomputed all eight sweep tables.
- **What changed.** At the user's choice, the guards now compare each variant with the pre-sweep default, which
  gives α = 0.75. The revision is disclosed in Appendix B §9.

**Other cases, each caught and then corrected or set aside:**

- **Code that broke the user's environment.** A matplotlib fix used keywords that exist only in the newest version
  and was tested only in the assistant's own venv. It broke the notebook on matplotlib 3.7, and the same bug came back
  in a second notebook. The fixes were then checked in the user's environment as well as the assistant's, and the
  call is now version-tolerant.
- **A validator that passed its own tests but was wrong.** The first validator crashed on several inputs and
  accepted invalid outputs (duplicate cutoffs, contradictory event logs). Adversarial agents found these, and each
  became a regression fixture or test.
- **Subtle statistical bugs:**
  - rank distributions built on raw floats let round-off change a hierarchy;
  - a stability null that kept the stable set identical, so "the null is just as stable" was built in;
  - a key collision that merged L0 and L1 records and inflated a null's over-claim;
  - bootstrap with replacement that biased ARI upwards.
- **Results that did not hold.** Ten rounds of prompt iteration cut the over-claim rate on 15 development labels
  but did not generalise to held-out labels: a selection effect, which was reported as such. The first label judge
  failed its validity gate.
- **Code that disagreed with the documentation.** The faithfulness code judged only the surviving claims, while the
  report said a failed decomposition is judged as label and gloss. Codex's evaluation caught it. The fix raised the
  over-claim rate from 0.60 to 0.63.
- **Overstated prose.**
  - The report's abstract claimed coherence without saying that every lift's bootstrap interval includes chance.
  - A notebook claim was backwards.
  - The extra abstract-based check had spread into the report's headline before the user confined it to its own
    section.
- **Perplexity outputs, set aside rather than adopted:**
  - citation markers could not be traced to papers;
  - a plain configuration null would be trivially easy to beat on this star-shaped data.
- **Undesired direction.** A revision answering reader questions grew the report from about 3,200 to 5,900 words.
  The length had to be cut back to the 3–5-page brief later.
