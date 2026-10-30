# Pipeline: 'make all' = build -> validate -> metrics -> abstract-coherence -> sweep-summary -> tables -> test, where 'make metrics' =
# coherence -> stability -> faithfulness -> retrieval; each check writes its own section of $(OUT)/metrics.json and can
# also be run on its own; 'make sweep-summary' rewrites its alpha_sweep section from the runs in $(OUT)/sweep/ (offline);
# 'make tables' regenerates every table of docs/report.md, docs/appendix.md (Appendix A) and docs/alpha_sweep.md
# (Appendix B) from $(OUT)/metrics.json only.
# LLM calls replay from data/llm_cache.json (TKH_LLM_MODE=offline, the default); live/refresh need a local Ollama server.
PYTHON ?= .venv/bin/python
OUT ?= out
SEED ?= 0

.PHONY: all test fixtures build validate null metrics sweep-summary tables coherence stability faithfulness retrieval figures sweep abstract-coherence
.NOTPARALLEL:     # the checks read-modify-write the same metrics.json, so never run them concurrently (make -j)

all: build validate metrics abstract-coherence sweep-summary tables test

metrics: coherence stability faithfulness retrieval   ## every evaluation check on $(OUT)/ -> $(OUT)/metrics.json

test:            ## the validator's tests: valid and broken fixtures (6a.2)
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

coherence:       ## held-out coherence check of $(OUT)/ against 99 configuration-null rebuilds and 999 random labels
	$(PYTHON) -m eval coherence --run $(OUT)

stability:       ## perturbation (10% of hyper-edges, 5 seeds) and cross-snapshot stability vs a new-paper null
	$(PYTHON) -m eval stability --run $(OUT)

faithfulness:    ## label faithfulness: held-out NLI judge on every L0-L1 label (LLM answers replay from the cache)
	$(PYTHON) -m eval faithfulness --run $(OUT)

retrieval:       ## T6 extrinsic utility: drill-down agent vs flat search, hit-rate, error rate, inspection, computation (offline, seconds)
	$(PYTHON) -m eval retrieval --run $(OUT)

tables:          ## every table of docs/report.md, docs/appendix.md and docs/alpha_sweep.md from $(OUT)/metrics.json only (no recomputation)
	$(PYTHON) make_tables.py --run $(OUT)
	$(PYTHON) make_tables.py --doc appendix --run $(OUT)
	$(PYTHON) make_tables.py --doc sweep --run $(OUT)

sweep-summary:   ## alpha_sweep section of $(OUT)/metrics.json from the existing runs in $(OUT)/sweep/ (offline, no rebuild)
	if [ -d $(OUT)/sweep ]; then $(PYTHON) -m eval sweep --out $(OUT)/sweep --out-dir $(OUT) --summarise-only; fi

abstract-coherence: ## extra check: phi4-rated closeness of paper abstracts within vs across L0 super-nodes -> eval/extra/ and $(OUT)/metrics.json abstract_coherence (offline from its cache)
	$(PYTHON) -m eval.extra.abstract_coherence --run $(OUT)

figures:         ## static PNGs of $(OUT)/metrics.json -> docs/figures/ (no recomputation)
	$(PYTHON) -m eval.figures --run $(OUT) --out docs/figures

sweep:           ## alpha = 0, 0.25, 0.5, 0.75, 1 (rest at defaults): full run + four checks each -> $(OUT)/sweep/; comparison -> $(OUT)/metrics.json alpha_sweep; tables, figures
	$(PYTHON) -m eval sweep --out $(OUT)/sweep --out-dir $(OUT)
	for d in $(OUT)/sweep/*/; do $(PYTHON) validate.py $$d --config $$d/run_config.toml || exit 1; done
	$(PYTHON) make_tables.py --run $(OUT)
	$(PYTHON) make_tables.py --doc appendix --run $(OUT)
	$(PYTHON) make_tables.py --doc sweep --run $(OUT)
	$(PYTHON) -m eval.figures --run $(OUT) --out docs/figures
