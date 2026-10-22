# One-command pipeline (6a.4): 'make all' runs sweep -> build -> validate -> metrics -> tables on a clean checkout,
# offline: the LLM labels and M3 judgements replay from the committed cache data/llm_cache.json.
PYTHON ?= .venv/bin/python
OUT ?= out
REPORT ?= report.md

.PHONY: all fast test fixtures sweep build validate metrics tables figures refresh-llm

all: sweep build validate metrics tables figures

fast:            ## quick end-to-end run into out_fast/ (fewer null replicates and seeds; report.md untouched)
	FAST=1 $(MAKE) all OUT=out_fast REPORT=

test:            ## validator proof (6a.2) and unit tests
	$(PYTHON) -m pytest tests/ -q

fixtures:        ## regenerate tests/fixtures/ from tests/make_fixtures.py
	$(PYTHON) tests/make_fixtures.py

sweep:           ## alpha grid, selection on M1 dev half A, ablations (via build_cmd) -> $(OUT)/selection.json
	$(PYTHON) scripts/sweep.py --out $(OUT)

build:           ## SHAC-T hierarchy (selected parameters) with LLM labels -> $(OUT)/<cutoff>/hierarchy.json, temporal_events.json
	$(PYTHON) scripts/build.py --out $(OUT)

validate:        ## check $(OUT)/ against the run config ($$TKH_CONFIG or configs/default.toml)
	$(PYTHON) validate.py $(OUT)

metrics:         ## M1-M5 for the model (scripts/evaluate.py), variants and the foreign baseline -> $(OUT)/metrics.json
	$(PYTHON) scripts/compute_metrics.py --out $(OUT)

tables:          ## every report table from $(OUT)/metrics.json -> $(OUT)/tables.md (and report.md)
	$(PYTHON) make_tables.py --metrics $(OUT)/metrics.json --out $(OUT)/tables.md --report "$(REPORT)"

figures:         ## optional static view of levels 0-2 across snapshots -> figures/hierarchy_levels.png
	$(PYTHON) scripts/visualize.py --out $(OUT) $(if $(REPORT),,--figures $(OUT)/figures)

refresh-llm:     ## re-query the Ollama models for every label and judgement (needs a running server)
	TKH_LLM_MODE=refresh $(MAKE) build metrics
