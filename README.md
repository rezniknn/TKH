<!-- Project overview, setup and exact reproduction steps (deliverable 1). Explains how 'make all' runs build -> validate -> metrics -> tables. -->
# Multi-resolution semantic abstraction over the TKH

## Setup

Python 3.12.

```bash
python3.12 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

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

This regenerates `figures/t1_*.png` (or the configured `figures_dir`). The snapshot rule is in `tkh/io.py` and the statistics in `tkh/describe.py`.
