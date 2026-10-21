# One-command pipeline (6a.4): 'make all' runs build -> validate -> metrics -> tables on a clean checkout.
PYTHON ?= .venv/bin/python
OUT ?= out

.PHONY: test fixtures validate

test:            ## validator proof (6a.2) and unit tests
	$(PYTHON) -m pytest tests/ -q

fixtures:        ## regenerate tests/fixtures/ from tests/make_fixtures.py
	$(PYTHON) tests/make_fixtures.py

validate:        ## check $(OUT)/ against the run config ($$TKH_CONFIG or configs/default.toml)
	$(PYTHON) validate.py $(OUT)
