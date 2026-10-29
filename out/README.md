<!-- Generated deliverables, produced by 'make all': <snapshot>/hierarchy.json and <snapshot>/coarse_hyperedges.json per snapshot, temporal_events.json, run_config.toml (resolved inputs and parameters), run_info.json (diagnostics), metrics.json (sections coherence, stability, faithfulness, retrieval), faithfulness_judgements.json (per-claim label faithfulness judgements), retrieval_answers.json (T6 retrieval answers, drill-down and flat, with the resolved gold per question); 'make sweep' adds sweep.json. -->

The top-level run is built with the configured default α = 0.75, the variant recommended by the α sweep, and is
identical to `sweep/0.75/`. `sweep/` holds all five α variants; `gamma/` and `label_dev/` predate the sweep and were
built at α = 0.5 (the report cites neither).
