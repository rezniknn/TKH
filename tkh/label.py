"""T5: generates a label and one-sentence gloss per super-node at levels 0-1. Records the exact labeller input and keeps evidence within the snapshot cutoff (P6).

`placeholder_labeller` is a deterministic stand-in used until the LLM labeller is wired in:
it only restates the super-node's composition (most common concept type and its most
widely shared members), so it cannot over-claim. Levels >= 2 carry no label.
"""

from collections import Counter

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
