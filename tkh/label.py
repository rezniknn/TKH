"""T5: generates a label and one-sentence gloss per super-node at levels 0-1. Records the exact labeller input and keeps evidence within the snapshot cutoff (P6).

`LLMLabeller` (the shipped labeller) asks an open model through a local Ollama server
(tkh/llm.py; model, endpoint and prompt template from the config's [labels] section; the
committed response cache makes the run reproducible offline).

Evidence (P6 and the circularity control of E3):
- a super-node's concept members are split in two halves by a seeded hash of the
  super-node's member set (`split_members`); the labeller sees only the SEEN half, the
  judge's primary evidence is the HELD-OUT half (tkh/evaluate/faithfulness.py);
- at most `max_members` members are shown, highest snapshot paper count first, as
  "name [type]"; names are snapshot nodes, so nothing after the cutoff is shown;
- the prompt states the cutoff year and forbids dates and unlisted entities.
`evidence(cutoff, level, members)` returns exactly what the labeller saw; build.py writes
it to out/<cutoff>/label_inputs.json.

`placeholder_labeller` is a deterministic stand-in for tests: it only restates the
super-node's composition, so it cannot over-claim. Levels >= 2 carry no label.
"""

from collections import Counter

from tkh.evalkit.evidence import Evidence  # noqa: F401  (evaluator-owned; re-exported for callers)
from tkh.evalkit.split import split_members  # noqa: F401  (the evaluator's seen/held-out split: the contract)
from tkh.llm import mode as _mode  # noqa: F401
from tkh.semantic import CONCEPT_TYPES

LABELLED_LEVELS = (0, 1)


def placeholder_labeller(tkh):
    ntype = tkh.nodes["type"].to_dict()
    name = tkh.nodes["surface_form"].to_dict()
    n_papers = tkh.nodes["prov_articles"].map(len).to_dict()

    def label(cutoff, level, members):
        if level not in LABELLED_LEVELS:
            return None, None
        concept = [v for v in members if ntype[v] in CONCEPT_TYPES] or list(members)
        types = Counter(ntype[v] for v in concept)
        top = sorted(concept, key=lambda v: (-n_papers[v], name[v]))[:2]
        lab = f"[placeholder] {types.most_common(1)[0][0]}: " + "; ".join(name[v][:30] for v in top)
        mix = ", ".join(f"{c} {t}" for t, c in types.most_common(3))
        gloss = f"[placeholder] {len(concept)} concept nodes ({mix}); the label lists the most widely shared members."
        return lab, gloss
    return label


class LLMLabeller:
    """labeller(cutoff, level, members) -> (label, gloss) for levels 0-1, (None, None) otherwise."""

    def __init__(self, tkh, cfg, llm=None):
        from tkh.llm import CachedLLM
        self.cfg, self.ev = cfg, Evidence(tkh, cfg)
        lab = cfg.labels
        self.llm = llm or CachedLLM(lab["labeller_model"], lab["cache"], lab.get("endpoint", "http://localhost:11434"), _mode(cfg))
        self.inputs = {}

    def prompt(self, view):
        from tkh.llm import render
        return render(self.cfg.labels["labeller_prompt"], cutoff=view["cutoff"], members="\n".join(view["lines"]))

    def __call__(self, cutoff, level, members):
        if level not in LABELLED_LEVELS:
            return None, None
        view = self.ev.labeller_view(cutoff, level, members)
        resp = self.llm.complete(self.prompt(view))
        label, gloss = clean_output(resp)
        self.inputs[(cutoff, level, tuple(sorted(members)))] = {"shown": view["shown"], "held_out": view["held_out"],
                                                               "prompt_key": self.llm.key(self.prompt(view))}
        return label, gloss


def clean_output(resp):
    """(label, gloss) from a model's JSON answer; unparseable answers become explicit failures."""
    label = resp.get("label") if isinstance(resp, dict) else None
    gloss = resp.get("gloss") if isinstance(resp, dict) else None
    label = " ".join(str(label).split()) if label else "[label generation failed]"
    gloss = " ".join(str(gloss).split()) if gloss else "[gloss generation failed]"
    return label, gloss
