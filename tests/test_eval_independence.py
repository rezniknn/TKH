"""The evaluator must not depend on the coarsening implementation (method independence, configs/eval.toml)."""

from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parent.parent
METHOD = ("tkh.coarsen", "tkh.hierarchy", "tkh.label", "tkh.semantic", "tkh.temporal")


def test_evaluator_imports_no_method_module():
    code = ("import sys, importlib.util; sys.path.insert(0, '.'); "
            "spec = importlib.util.spec_from_file_location('ev', 'scripts/evaluate.py'); "
            "m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m); "
            "import tkh.evalkit.entailment, tkh.evalkit.queries, tkh.evalkit.exports, tkh.evalkit.runner, validate; "
            f"bad = [k for k in sys.modules if k in {METHOD!r} or k.startswith('scripts')]; print(bad)")
    out = subprocess.run([sys.executable, "-c", code], cwd=ROOT, capture_output=True, text=True, check=True).stdout.strip()
    assert out == "[]", out
