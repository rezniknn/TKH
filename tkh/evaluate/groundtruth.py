"""Ground truth (questions.csv / ground_truth.json) mapped onto graph nodes, for evaluation only.

Matching is strict and reproducible: a ground-truth method name matches a node when the
normalised name (NFKC, lower case, alphanumerics only; a trailing parenthetical such as
'MACE (general)' is dropped) equals the normalised surface form or one of the node's
aliases. Names that match nothing are reported, never guessed.
"""

from pathlib import Path
import json
import re
import unicodedata


def key(s):
    s = unicodedata.normalize("NFKC", str(s)).lower()
    s = re.sub(r"\s*\([^)]*\)\s*$", "", s)
    return re.sub(r"[^0-9a-z]+", "", s)


def name_index(tkh):
    """{normalised name: set(node ids)} over surface forms and aliases."""
    idx = {}
    al = tkh.nodes["aliases"] if "aliases" in tkh.nodes else None
    for nid, sf in tkh.nodes["surface_form"].items():
        extra = al.get(nid) if al is not None else None
        for s in [sf, *(extra if isinstance(extra, list) else [])]:
            idx.setdefault(key(s), set()).add(nid)
    return idx


def load_ground_truth(path):
    return json.loads(Path(path).read_text())


def question_targets(tkh, gt, types=None):
    """{question: {"expected": {name: set(ids)}, "wrong_domain": {name: set(ids)}}} for type-A questions."""
    idx = name_index(tkh)
    out = {}
    for q, v in gt.items():
        if v.get("type") != "A":
            continue
        def match(names):
            m = {n: {i for i in idx.get(key(n), set()) if types is None or tkh.nodes.at[i, "type"] in types}
                 for n in names}
            return m
        out[q] = {"expected": match(v.get("expected_methods", [])),
                  "wrong_domain": match((v.get("fp_categories") or {}).get("wrong_domain", []))}
    return out
