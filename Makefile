# Pipeline: 'make all' = build -> validate -> p3 (held-out P3 check vs nulls, writes $(OUT)/metrics.json) -> test.
PYTHON ?= .venv/bin/python
OUT ?= out
SEED ?= 0

.PHONY: all test fixtures build validate null p3 sweep

all: build validate p3 test

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
	$(PYTHON) -m tkh p3 --run $(OUT)

sweep:           ## configuration grid, one-SE selection on cited-work halves -> $(OUT)/sweep.json (~6 min on 8 cores)
	$(PYTHON) -m tkh sweep --out $(OUT)/sweep.json
