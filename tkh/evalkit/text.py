"""Evaluator-owned node text: name strings and a word TF-IDF index, independent of any method's semantic signal code."""

import re
import unicodedata

from sklearn.feature_extraction.text import TfidfVectorizer

_DASHES = dict.fromkeys(map(ord, "\u2010\u2011\u2012\u2013\u2014\u2212"), "-")
_SPACES = dict.fromkeys(map(ord, "\u00a0\u2009\u202f"), " ")


def clean(s):
    """NFKC, Unicode dashes/minus to '-', non-breaking spaces to ' ', collapsed whitespace."""
    s = unicodedata.normalize("NFKC", str(s)).translate(_DASHES).translate(_SPACES)
    return re.sub(r"\s+", " ", s).strip()


def names(tkh):
    """{node id: surface form + aliases}."""
    al = tkh.nodes["aliases"] if "aliases" in tkh.nodes else None
    out = {}
    for nid, sf in tkh.nodes["surface_form"].items():
        extra = al.get(nid) if al is not None else None
        extra = extra if isinstance(extra, list) else []
        out[nid] = clean(" ; ".join([sf, *extra]))
    return out


def word_tfidf(texts):
    """L2-normalised word TF-IDF matrix and the fitted vectoriser."""
    vec = TfidfVectorizer(lowercase=True, stop_words="english", sublinear_tf=True,
                          token_pattern=r"(?u)\b[\w][\w\-\+]*\b", min_df=1)
    return vec.fit_transform(texts), vec
