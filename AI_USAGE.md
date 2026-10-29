# AI usage

This is a summary of how AI assistants were used for each part of the assignment. The detailed sources are:

- **[AI_USAGE_detailed.md](AI_USAGE_detailed.md):** an ordered log of 59 entries. Each entry gives the prompt, what
  was accepted or changed, and what was verified.
- **[prompts/](prompts/):** the major prompts per section, each with its own verification criteria.
- **[notes/](notes/):** the research outputs used for the literature review and the formal statement.

Entry numbers below (#n) refer to the log.

## Tools

| Tool | Used for |
|---|---|
| Perplexity Deep Research, academic connector | Literature search, concept primer, hypergraph-clustering review, null-model survey (`notes/*_perplexity.md`) |
| Claude Code (Claude Opus 5.5, VS Code extension) | Data investigation, code, notebooks, evaluation, report and README. Larger tasks ran as multi-agent workflows that pair investigators with independent verifiers and adversarial reviewers. |
| qwen2.5:7b-instruct and phi4 via Ollama | Part of the method, not assistants: qwen2.5 writes the L0–L1 labels, and phi4 (a different family) judges their faithfulness and rates abstracts. Every answer is cached (`data/llm_cache.json` for labels and judging, `eval/extra/llm_cache.json` for abstract ratings) and replays offline. |

## By stage

**Research.**
- **Literature.** Perplexity produced the shortlist that became the four positioning papers [1–4] (#2), a
  clustering review (#12) and a null-model survey (#15). Its outputs were treated as reading lists.
  - Three of the four positioning papers (h-Louvain, DynHAC, HyperEF 2.0) were read against their arXiv text and
    code (`notes/prior_work_comparison.md`).
  - Citations that could not be confirmed (#12 lists them) were not used.
  - The output gave no authors for HyperEF 2.0 (#2). They, and the exact venue (ICCAD 2025), were completed from the
    arXiv paper.
  - The h-Louvain description was later re-checked against its arXiv text, because a reviewer found it imprecise
    (#57).
- **Data.** Five investigator agents described `data/`, and five verifier agents recomputed every headline number
  with fresh code (#7, `notes/data_investigation.md`). Of 79 claims, 57 were confirmed, 22 corrected and none
  refuted. One recommendation was rejected: slicing snapshots by `first_seen_year`, a field that contradicts its
  documented meaning for 127 nodes.

**Formal statement and method (T2–T5).**
- **T1.** The data description came from `tkh/describe.py` and notebook 01 (#8, #11, #14), with its numbers checked
  against the verified investigation.
- **SHAC (T2, T4).** The first design, SHAC-T (#21), was replaced at the user's request by a simpler rewrite (#22,
  prompt `prompts/T2_T4_T6c.md`). The rewrite dropped the temporal prior, the projection variant and the null hooks,
  and made the structural rank positive-only. The T4 collapse rule was implemented in `tkh/coarsen.py`, and its
  description was corrected twice to match the code (internal, partial and uncollapsed classes, with multi-way as a
  flag) (#26, #45).
- **Temporal coupling, labels and retrieval.** These were built from `prompts/T3_T6s.md`, `prompts/T5_T6lf.md` and
  `prompts/T6e.md` (#27, #29, #33).
- **Formal statement.** It was audited twice against the code (#26, #44) to keep it describing what the code does.

**Evaluation (T6).** These were the non-trivial design contributions, each proposed by the assistant and then
challenged by review agents:
- the held-out coherence ruler (citation coupling of concept-disjoint papers, a name-leak filter, period strata,
  two nulls) (#22–23);
- a new-paper null for cross-snapshot stability (#27);
- held-out-evidence faithfulness with a judge from another model family (#29);
- a five-value α sweep with a rule fixed before the results were read (#48);
- an extra abstract-based coherence check (#54, `prompts/Extra_abstracts.md`).

**Deliverables.**
- **Validator.** `validate.py` and 48 broken fixtures (#13 created 47; one was added later).
- **Tables.** `make_tables.py` regenerates every table from `metrics.json`, and every hand-written result claim in
  the report carries a tag whose predicate is re-checked on each run (#46, #52).
- **Report.** The report (#45, #57; `prompts/Report.md`) was cut from about 10,000 to about 2,500 words of prose,
  with appendices, after reviewer feedback.

## How AI output was verified

- **Recomputation, not recall.** Numbers in notes and reports come from scripts run on the data. For example, the
  T1 figures matched the verified investigation values (#8).
- **Independent adversarial review.** Substantive changes were reviewed by agents told to refute them, and each
  finding was verified separately before it was fixed (#13, #38, #40, #42, #46, #48, #52, #53, #56, #57).
  These reviews confirmed 5–21 real findings each.
- **Machine-checked claims.** `make_tables.py --check` fails if a table is stale or a tagged sentence is false on
  `metrics.json`. `validate.py` must reject every broken fixture (`make test`).
- **Determinism and replay.** A rebuild from the shipped config is byte-identical to `out/`. LLM steps replay from
  the cache with zero live calls.
- **Independent rubric scoring.** A fresh agent scored the final report against the brief's §7 criteria, and its
  main finding was adopted (#57).

## Where AI was wrong or led to an undesired result

**The main case (§6a): the α-sweep decision rule (#48).**
- **What went wrong.** The assistant fixed the rule for choosing α before the results were read. Its stability guard
  excluded any variant distinguishably less robust than the *most* robust variant. Applied to the results, the rule
  recommended α = 1, a names-only build with no robust coherence cell.
- **Why.** Removing hyper-edges barely affects a grouping made from names (only the temporal prior's stable set
  depends on them). The names-only build was therefore robust for a reason unrelated to group quality, and its
  interval excluded every other variant.
- **How it was caught.** The assistant checked the recommendation against the per-criterion tables and the report's
  own stability reading, found the contradiction, and raised it with the user before changing anything. The
  same entry's 21-agent review independently recomputed all eight sweep tables.
- **What changed.** At the user's choice, the guards now compare each variant with the pre-sweep default, which gives α = 0.75. The
  revision is disclosed in Appendix B §9. The checked claim `original_rule` recomputes the original rule's outcome on
  every `make tables`.

**Other cases, each caught and then corrected or set aside:**

- **Code that broke the user's environment (#10, #19).** A matplotlib fix used keywords that exist only in the newest
  version and was tested only in the assistant's own venv. It broke the notebook on matplotlib 3.7, and the same bug
  came back in a second notebook. The fixes were checked in the user's environment as well as the assistant's (three
  environments in #10, two in #19), and the call is now version-tolerant.
- **A validator that passed its own tests but was wrong (#13).** The first validator crashed on several inputs and
  accepted invalid outputs (duplicate cutoffs, contradictory event logs). Adversarial agents found these, and each
  became a regression fixture or test.
- **Subtle statistical bugs:**
  - rank distributions built on raw floats let round-off change a hierarchy (#22);
  - a stability null that kept the stable set identical, so "the null is just as stable" was built in (#27);
  - a key collision that merged L0 and L1 records and inflated a null's over-claim (#32);
  - bootstrap with replacement that biased ARI upwards (#17).
- **Results that did not hold.** Ten rounds of prompt iteration cut the over-claim rate on 15 development labels
  but did not generalise to held-out labels: a selection effect, which was reported as such (#30). The first
  label judge failed its validity gate (#29).
- **Code that disagreed with the documentation.** The faithfulness code judged only the surviving claims, while the
  report said a failed decomposition is judged as label and gloss. External review feedback, relayed by the user,
  caught it. The fix raised the over-claim
  rate from 0.60 to 0.63 (#55).
- **Overstated prose.**
  - The report's abstract claimed coherence without saying that every lift's bootstrap interval includes chance
    (#45, again in #57).
  - A notebook claim was backwards (#53).
  - The extra abstract-based check had spread into the report's headline before the user confined it to its own
    section (#58).
- **Perplexity outputs, set aside rather than adopted:**
  - field and relation names were invented, because it never saw the data (#3);
  - a misnamed collapse metric: a fully collapsed arity-4 edge scores 0.75, not 1 (#3);
  - citation markers could not be traced to papers (#15);
  - a plain configuration null that would be trivially easy to beat on this star-shaped data (#15).
- **Undesired direction.** A revision answering reader questions grew the report from about 3,200 to 5,900 words
  (#47). The length had to be cut back to the 3–5-page brief later (#57).
