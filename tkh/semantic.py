"""P3 semantic signal used for clustering: node text features/embeddings. Must stay separate from the independent signal used to evaluate coherence.

Only text that ships with the graph is used (no downloads, no external models):
- "name":    surface_form plus `aliases` (present on some method nodes);
- "context": name, plus text attached to the node by the export itself: the sentences
             of claims edges the node is a member of, the future-topic sentences of the
             article that presents it (presented methods only), and the free-text
             attributes of its evaluated_on edges (metric / task / domain strings).
Article titles are deliberately excluded from node text: a title is shared by every
node of a paper, so it would re-encode "same paper", i.e. the structural signal.

Vectors are TF-IDF, either on words or on character n-grams within word boundaries
(robust to hyphenation, plurals and spacing variants such as 'TensorField'/'Tensor Field').
"""

from collections import defaultdict
import re
import unicodedata

import numpy as np
from sklearn.decomposition import TruncatedSVD
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.preprocessing import normalize

CONCEPT_TYPES = ("method", "task", "problem", "technique", "component", "dataset", "metric")


_DASHES = dict.fromkeys(map(ord, "\u2010\u2011\u2012\u2013\u2014\u2212"), "-")
_SPACES = dict.fromkeys(map(ord, "\u00a0\u2009\u202f"), " ")


def clean(s):
    """NFKC, then Unicode dashes/minus to '-' and non-breaking/narrow spaces to ' ', collapse whitespace.
    (NFKC alone maps U+2011 to U+2010, not to ASCII '-', so the mapping must come after it.)"""
    s = unicodedata.normalize("NFKC", str(s)).translate(_DASHES).translate(_SPACES)
    return re.sub(r"\s+", " ", s).strip()


def name_key(s):
    """Normalised name for exact matching: NFKC, lower case, alphanumerics only; a trailing parenthetical is dropped."""
    s = unicodedata.normalize("NFKC", str(s)).lower()
    s = re.sub(r"\s*\([^)]*\)\s*$", "", s)
    return re.sub(r"[^0-9a-z]+", "", s)


def name_keys(tkh):
    """{node id: set of name_key of its surface form and aliases} (the names the method's text sees)."""
    al = tkh.nodes["aliases"] if "aliases" in tkh.nodes else None
    out = {}
    for nid, sf in tkh.nodes["surface_form"].items():
        extra = al.get(nid) if al is not None else None
        out[nid] = {k for k in map(name_key, [sf, *(extra if isinstance(extra, list) else [])]) if k}
    return out


def names(tkh):
    """{node id: surface form + aliases}."""
    al = tkh.nodes["aliases"] if "aliases" in tkh.nodes else None
    out = {}
    for nid, sf in tkh.nodes["surface_form"].items():
        extra = al.get(nid) if al is not None else None
        extra = extra if isinstance(extra, list) else []
        out[nid] = clean(" ; ".join([sf, *extra]))
    return out


def attached_text(tkh):
    """{node id: list of text snippets attached to it by claims / future-work / evaluated_on edges}."""
    n, e = tkh.nodes, tkh.edges
    sf = n["surface_form"].to_dict()
    ntype = n["type"].to_dict()
    att = defaultdict(list)
    presented = {}  # article id -> presented method
    for m, r, a in zip(e["members"], e["relation_type"], e["article_id"]):
        if r == "presents":
            presented[a] = m[1]
    for m, r, a, attrs in zip(e["members"], e["relation_type"], e["article_id"],
                              e["attributes"] if "attributes" in e else [None] * len(e)):
        attrs = attrs if isinstance(attrs, dict) else {}
        if r == "claims":
            claim = [v for v in m if ntype[v] == "claim"]
            for v in m:
                if ntype[v] not in ("claim", "article"):
                    att[v] += [sf[c] for c in claim]
        elif r == "proposes_future_work" and a in presented:
            att[presented[a]] += [sf[v] for v in m[1:]]
        elif r == "evaluated_on":
            txt = " ".join(str(attrs[k]) for k in ("metric", "task", "domain") if attrs.get(k))
            for v in m:
                if txt:
                    att[v].append(txt)
    return att


def node_texts(tkh, node_ids, mode="name"):
    nm = names(tkh)
    if mode == "name":
        return [nm[v] for v in node_ids]
    if mode == "context":
        att = attached_text(tkh)
        return [clean(" . ".join([nm[v], *att.get(v, [])])) for v in node_ids]
    raise ValueError(mode)


def vectorize(texts, kind="char"):
    """L2-normalised sparse TF-IDF matrix (rows = texts)."""
    if kind == "word":
        vec = TfidfVectorizer(lowercase=True, stop_words="english", sublinear_tf=True,
                              token_pattern=r"(?u)\b[\w][\w\-\+]*\b", min_df=1)
    elif kind == "char":
        vec = TfidfVectorizer(lowercase=True, analyzer="char_wb", ngram_range=(3, 5), sublinear_tf=True, min_df=1)
    else:
        raise ValueError(kind)
    X = vec.fit_transform(texts)
    return X, vec


def lsa(X, dim=100, seed=0):
    """Dense L2-normalised LSA (truncated SVD) projection of a TF-IDF matrix."""
    dim = min(dim, X.shape[1] - 1, X.shape[0] - 1)
    return normalize(TruncatedSVD(dim, random_state=seed).fit_transform(X))


def cosine(Z):
    """Dense cosine-similarity matrix of L2-normalised rows (sparse or dense input)."""
    S = Z @ Z.T
    return np.asarray(S.toarray() if hasattr(S, "toarray") else S)
