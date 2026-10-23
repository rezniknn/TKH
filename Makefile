# Pipeline: 'make all' = build -> validate -> p3 (coherence) -> stability -> test; both checks write $(OUT)/metrics.json.
PYTHON ?= .venv/bin/python
OUT ?= out
SEED ?= 0

.PHONY: all test fixtures build validate null p3 stability gamma sweep

all: build validate p3 stability test

test:            ## unit tests and the validator's broken fixtures (6a.2)
	$(PYTHON) -m pytest tests/ -q -p no:cacheprovider

fixtures:        ## regenerate tests/fixtures/ from tests/make_fixtures.py
	$(PYTHON) tests/make_fixtures.py

build:           ## SHAC hierarchy for every snapshot -> $(OUT)/ ([method] in the config; override with PARAMS="alpha=0.25 ...")
	$(PYTHON) -m tkh build --out $(OUT) $(if $(PARAMS),--param $(PARAMS))

validate:        ## check $(OUT)/ against its own resolved run config
	$(PYTHON) validate.py $(OUT) --config $(OUT)/run_config.toml

null:            ## one configuration-null export and run -> out_null/$(SEED)/, validated against its own graph
	$(PYTHON) -m tkh null --seed $(SEED) --out out_null/$(SEED) $(if $(PARAMS),--param $(PARAMS))
	$(PYTHON) validate.py out_null/$(SEED) --config out_null/$(SEED)/run_config.toml

p3:              ## held-out P3 check of $(OUT)/ against 99 configuration-null rebuilds and 999 random labels
	$(PYTHON) -m eval p3 --run $(OUT)

stability:       ## perturbation (10% of hyper-edges, 5 seeds) and cross-snapshot stability vs a new-paper null
	$(PYTHON) -m eval stability --run $(OUT)

gamma:           ## temporal-prior variants gamma = 0..1: stability and coherence, paired vs gamma = 0 -> $(OUT)/gamma/gamma.json
	$(PYTHON) -m eval gamma --out $(OUT)/gamma

sweep:           ## configuration grid, one-SE selection on cited-work halves -> $(OUT)/sweep.json (~6 min on 8 cores)
	$(PYTHON) -m eval sweep --out $(OUT)/sweep.json
