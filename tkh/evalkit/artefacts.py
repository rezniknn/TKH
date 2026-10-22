"""Load a run directory in the artefact format (out/<cutoff>/hierarchy.json, temporal_events.json, label_inputs.json)."""

from pathlib import Path
import json

from tkh.structure import CONCEPT_TYPES


class Run:
    def __init__(self, out_dir, cutoffs, tkh=None):
        self.dir = Path(out_dir)
        self.cutoffs = list(cutoffs)
        self.hier = {c: json.loads((self.dir / str(c) / "hierarchy.json").read_text()) for c in self.cutoffs}
        self.levels = max(h["levels"] for h in self.hier.values())
        self.budgets = self.hier[self.cutoffs[-1]]["budgets"]
        self.parts = {c: [{s["id"]: set(s["member_ids"]) for s in h["supernodes"] if s["level"] == k}
                          for k in range(h["levels"])] for c, h in self.hier.items()}
        ev = self.dir / "temporal_events.json"
        self.events = json.loads(ev.read_text())["events"] if ev.exists() else []
        self.label_inputs = {}
        for c in self.cutoffs:
            p = self.dir / str(c) / "label_inputs.json"
            if p.exists():
                self.label_inputs[c] = json.loads(p.read_text())
        self.tkh = tkh

    def concept_parts(self, tkh=None):
        """Partitions restricted to concept nodes (the evaluation scope; empty groups dropped)."""
        t = (tkh or self.tkh).nodes["type"]
        out = {}
        for c, levels in self.parts.items():
            out[c] = [{g: {v for v in m if t.at[v] in CONCEPT_TYPES} for g, m in lv.items()} for lv in levels]
            out[c] = [{g: m for g, m in lv.items() if m} for lv in out[c]]
        return out
