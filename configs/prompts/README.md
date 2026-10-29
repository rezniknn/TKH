# Prompts

Plain-text templates with `{placeholders}`; literal braces are written `{{ }}`. They are rendered by `tkh.llm.render`, and every rendered prompt is a key of the response cache `data/llm_cache.json`, so editing a template invalidates its cached answers.

| File | Used by | Model (`[labels]`) | Inputs | Output (JSON) |
|---|---|---|---|---|
| `labeller.txt` | `tkh/label.py`, `LLMLabeller` (T5) | `labeller_model` | `cutoff`, `evidence`: the **seen** half of the super-node's evidence lines, `contrast`: top concept names of the K same-level groups sharing the most clustering edges (`[labels] contrast = K`; 0 = off) | `{"label", "gloss"}` |
| `claims_split.txt` | `eval/faithfulness.py`, step 1 (T6) | `judge_model` | `label`, `gloss` | `{"claims": [...]}` |
| `claim_entail.txt` | `eval/faithfulness.py`, step 2 (T6) | `judge_model` | `cutoff`, `evidence`: the **held-out** half, `claim` | `{"line": <number>, "verdict": "supported" or "unsupported"}` |

**Evidence lines.** These are built by `tkh.label.Evidence.items` (and split by `tkh.label.split_evidence`), and their sources all lie inside the snapshot:
- member concepts, as `name [type]` with aliases;
- the clustering relations of incident edges;
- `evaluated_on` results;
- claim sentences;
- future-work topics;
- paper titles.

Cited works are excluded, because they are the coherence ruler. Authors are excluded too.

**The 50/50 split.** Each super-node's evidence is split into two halves, seeded and stratified by kind (`split_evidence`). The labeller sees only the seen half; the judge sees only the held-out half.

**The judge must cite a line.** A claim counts as supported only if the cited line number is one of the held-out lines.

**Model families.** The labeller and the judge must come from different model families. The defaults are qwen2.5:7b-instruct (Alibaba) and phi4 (Microsoft).
