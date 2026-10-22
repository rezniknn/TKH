"""M3: claim-level over-claim rate of labels and glosses, with a judge whose validity is measured, not assumed.

Protocol (one judge model, configs/default.toml [labels] judge_model; prompts configs/prompts/):
1. Decompose every level-0/1 label + gloss into atomic claims (claims_split.txt). Deterministic check: at least
   80% of each claim's content words must occur in the label or gloss; otherwise the decomposition is replaced by
   the two claims [label, gloss].
2. Judge each claim against an evidence pack (claim_entail.txt). A claim counts as SUPPORTED only if the judge says
   so AND the quoted line occurs verbatim (after whitespace/case normalisation) in the pack: an anti-sycophancy check
   that needs no model.
   Packs: "held_out" = the evaluator's held-out half of the members (tkh.evalkit.split) + claim sentences and titles
   of their papers (<= cutoff) = the circularity control; "all" = all members (P6's literal wording).
3. A label over-claims if at least one of its claims is unsupported. Raw rate with a Wilson interval.
4. Judge validity from known-answer controls judged with the held-out pack:
   known-false: "swap" (a claim of another super-node of the same level, different parent), "sibling" (a claim of
   a sibling under the same parent: the hard control), "inflation" (an unsupported superlative), "temporal" (a date
   after the cutoff); known-true: a held-out member stated as a member, or its node type stated as present.
   Se = P(unsupported | known-false), Sp = P(supported | known-true). Corrected claim-level rate by Rogan-Gladen,
   u = (u_obs + Sp - 1) / (Se + Sp - 1), clipped to [0, 1]; label-level corrected rate
   1 - mean_l (1 - u)^{n_l}; intervals by bootstrap over labels and controls. Gate: Youden J = Se_sibling + Sp - 1
   >= 0.4, else the metric is reported INVALID.
"""

import random
import re

import numpy as np

from tkh.evalkit.evidence import Evidence
from tkh.evalkit.split import split_members
from tkh.llm import CachedLLM, mode, render

STOP = set("a an the of and or for to in on with by from as at is are be this that these those its it their group "
           "groups which into using use used via such including includes include various related".split())


def _words(s):
    return [w for w in re.findall(r"[a-z0-9][a-z0-9\-+]*", s.lower()) if w not in STOP]


def _norm(s):
    return re.sub(r"\s+", " ", re.sub(r"^[\s\-\*•]+", "", str(s))).strip().lower()


class Entailment:
    def __init__(self, tkh, cfg, llm=None):
        lab = cfg.labels
        self.cfg, self.ev = cfg, Evidence(tkh, cfg)
        self.llm = llm or CachedLLM(lab["judge_model"], lab["cache"], lab.get("endpoint", "http://localhost:11434"), mode(cfg))
        self.seed = int(lab.get("seed", 0))
        root = cfg.labels.get("labeller_prompt")
        from pathlib import Path
        self.p_split = Path(root).parent / "claims_split.txt"
        self.p_entail = Path(root).parent / "claim_entail.txt"

    # ---- evidence
    def pack(self, cutoff, members, kind):
        concept = self.ev.concept(members)
        seen, held = split_members(concept, self.seed)
        nodes = concept if kind == "all" else held
        lines, _ = self.ev.member_lines(cutoff, nodes) if nodes else ([], [])
        claims, titles = self.ev.paper_texts(cutoff, nodes or seen)
        items = [ln.lstrip("- ").strip() for ln in lines] + claims + [f"Paper title: {t}" for t in titles]
        return items, held

    # ---- steps
    def decompose(self, label, gloss):
        resp = self.llm.complete(render(self.p_split, label=label, gloss=gloss or ""))
        claims = resp.get("claims") if isinstance(resp, dict) else None
        src = set(_words(f"{label} {gloss}"))
        ok = isinstance(claims, list) and claims and all(
            isinstance(c, str) and _words(c) and np.mean([w in src for w in _words(c)]) >= 0.8 for c in claims)
        return ([" ".join(str(c).split()) for c in claims], True) if ok else ([label, gloss or label], False)

    def judge(self, cutoff, claim, items):
        evidence = "\n".join(items) or "(none)"
        resp = self.llm.complete(render(self.p_entail, cutoff=cutoff, evidence=evidence, claim=claim))
        verdict = str(resp.get("verdict", "")).strip().lower() if isinstance(resp, dict) else ""
        quote = _norm(resp.get("quote", "")) if isinstance(resp, dict) else ""
        quote_ok = len(quote) >= 6 and any(quote in _norm(x) or _norm(x) in quote for x in items if len(_norm(x)) >= 6)
        return {"verdict": verdict, "quote_ok": quote_ok, "supported": verdict == "supported" and quote_ok}

    # ---- protocol
    def run(self, hierarchies, levels=(0, 1), seed=0):
        """hierarchies: {cutoff: hierarchy dict}. Returns (label rows, claim rows, control rows)."""
        rng = random.Random(seed)
        lab_rows, claim_rows, ctrl_rows = [], [], []
        for c, h in sorted(hierarchies.items()):
            sns = {s["id"]: s for s in h["supernodes"] if s["level"] in levels and s.get("label")}
            dec = {i: self.decompose(s["label"], s["gloss"]) for i, s in sns.items()}
            for i, s in sorted(sns.items()):
                claims, ok = dec[i]
                res = {}
                for kind in ("held_out", "all"):
                    items, held = self.pack(c, s["member_ids"], kind)
                    js = [self.judge(c, cl, items) for cl in claims]
                    for cl, j in zip(claims, js):
                        claim_rows.append({"snapshot": c, "level": s["level"], "id": i, "pass": kind, "claim": cl, **j})
                    res[kind] = any(not j["supported"] for j in js)
                lab_rows.append({"snapshot": c, "level": s["level"], "id": i, "n_claims": len(claims), "decomposition_ok": ok,
                                 "over_claim_held_out": res["held_out"], "over_claim_all": res["all"]})
                # known-answer controls, judged with the held-out pack
                items, held = self.pack(c, s["member_ids"], "held_out")
                others = [j for j in sns if j != i and sns[j]["level"] == s["level"] and dec[j][1]]   # decomposed claims only
                diff = [j for j in others if sns[j].get("parent_id") != s.get("parent_id") or s["level"] == 0]
                sib = [j for j in others if s["level"] > 0 and sns[j].get("parent_id") == s.get("parent_id")]
                ctrls = []
                if diff:
                    ctrls.append(("swap", False, dec[rng.choice(sorted(diff))][0][0]))
                if sib:
                    ctrls.append(("sibling", False, dec[rng.choice(sorted(sib))][0][0]))
                ctrls.append(("inflation", False, "Its methods outperform all alternative approaches on every benchmark."))
                ctrls.append(("temporal", False, f"Its main results were first published in {c + 2}."))
                if held:
                    v = rng.choice(held)
                    nm, ty = self.ev.name[v], self.ev.ntype[v]
                    ctrls.append(("true", True, f"The group includes {nm}." if rng.random() < 0.5 else f"Some members are of type {ty}."))
                for kind, truth, cl in ctrls:
                    j = self.judge(c, cl, items)
                    ctrl_rows.append({"snapshot": c, "level": s["level"], "id": i, "control": kind, "truth": truth,
                                      "claim": cl, **j})
        return lab_rows, claim_rows, ctrl_rows


def summarise(lab_rows, claim_rows, ctrl_rows, n_boot=2000, seed=0, j_min=0.4):
    """Raw and Rogan-Gladen corrected over-claim rates, judge Se/Sp by control type, validity gate."""
    from tkh.evaluate.stats import wilson
    rng = np.random.default_rng(seed)
    out = {}
    n = len(lab_rows)
    for kind in ("held_out", "all"):
        k = sum(r[f"over_claim_{kind}"] for r in lab_rows)
        lo, hi = wilson(k, n)
        out[f"raw_over_claim_{kind}"] = {"value": k / n if n else None, "lo": lo, "hi": hi, "n": n, "k": k}
    ctrl = {}
    for r in ctrl_rows:
        ctrl.setdefault(r["control"], []).append(r)
    sp_rows = ctrl.get("true", [])
    sp = np.mean([r["supported"] for r in sp_rows]) if sp_rows else np.nan
    for t, rows in ctrl.items():
        if t == "true":
            continue
        se = float(np.mean([not r["supported"] for r in rows]))
        lo, hi = wilson(sum(not r["supported"] for r in rows), len(rows))
        out[f"Se_{t}"] = {"value": se, "lo": lo, "hi": hi, "n": len(rows)}
    lo, hi = wilson(sum(r["supported"] for r in sp_rows), len(sp_rows))
    out["Sp"] = {"value": float(sp), "lo": lo, "hi": hi, "n": len(sp_rows)}
    se_hard = out.get("Se_sibling", {}).get("value", np.nan)
    J = se_hard + sp - 1 if np.isfinite(se_hard) and np.isfinite(sp) else np.nan
    out["J_sibling"] = {"value": float(J) if np.isfinite(J) else None, "n": out.get("Se_sibling", {}).get("n", 0)}
    out["valid"] = bool(np.isfinite(J) and J >= j_min)
    held = [r for r in claim_rows if r["pass"] == "held_out"]

    def corrected(lrows, crows, ctr):
        u_obs = np.mean([not r["supported"] for r in crows]) if crows else np.nan
        false = [r for t, rs in ctr.items() if t != "true" for r in rs]
        sev = [r for r in ctr.get("sibling", [])] or false
        se_ = np.mean([not r["supported"] for r in sev]) if sev else np.nan
        sp_ = np.mean([r["supported"] for r in ctr.get("true", [])]) if ctr.get("true") else np.nan
        den = se_ + sp_ - 1
        if not np.isfinite(den) or den <= 0:
            return np.nan, np.nan
        u = float(np.clip((u_obs + sp_ - 1) / den, 0, 1))
        lab = float(np.mean([1 - (1 - u) ** r["n_claims"] for r in lrows]))
        return u, lab

    u, labc = corrected(lab_rows, held, ctrl)
    ids = sorted({(r["snapshot"], r["id"]) for r in lab_rows})
    by_id = {k: [r for r in held if (r["snapshot"], r["id"]) == k] for k in ids}
    lab_by = {(r["snapshot"], r["id"]): r for r in lab_rows}
    ctrl_by = {}
    for r in ctrl_rows:
        ctrl_by.setdefault((r["snapshot"], r["id"]), []).append(r)
    boots = []
    for _ in range(n_boot):
        pick = [ids[i] for i in rng.integers(0, len(ids), len(ids))]
        cr = [x for k in pick for x in by_id[k]]
        ct = {}
        for k in pick:
            for x in ctrl_by.get(k, []):
                ct.setdefault(x["control"], []).append(x)
        boots.append(corrected([lab_by[k] for k in pick], cr, ct)[1])
    b = np.array([x for x in boots if np.isfinite(x)])
    out["corrected_over_claim_held_out"] = {"value": labc if np.isfinite(labc) else None,
                                            "lo": float(np.quantile(b, 0.025)) if len(b) else None,
                                            "hi": float(np.quantile(b, 0.975)) if len(b) else None, "n": n,
                                            "claim_level": u if np.isfinite(u) else None}
    out["decomposition_ok"] = float(np.mean([r["decomposition_ok"] for r in lab_rows])) if lab_rows else None
    out["quote_rejections"] = float(np.mean([r["verdict"] == "supported" and not r["quote_ok"] for r in claim_rows])) if claim_rows else None
    return out
