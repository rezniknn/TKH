# Pipeline: 'make build' writes out/, 'make validate' checks it; 'make test' runs the unit tests and the validator's broken fixtures.
PYTHON ?= .venv/bin/python
OUT ?= out

.PHONY: test fixtures build validate

test:            ## validator proof (6a.2) and unit tests
	$(PYTHON) -m pytest tests/ -q

fixtures:        ## regenerate tests/fixtures/ from tests/make_fixtures.py
	$(PYTHON) tests/make_fixtures.py

build:           ## SHAC-T hierarchy for every snapshot -> $(OUT)/ (parameters: [method] in the config)
	$(PYTHON) scripts/build.py --out $(OUT)

validate:        ## check $(OUT)/ against the run config ($$TKH_CONFIG or configs/default.toml)
	$(PYTHON) validate.py $(OUT)
