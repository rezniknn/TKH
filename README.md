# Multi-resolution semantic abstraction over the TKH

This repository builds a budgeted, nested, three-level abstraction (L0 coarsest, then L1, then L2) of the TKH
temporal knowledge hypergraph for four cumulative snapshots: ≤2020, ≤2022, ≤2024 and ≤2026. The method is SHAC, a
budgeted semantic–hypergraph agglomeration. The repository also evaluates the result.

- **Final report:** [docs/report.md](docs/report.md).
- **Appendix A:** [docs/appendix.md](docs/appendix.md), with the full definitions and per-metric tables.
- **Appendix B:** [docs/alpha_sweep.md](docs/alpha_sweep.md), the α sweep.
- **AI usage:** [AI_USAGE.md](AI_USAGE.md).

## Repository structure

| Path | Content |
|---|---|
| `docs/report.md` | Final report: formal statement, method and literature, T4 coarsening decision, evaluation, future work |
| `docs/appendix.md`, `docs/alpha_sweep.md` | Appendix A (definitions, resources, full result tables) and Appendix B (α sweep) |
| `docs/figures/` | Figures of the report and its appendices (`make figures`) |
| `notebooks/` | Exploratory and explanatory notebooks (index below) |
| `tkh/` | Hypergraph data structures and the SHAC method: loading and snapshots (`io.py`), structure and semantics (`structure.py`, `semantic.py`), greedy agglomeration (`hierarchy.py`), hyper-edge coarsening (`coarsen.py`), temporal coupling (`temporal.py`), labels (`label.py`, `llm.py`), the T6 drill-down agent (`retrieve.py`), null models (`null.py`), pipeline and CLI (`pipeline.py`, `__main__.py`) |
| `eval/` | Evaluation metrics: held-out coherence (`coherence.py`, `experiments.py`), stability (`stability.py`), label faithfulness (`faithfulness.py`), retrieval utility (`retrieval.py`), α sweep (`sweep.py`), figures; `eval/extra/` holds the extra abstract-based coherence check |
| `out/` | Produced hierarchies, committed: `<cutoff>/hierarchy.json` per snapshot, `temporal_events.json`, `metrics.json` (every evaluation number), the run config and diagnostics, and the five α-sweep runs in `out/sweep/<α>/` ([out/README.md](out/README.md)) |
| `data/` | Assignment inputs (TKH export, article table, T6 questions and gold answers) and the LLM response cache ([data/README.md](data/README.md)) |
| `configs/` | Run configuration `default.toml` and the LLM prompt templates in `configs/prompts/` |
| `validate.py`, `schema/` | Output validator and the JSON schemas it checks against |
| `make_tables.py` | Generates every results table of the report and the appendices from `out/metrics.json` |
| `tests/` | Validator tests on one valid and many deliberately broken outputs |
| `figures/` | Notebook figures |
| `prompts/`, `notes/` | Major AI prompts and research notes referenced by `AI_USAGE.md` |

### Notebooks

| Notebook | What it shows |
|---|---|
| `01_describe_graph.ipynb` | T1 data description: node and relation types, hyper-edge arity, how articles link the graph, growth across snapshots |
| `02_semantic_signal.ipynb` | What semantic information the export's metadata carries; lexical (character n-gram TF-IDF) representations; a trial clustering on semantics alone; a feasibility probe for fetching abstracts |
| `03_structural_signal.ipynb` | The structure of the graph (which nodes and relations link papers, what a coarser level must represent), and design rules derived from it |
| `04_hierarchies.ipynb` | The shipped hierarchies (α = 0.75) taken apart with the method's own code: one merge step by step, level transitions and the temporal prior, super-node records, the hyper-edge coarsening per edge, labels and glosses |
| `05_retrieval_design.ipynb` | Design of the T6 retrieval evaluation: question and gold formats, what the export can answer, the drill-down agent and its flat baseline, the metrics |

All notebooks read `out/` and the LLM cache. None rebuilds anything or calls an LLM.

## Installation

Python 3.11 or 3.12 is required (3.11 is the minimum, for `tomllib`).

```bash
python3.12 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

With [uv](https://docs.astral.sh/uv/):

```bash
uv venv --python 3.12 .venv && uv pip install --python .venv/bin/python -r requirements.txt
```

Run the notebooks with `.venv/bin/jupyter`, or select `.venv` as the kernel. `requirements.txt` pins the versions;
another environment, such as an older Anaconda, may give different results.

### LLM: open-source models with an offline cache

Two open-source models run locally through [Ollama](https://ollama.com):

- **qwen2.5:7b-instruct** writes the L0–L1 labels and glosses.
- **phi4**, from a different model family, judges label faithfulness and rates paper abstracts for the extra check.

Every answer is stored in a committed cache, keyed by model digest, prompt and decoding options:

- `data/llm_cache.json` holds the labels and the faithfulness judgements;
- `eval/extra/llm_cache.json` holds the abstract ratings.

Decoding is deterministic: temperature 0 and a fixed seed. The default mode is offline, so **no Ollama installation
and no network access are needed to reproduce the report**. An offline run never contacts a server. A prompt
missing from the cache is an error (`CacheMiss`), never a silent fallback.

Ollama is needed only when a run creates prompts the cache does not hold, for example new parameter values, new
data or edited prompt templates. To install it:

```bash
# macOS: brew install ollama, or download the app from https://ollama.com/download
# Linux:
curl -fsSL https://ollama.com/install.sh | sh

ollama serve &                        # local server on http://localhost:11434 ([labels] endpoint)
ollama pull qwen2.5:7b-instruct       # labeller
ollama pull phi4                      # faithfulness judge and abstract rater
```

Then select a mode with `TKH_LLM_MODE`, which overrides `[labels] mode`:

- `live` answers a cache miss from the server and stores the answer;
- `refresh` asks the server again for every prompt and overwrites the cache;
- `offline` is the default.

## Reproducing the report

Every number in the report and its appendices comes from `out/metrics.json`. The full chain, from inputs to tables,
is:

```bash
make all
```

It runs these steps in order:

1. `build`: SHAC hierarchies for every snapshot to `out/`. This takes about 13 minutes on 8 cores.
2. `validate`: checks `out/` against the schemas and its own run config (P1 laminarity, P2 budgets, cutoffs,
   labels, event log).
3. `metrics`, which runs four checks, each writing its own section of `out/metrics.json`:
   - `coherence`: held-out citation coherence against 99 configuration-null rebuilds and 999 random labellings;
   - `stability`: perturbation (5 seeds) and cross-snapshot stability against a new-paper null;
   - `faithfulness`: label over-claim against held-out evidence;
   - `retrieval`: T6 drill-down against flat search.
4. `abstract-coherence`: the extra abstract-based check.
5. `sweep-summary`: the α-sweep comparison, computed from the committed runs in `out/sweep/`.
6. `tables`: regenerates every table of `docs/report.md` and both appendices.
7. `test`: the validator tests.

The LLM steps replay from the cache, so the result should match the committed `out/`. Check that with
`git status` or `git diff --stat out/ docs/`.

**Shorter checks** that need no rebuild:

```bash
make validate                                  # validator on the committed out/
make test                                      # validator rejects every broken fixture
make tables                                    # regenerate every table from out/metrics.json; git diff docs/ shows any change
make retrieval                                 # recompute the T6 section from out/ (seconds)
```

**The α sweep (Appendix B)** is not rebuilt by `make all`, which only summarises the committed runs. To rebuild it:

```bash
make sweep    # α = 0, 0.25, 0.5, 0.75, 1, other parameters at defaults: full build + four checks per α -> out/sweep/<α>/
```

`out/` (the default α = 0.75) is identical to `out/sweep/0.75/`.

**Notebooks:** re-execute any of them in place, for example:

```bash
.venv/bin/jupyter nbconvert --to notebook --execute --inplace notebooks/04_hierarchies.ipynb
```

Notebook 02's abstract-retrieval probe makes network calls only with `TKH_ONLINE=1`.

## Changing parameters

All settings live in a TOML config. The default is [configs/default.toml](configs/default.toml), whose comments
document every key.

| Section | Keys |
|---|---|
| `[inputs]` | `graph` (required), `articles` (optional) |
| `[snapshots]` | `cutoffs`: at least 3 years |
| `[hierarchy]` | `budgets`: maximum super-nodes per level, L0 first, non-decreasing |
| `[method]` | `alpha` (semantic vs structural weight, default 0.75), `gamma` (temporal prior, 0.5), `rho` (size cap, 2), `edge_weight`, `hub_frac` (0.2), `lsa_dim` (100); unknown keys are an error |
| `[labels]` | labeller and judge models, Ollama endpoint, cache path, LLM mode, evidence split; `labeller = "placeholder"` skips the LLM |
| `[outputs]` | `out_dir`, `figures_dir` |

There are three ways to change them:

```bash
# 1. a copy of the config, used by every script and notebook
cp configs/default.toml configs/my.toml        # edit; relative paths resolve against the file's directory
export TKH_CONFIG=configs/my.toml

# 2. command-line overrides of one build (they take precedence over the config)
make build PARAMS="alpha=0.5 rho=4"            # [method] parameters -> out/
.venv/bin/python -m tkh build --out out_alt --budgets 10 40 160 --cutoffs 2021 2023 2026 --param hub_frac=0.3
.venv/bin/python validate.py out_alt --config out_alt/run_config.toml

# 3. the checks on any run directory
make metrics OUT=out_alt
```

- **Overwriting `out/`.** `make build` writes to `out/`, which holds the committed results, so a parameter
  experiment is better sent elsewhere with `--out`.
- **Run config.** Every run writes its resolved configuration to `<run>/run_config.toml`. The validator and the
  checks read it, so a run is always checked against what built it.
- **LLM cache.** New parameter values change the super-nodes and therefore the label prompts. Run them with
  `TKH_LLM_MODE=live` and Ollama, or set `labeller = "placeholder"` in a config copy.
  - The cache already covers the five α-sweep values with the other parameters at their defaults.
- **Null model.** `make null SEED=3` builds and validates one configuration-null run in `out_null/3/`.
