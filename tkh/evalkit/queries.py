"""Known-item retrieval queries for M4, generated from the export's claim sentences.

Each claim sentence of a paper (year <= cutoff) becomes a query whose target is the method the claim is about: the
method member of its claims edge, else the paper's presented method. Every name string of the target (surface form
and aliases) is masked out of the query, so lexical matching cannot find the target directly; a retrieval method
must reach it through what it groups or links with it. Queries shorter than `min_tokens` after masking are dropped.
"""

import re

from tkh.evalkit.text import clean


def known_item_queries(tkh, cutoff, min_tokens=5):
    n, e = tkh.nodes, tkh.edges
    ntype = n["type"].to_dict()
    sf = n["surface_form"].to_dict()
    al = n["aliases"].to_dict() if "aliases" in n else {}
    presented = {a: m[1] for m, r, a in zip(e["members"], e["relation_type"], e["article_id"]) if r == "presents"}
    seen, out = set(), []
    claims = e[(e["relation_type"] == "claims") & (e["article_year"] <= cutoff)]
    for eid, m, a in zip(claims.index, claims["members"], claims["article_id"]):
        methods = [v for v in m if ntype[v] == "method"]
        target = methods[0] if methods else presented.get(a)
        if target is None:
            continue
        names = [sf[target], *(al.get(target) if isinstance(al.get(target), list) else [])]
        for c in (v for v in m if ntype[v] == "claim"):
            text = clean(sf[c])
            for nm in sorted({clean(x) for x in names if str(x).strip()}, key=len, reverse=True):
                text = re.sub(r"(?<![\w-])" + re.escape(nm) + r"(?![\w-])", " ", text, flags=re.IGNORECASE)
            text = re.sub(r"\s+", " ", text).strip()
            if len(text.split()) < min_tokens or (text, target) in seen:
                continue
            seen.add((text, target))
            out.append({"query": f"{eid}:{c}", "text": text, "target": target, "paper": a})
    return out
