"""Method-independent evaluator: judges a finished hierarchy (the artefacts in out/) against the export.

Contract: modules here, and the tkh/evaluate modules they build on, import nothing from the coarsening
implementation (tkh.coarsen, tkh.hierarchy, tkh.label, tkh.semantic, tkh.temporal, scripts/). Structural
primitives come from tkh.structure. The data contract shared by every method under evaluation: concept-node
scope (tkh.structure.CONCEPT_TYPES, checked against the export schema), a fixed evaluator hub share (configs/
eval.toml [eval] hub_frac), the citation residual filter, and the tkh.io snapshot rule. Method re-runs (null and
perturbed graphs) go through one shell hook, [eval] build_cmd. tests/test_eval_independence.py enforces this.
"""
