<!-- Generated deliverables, produced by 'make all': <snapshot>/hierarchy.json and <snapshot>/coarse_hyperedges.json per snapshot, temporal_events.json, run_config.toml (resolved inputs and parameters), run_info.json (diagnostics), metrics.json (sections coherence, stability, faithfulness, retrieval, abstract_coherence from 'make abstract-coherence', and alpha_sweep from 'make sweep-summary' over the committed sweep/ runs), faithfulness_judgements.json (per-claim label faithfulness judgements), retrieval_answers.json (T6 retrieval answers, drill-down and flat, with the resolved gold per question); 'make sweep' rebuilds the variant runs in sweep/<alpha>/. -->

The top-level run is built with the configured default α = 0.75, the variant recommended by the α sweep, and is
identical to `sweep/0.75/`. `sweep/` holds all five α variants; `gamma/` and `label_dev/` predate the sweep and were
built at α = 0.5 (the report cites neither).
