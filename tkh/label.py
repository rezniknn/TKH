"""T5 placeholder: a label and one-sentence gloss per super-node at levels 0-1, using only the snapshot's evidence (P6 cutoff).

`placeholder_labeller` is a deterministic stand-in until a real labeller is wired in: it only
restates the super-node's composition (most common concept type and its members shared by the
most snapshot papers), so it cannot over-claim. Levels >= 2 carry no label.
"""

from collections import Counter

from tkh.coarsen import node_papers
from tkh.io import snapshot
from tkh.semantic import CONCEPT_TYPES

LABELLED_LEVELS = (0, 1)


def placeholder_labeller(tkh):
    ntype = tkh.nodes["type"].to_dict()
    name = tkh.nodes["surface_form"].to_dict()
    n_papers = {}  # per cutoff: paper counts within that snapshot only

    def label(cutoff, level, members):
        if level not in LABELLED_LEVELS:
            return None, None
        if cutoff not in n_papers:
            n_papers[cutoff] = {v: len(p) for v, p in node_papers(tkh, snapshot(tkh, cutoff)).items()}
        concept = [v for v in members if ntype[v] in CONCEPT_TYPES] or list(members)
        types = Counter(ntype[v] for v in concept)
        top = sorted(concept, key=lambda v: (-n_papers[cutoff][v], name[v]))[:2]
        lab = f"[placeholder] {types.most_common(1)[0][0]}: " + "; ".join(name[v][:30] for v in top)
        mix = ", ".join(f"{c} {t}" for t, c in types.most_common(3))
        gloss = f"[placeholder] {len(concept)} concept nodes ({mix}); the label lists the most widely shared members."
        return lab, gloss
    return label
