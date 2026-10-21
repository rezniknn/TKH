<!-- Project overview, setup and exact reproduction steps (deliverable 1). Explains how 'make all' runs build -> validate -> metrics -> tables. -->
# Multi-resolution semantic abstraction over the TKH

## Setup

Python 3.12.

```bash
python3.12 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

## T1: data description

```bash
.venv/bin/jupyter nbconvert --to notebook --execute --inplace notebooks/01_describe_graph.ipynb
```

This regenerates `figures/t1_*.png`. The snapshot rule is in `tkh/io.py` and the statistics in `tkh/describe.py`.
