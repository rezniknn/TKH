# Prompts

Plain-text templates with `{placeholders}`; literal braces are written `{{ }}`. They are rendered by `tkh.llm.render`, and every rendered prompt is a key of the response cache `data/llm_cache.json`, so editing a template invalidates its cached answers.

| File | Used by | Model (`[labels]`) | Inputs | Output (JSON) |
|---|---|---|---|---|
| `labeller.txt` | `tkh/label.py`, `LLMLabeller` (T5) | `labeller_model` | `cutoff`, `evidence`: the **seen** half of the super-node's evidence lines | `{"label", "gloss"}` |
| `claims_split.txt` | `eval/labels.py`, step 1 (T6) | `judge_model` | `label`, `gloss` | `{"claims": [...]}` |
| `claim_entail.txt` | `eval/labels.py`, step 2 (T6) | `judge_model` | `cutoff`, `evidence`: the **held-out** half, `claim` | `{"verdict": "supported" or "unsupported", "quote"}` |

**Evidence lines.** These are built by `tkh.label.evidence`, and their sources all lie inside the snapshot:
- member concepts, as `name [type]` with aliases;
- the clustering relations of incident edges;
- `evaluated_on` results;
- claim sentences;
- future-work topics;
- paper titles.

Cited works are excluded, because they are the coherence ruler. Authors are excluded too.

**The 50/50 split.** Each super-node's evidence is split into two halves, seeded and stratified by kind (`split_evidence`). The labeller sees only the seen half; the judge sees only the held-out half.

**The judge must quote.** A claim counts as supported only if the quoted line is one of the held-out lines.

**Model families.** The labeller and the judge must come from different model families. The defaults are qwen2.5:7b-instruct (Alibaba) and phi4 (Microsoft).
