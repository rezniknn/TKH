"""Can paper abstracts be obtained from the export's metadata? Route planning and (opt-in) retrieval.

Routes, per article, from the identifiers the export carries:
  - "arxiv id": arXiv API (export.arxiv.org), requesting version v1, i.e. the abstract as
                first posted (closest to the publication date; later revisions may postdate
                a snapshot cutoff);
  - "doi":      OpenAlex lookup by DOI (only used when there is a DOI but no arXiv id);
  - "title":    OpenAlex title search, falling back to arXiv title search.
Every retrieved record is verified against the article's own title (similarity, tolerant
of titles truncated in the export) before it counts as found.

Only the standard library is used. This module caches and writes nothing itself;
eval/extra/abstract_coherence.py stores the retrieved abstracts in eval/extra/abstracts/ (one <article id>.txt per
abstract plus manifest.json), so the extra coherence check runs offline.
"""

from difflib import SequenceMatcher
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen
import json
import re
import time
import xml.etree.ElementTree as ET

import pandas as pd

ARXIV = "https://export.arxiv.org/api/query"
OPENALEX = "https://api.openalex.org/works"
UA = {"User-Agent": "tkh-assessment/0.1 (research prototype; feasibility check)"}
ATOM = {"a": "http://www.w3.org/2005/Atom", "arxiv": "http://arxiv.org/schemas/atom"}


def _norm(s):
    return re.sub(r"[^0-9a-z]+", " ", str(s).lower()).strip()


def title_similarity(ours, theirs):
    """Similarity of two titles in [0, 1]; tolerant of our title being a truncated prefix."""
    a, b = _norm(ours), _norm(theirs)
    if not a or not b:
        return 0.0
    full = SequenceMatcher(None, a, b).ratio()
    prefix = SequenceMatcher(None, a, b[:len(a)]).ratio() if len(b) > len(a) else full
    return max(full, prefix)


def routes(tkh):
    """One row per article: identifiers and the retrieval route they allow."""
    art = tkh.articles.copy()
    doi = {}
    if "node_id" in art:
        prov = tkh.nodes["provenance"]
        doi = {a: (prov.get(nid) or {}).get("doi") for a, nid in art["node_id"].items() if isinstance(nid, str)}
    art["doi"] = art.index.map(lambda a: doi.get(a))
    arx = art["arxiv_id"] if "arxiv_id" in art else pd.Series(None, index=art.index)
    art["route"] = ["arxiv id" if isinstance(x, str) and x else "doi" if isinstance(d, str) and d else "title"
                    for x, d in zip(arx, art["doi"])]
    return art[[c for c in ("year", "title", "arxiv_id", "doi", "route") if c in art]]


def _get(url, timeout=30):
    with urlopen(Request(url, headers=UA), timeout=timeout) as r:
        return r.read()


def _parse_arxiv(xml_bytes):
    root = ET.fromstring(xml_bytes)
    out = []
    for e in root.findall("a:entry", ATOM):
        eid = e.findtext("a:id", default="", namespaces=ATOM)
        out.append({"arxiv_id": re.sub(r"v\d+$", "", eid.rsplit("/abs/", 1)[-1]),
                    "title": " ".join((e.findtext("a:title", default="", namespaces=ATOM)).split()),
                    "abstract": " ".join((e.findtext("a:summary", default="", namespaces=ATOM)).split()),
                    "published": e.findtext("a:published", default="", namespaces=ATOM)[:10]})
    return [r for r in out if r["title"] and r["title"] != "Error"]


def fetch_arxiv(ids, version="v1"):
    """{arxiv id: record} for a batch of ids (one request)."""
    q = urlencode({"id_list": ",".join(f"{i}{version}" for i in ids), "max_results": len(ids)})
    return {r["arxiv_id"]: r for r in _parse_arxiv(_get(f"{ARXIV}?{q}"))}


def search_arxiv_title(title, n=5):
    """arXiv title search on the exact phrase of the first 8 title words."""
    words = [w for w in _norm(title).split() if len(w) > 1][:8]
    q = urlencode({"search_query": f'ti:"{" ".join(words)}"', "max_results": n})
    return _parse_arxiv(_get(f"{ARXIV}?{q}"))


def inverted_index_to_text(inv):
    """OpenAlex abstract_inverted_index -> plain text."""
    if not inv:
        return ""
    pos = sorted((p, w) for w, ps in inv.items() for p in ps)
    return " ".join(w for _, w in pos)


def _openalex_record(w):
    return {"title": w.get("display_name") or "", "abstract": inverted_index_to_text(w.get("abstract_inverted_index")),
            "published": (w.get("publication_date") or "")[:10], "openalex_id": w.get("id")}


def openalex_by_doi(doi):
    return _openalex_record(json.loads(_get(f"{OPENALEX}/doi:{quote(doi)}")))


def search_openalex_title(title, n=5):
    q = urlencode({"search": title, "per-page": n})
    return [_openalex_record(w) for w in json.loads(_get(f"{OPENALEX}?{q}")).get("results", [])]


def _best(title, cands):
    best = max(cands, key=lambda c: title_similarity(title, c["title"]), default=None)
    return best, (title_similarity(title, best["title"]) if best else 0.0)


def retrieve(tkh, min_title_sim=0.9, pause=1.0):
    """Try every article's route; one row per article with a status and, when verified, the abstract.

    status: "abstract"            verified abstract;
            "retitled"            verified via the latest arXiv version's title (the paper was renamed
                                  after v1); the v1 abstract is kept;
            "no abstract"         the paper's record was found (title matches) but has no abstract;
            "id mismatch"         the export's arXiv id resolves to a different paper and title search
                                  did not recover it (counted separately: an export data-quality issue);
            "not found"           no matching record.
    """
    plan = routes(tkh)
    ids = [x for x in plan.loc[plan["route"] == "arxiv id", "arxiv_id"]]
    v1 = fetch_arxiv(ids) if ids else {}
    time.sleep(3.0)
    latest = fetch_arxiv(ids, version="") if ids else {}
    rows = {}
    for a, r in plan.iterrows():
        title, rec, status, source, sim, notes = r["title"], None, "not found", None, 0.0, []
        try:
            if r["route"] == "arxiv id":
                rv, rl = v1.get(r["arxiv_id"]), latest.get(r["arxiv_id"])
                s1 = title_similarity(title, rv["title"]) if rv else 0.0
                sl = title_similarity(title, rl["title"]) if rl else 0.0
                if rv and s1 >= min_title_sim:
                    rec, status, source, sim = rv, "abstract", "arXiv API (v1)", s1
                elif rv and sl >= min_title_sim:
                    rec, status, source, sim = rv, "retitled", "arXiv API (v1; title matches latest version)", sl
                else:
                    notes.append(f"arXiv id {r['arxiv_id']} resolves to '{(rl or rv or {}).get('title', '')[:60]}'")
            if rec is None and r["route"] == "doi":
                c = openalex_by_doi(r["doi"]); time.sleep(pause)
                sim = title_similarity(title, c["title"])
                if sim >= min_title_sim:
                    rec, source = c, "OpenAlex (DOI)"
                    status = "abstract" if c["abstract"] else "no abstract"
            if rec is None or status == "no abstract":
                best, bs = _best(title, search_openalex_title(title)); time.sleep(pause)
                if best is not None and bs >= min_title_sim:
                    rec, sim, source = best, bs, "OpenAlex (title search)"
                    status = "abstract" if best["abstract"] else "no abstract"
            if rec is None or status == "no abstract":
                time.sleep(3.0)  # arXiv asks for at most one request every 3 s
                best, bs = _best(title, search_arxiv_title(title))
                if best is not None and bs >= min_title_sim and best["abstract"]:
                    rec, sim, source, status = best, bs, "arXiv (title search)", "abstract"
            if rec is None and notes:
                status = "id mismatch"
            error = None
        except Exception as e:  # noqa: BLE001 - feasibility check: record and continue
            error = f"{type(e).__name__}: {e}"
        ok = status in ("abstract", "retitled")
        year = int(rec["published"][:4]) if rec and rec["published"][:4].isdigit() else None
        rows[a] = {"status": status, "source": source, "title_similarity": round(sim, 3),
                   "returned_title": rec["title"] if rec else None, "returned_year": year,
                   "year_minus_export_year": (year - int(r["year"])) if year else None,
                   "abstract_chars": len(rec["abstract"]) if rec and ok else 0,
                   "abstract": rec["abstract"] if rec and ok else None, "notes": "; ".join(notes) or None, "error": error}
    return plan.join(pd.DataFrame.from_dict(rows, orient="index"))
