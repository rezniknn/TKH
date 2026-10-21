<!-- Project overview, setup and exact reproduction steps (deliverable 1). Explains how 'make all' runs build -> validate -> metrics -> tables. -->
# Multi-resolution semantic abstraction over the TKH

## Setup

Python 3.11 or 3.12 (tested with both; 3.11 is the minimum, for `tomllib`).

```bash
python3.12 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

Equivalent with [uv](https://docs.astral.sh/uv/): `uv venv --python 3.12 .venv && uv pip install --python .venv/bin/python -r requirements.txt`.

Any Python 3.11/3.12 interpreter works in place of `python3.12` (e.g. `python3 -m venv .venv`
if `python3 --version` reports 3.11 or 3.12).

## Reproduce everything (§6a.4)

```bash
make all      # sweep -> build -> validate -> metrics -> tables (about 30 min on 8 cores; offline)
make fast     # the same with fewer null replicates and seeds, into out_fast/ (report.md untouched)
make test     # unit tests and the validator's broken-fixture proof
```

- **What `make all` does.**
  - `sweep`: α grid, selection on E1a half A, ablations, nulls and perturbation runs
    → `out/selection.json` and the git-ignored `out/runs/`.
  - `build`: the selected configuration with LLM labels → `out/<cutoff>/hierarchy.json`,
    `temporal_events.json`, `coarse_hyperedges.json` and `label_inputs.json`.
  - `validate`: `validate.py out/`.
  - `metrics`: E1–E4 for the model, every configuration and every null →
    `out/metrics.json` (schema `schema/metrics.schema.json`) and
    `out/label_judgements.json`.
  - `tables`: `make_tables.py`, which writes every number table of `report.md` and
    `out/tables.md`.
- **LLM calls (labels and the E3 judges) replay from the committed cache
  `data/llm_cache.json`.** A clean checkout needs no model server. `TKH_LLM_MODE` selects
  the mode:
  - `offline` (default): replay; a missing key raises `CacheMiss`.
  - `live`: call the server on a miss.
  - `refresh`: re-query everything; `make refresh-llm` does this.

  Live modes need a local [Ollama](https://ollama.com) server with the models named in
  `[labels]` of the config (`ollama pull qwen2.5:7b-instruct llama3.1:8b gemma2:9b phi4`).

Run the notebooks with this environment's Jupyter (`.venv/bin/jupyter`), or select `.venv` as the kernel in your editor. The pinned versions matter: other environments (e.g. an older Anaconda) may differ.

## Configuration

All input paths, snapshot cutoffs and output directories are set in a TOML config.
The default is [configs/default.toml](configs/default.toml), which points at `data/`.
To run on other inputs, copy it, edit the paths, and select it:

```bash
export TKH_CONFIG=/path/to/my.toml     # used by the notebooks and scripts
```

Relative paths in a config are resolved against the config file's directory.
Only `[inputs] graph` is required. Without `articles`, publication years come
from hyper-edge provenance and titles from article nodes. Scripts also accept
`--config` and per-value overrides (`--graph`, `--articles`, `--cutoffs ...`,
`--out-dir`, `--figures-dir`), which take precedence over the config file.

## T1: data description

```bash
.venv/bin/jupyter nbconvert --to notebook --execute --inplace notebooks/01_describe_graph.ipynb
```

This regenerates `figures/t1_*.png` (or the configured `figures_dir`).

`notebooks/02_semantic_signal.ipynb` asks what semantic information the export's metadata
carries and whether clustering can use it. It covers lexical TF-IDF representations
(`tkh/semantic.py`), tests against ground-truth groups with a type-preserving null
(`tkh/evaluate/groundtruth.py`), and a trial clustering on semantics alone.

Its §5 checks whether paper abstracts can be retrieved from the export's identifiers
(`tkh/abstracts.py`: arXiv API by id, OpenAlex/arXiv title search). The live part is
opt-in, and nothing is stored:

```bash
TKH_ONLINE=1 .venv/bin/jupyter nbconvert --to notebook --execute --inplace notebooks/02_semantic_signal.ipynb
``` The snapshot rule is in `tkh/io.py` and the statistics in `tkh/describe.py`.

## Output validator (§6a)

```bash
.venv/bin/python validate.py out/          # or: make validate
```

The validator checks every configured snapshot's `out/<cutoff>/hierarchy.json` and
`out/temporal_events.json` against `schema/` and the run config:
- **P1 laminarity:** coverage, uniqueness, parent levels, nesting.
- **P2 budgets:** `[hierarchy] budgets` in the config; at least 2 levels are required.
- **Snapshot cutoff:** member ids must exist in that snapshot.
- **Labels:** levels 0 and 1 must have a label and gloss.
- **Event log:** references, snapshot order and arity, plus lineage completeness and
  consistency for P5 (every super-node has exactly one fate per transition).
- **Ids:** one global id namespace (constant level, no rebirth after a gap).

The full rule list is in the `validate.py` docstring. It prints one
`CODE location: message` line per violation. Exit codes: 0 = pass, 1 = violations,
2 = usage or input error, 3 = internal error.

Proof that it bites: `make test`. This runs `tests/test_validate.py` on
`tests/fixtures/`, which holds one valid output and a set of broken mutations
(generated by `tests/make_fixtures.py`). Each mutation must be rejected with exactly
its expected codes. The tests also cover inputs that can't be committed as fixtures
(unreadable files, integer ids, undated input nodes, duplicate cutoffs, internal
errors), a mock built from the full input graph (`tests/mock_output.py`), and
mutations of that mock.

## Stability evaluation (T6)

`tkh/evaluate/stability.py` measures stability in two ways, as T6 asks.

- **Perturbation stability.** Remove 10% of the hyper-edges, stratified by publication
  period (5 seeds), rebuild with the builder that produced the hierarchy, and compute
  ARI against the unperturbed hierarchy per snapshot and level. Reported with a 95%
  t-interval.
- **Cross-snapshot stability.** ARI between consecutive snapshots on the nodes present
  in both, per level. Reported with a 95% interval over half-subsamples of the nodes
  and a permutation p-value against random labels that keep cluster sizes (floor 0.001).

Each ARI is reported with the largest cluster's share of nodes, because a giant cluster
dominates pair-counting ARI. The evaluator takes a `build` function (input hypergraph to
per-snapshot, per-level partitions), so it can be run on any method.

- **Scope.** Perturbation removes edges of the clustering relations only. The literal
  all-edges variant is available with `relations=None` and is labelled as such. All
  measures are computed on concept nodes only.
- **Change localisation (P5).** The reassignment rate of old nodes touched by new
  clustering edges, divided by that of untouched old nodes, with a permutation p-value.
- **References.** A γ = 0 build and a `freeze` build (old assignments fixed; method
  parameter `freeze=true`) are run alongside.

## Null models (T6)

`tkh/evaluate/nulls.py`. The struct, sem and full nulls are rebuilt through the same
pipeline (the struct and full nulls with the real graph's hub sets). The random-labels null
permutes the model's finished tree. All of them are scored with the
same metrics, against the real graph.

| Null | What it keeps | What it destroys |
|---|---|---|
| `shuffle_hypergraph` (struct) | arity and type composition of every edge, each node's degree per period, members[0], hubs, all non-clustering edges | which concept nodes co-occur |
| `semantic_permutation` (sem) | structure; text bijection within type × entry period | which node carries which name |
| full | both of the above | both |
| `permute_hierarchy` (random labels) | the tree, sizes, nesting, temporal structure; permutation within type × entry period × paper-count bin | which node sits in which super-node |

`shuffle_hypergraph` is a Curveball shuffle within each period. At seed 0 it keeps 15% of
the original incidences. Its invariants are asserted on every call.

## Method: SHAC-T (T2, T4)

The formal statement, assumptions and trade-offs are in
[docs/formal_statement.md](docs/formal_statement.md).

- **Procedure.** A constrained greedy agglomeration over the concept nodes, run from the
  finest level (240) to the coarsest (15). Each merge maximises a rank-normalised mix of:
  - a hypergraph-native structural score, the degree-normalised reduction of the λ−1
    connectivity cut on the collapsed incidence (`tkh/coarsen.py`, T4);
  - a name-based semantic score.

  A temporal prior on the previous snapshot's co-membership is added. A size cap keeps
  every budget reachable.
- **Other nodes.** Non-concept nodes are anchored to a concept node. Citations never enter
  the clustering hypergraph. They only anchor `cited_work` nodes, which no metric scores, and
  serve as the held-out ruler of E1a.

```bash
make build                                         # -> out/<cutoff>/hierarchy.json, temporal_events.json,
                                                   #    out/<cutoff>/coarse_hyperedges.json, out/run_info.json
.venv/bin/python scripts/build.py --param alpha=0.25 --param structure=projection --out /tmp/alt
```

Parameters (`alpha`, `gamma`, `rho`, `structure`, `lsa_dim`, `hub_frac`, and `freeze` for the reference variant) live in
`[method]` of the config. Labels at levels 0–1 come from the LLM labeller (`[labels]`);
`--placeholder-labels` gives deterministic stand-ins without an LLM.
