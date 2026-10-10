# ruff: noqa: E501
"""Scoring: matching rule (EVALUATION.md section 3) and metrics (N1, N2).

An injected error is a true positive if a flag in the injected run has a check id the error type maps to AND
its location overlaps the injection (same page, or the injected text / M11 id appears in the flag). Each error
and each flag is matched at most once. Flags that also appear in the clean run (same check, title, page) are
pre-existing real issues and are never counted as false positives.
"""
from __future__ import annotations

import re
from collections import defaultdict
from dataclasses import dataclass, field

from .types import TYPES

# Advisory flags are labelled advisory and excluded from benchmark scoring (PRD C11).
SCORED_SEVERITIES = {"critical", "major", "minor"}


def _norm(s: str | None) -> str:
    return re.sub(r"\s+", " ", (s or "").lower()).strip()


def flag_key(issue: dict) -> tuple:
    return (issue["check_id"], _norm(issue["title"]), (issue.get("where") or {}).get("page"))


def _locations(issue: dict) -> tuple[set[int], str]:
    spots = [issue.get("where") or {}, *(issue.get("related") or [])]
    pages = {s["page"] for s in spots if s.get("page")}
    text = _norm(" ".join([issue["title"], *(s.get("quote") or "" for s in spots)]))
    return pages, text


def location_match(error: dict, issue: dict) -> bool:
    pages, text = _locations(issue)
    m = error.get("match", {})
    if any(_norm(t) in _norm(issue["title"]) for t in m.get("titles", []) if _norm(t)):
        return True  # e.g. "M11 10.11 ..." for a removed section: flags for missing sections carry no page
    if pages & set(m.get("pages", [error.get("page")])):
        return True
    return any(_norm(q) and _norm(q) in text for q in m.get("texts", []))


@dataclass
class Scored:
    tp: list[tuple[dict, dict]] = field(default_factory=list)   # (error, issue)
    fn: list[dict] = field(default_factory=list)
    fp: list[dict] = field(default_factory=list)
    scored_flags: int = 0
    diagnosis: dict[str, str] = field(default_factory=dict)  # error_id -> why it was missed


def score_run(errors: list[dict], injected_issues: list[dict], clean_issues: list[dict], facts: dict | None = None) -> Scored:
    clean_keys = {flag_key(i) for i in clean_issues}
    flags = [i for i in injected_issues if i["severity"] in SCORED_SEVERITIES and flag_key(i) not in clean_keys]
    used: set[int] = set()
    out = Scored(scored_flags=len(flags))

    def candidates(e: dict) -> list[int]:
        spec = TYPES[e["type"]]
        return [n for n, i in enumerate(flags) if i["check_id"] in spec.expected_checks and location_match(e, i)
                and (not spec.title_hint or re.search(spec.title_hint, i["title"], re.I))]

    # most constrained errors first, so a flag that only one error can explain is not taken by another
    order = sorted(range(len(errors)), key=lambda k: len(candidates(errors[k])))
    hit: dict[int, int] = {}
    for k in order:
        free = [n for n in candidates(errors[k]) if n not in used]
        if free:
            hit[k] = free[0]
            used.add(free[0])
    for k, e in enumerate(errors):
        if k in hit:
            out.tp.append((e, flags[hit[k]]))
        else:
            out.fn.append(e)
            out.diagnosis[e.get("error_id", str(k))] = _diagnose(e, injected_issues, clean_keys, facts)
    out.fp = [i for n, i in enumerate(flags) if n not in used]
    return out


def _extracted(e: dict, facts: dict | None) -> bool | None:
    """Did ingest pick up the injected value at all? None = cannot tell for this type."""
    if not facts:
        return None
    t, new, page = e["type"], str(e["new"]), e["page"]
    kinds = {"T06": "age_min", "T08": "sample_size", "T10": "ratio", "T07": "dose", "T17": "duration_weeks"}
    if t in kinds:
        want = {new, str(float(new))} if re.fullmatch(r"\d+", new) else {new}
        return any(k == kinds[t] and p == page and v in want for k, p, v in facts["numbers"])
    if t == "T14":
        return any(p == page and new in tgt for p, tgt in facts["xrefs"])
    if t == "T16":
        return any(new in (str(int(w)) for w in (wm, wp) if w is not None) for _, _, wm, wp in facts["windows"])
    return None


def _diagnose(e: dict, injected: list[dict], clean_keys: set, facts: dict | None = None) -> str:
    """Why an injected error was not credited: gives A and B something to act on."""
    spec = TYPES[e["type"]]
    same = [i for i in injected if i["check_id"] in spec.expected_checks]
    ex = _extracted(e, facts)
    if ex is False:
        return "injected value was NOT extracted by ingest (pipeline gap)"
    tail = " (extracted, but the check did not flag it)" if ex else ""
    if not same:
        return f"no {'/'.join(spec.expected_checks)} flag at all" + (" (needs LLM extraction)" if spec.needs_llm else tail)
    fresh = [i for i in same if flag_key(i) not in clean_keys]
    if not fresh:
        return "expected check fired but only on issues already present in the clean run" + tail
    return "expected check fired elsewhere: " + "; ".join(f"p{(i.get('where') or {}).get('page')} {i['title'][:50]}" for i in fresh[:2]) + tail


def clean_flags_by_check(clean_runs: list[list[dict]]) -> dict:
    """Where the false alarms on clean protocols come from (critical+major only), per protocol on average."""
    out: dict[str, float] = defaultdict(float)
    for run in clean_runs:
        for i in run:
            if i["severity"] in {"critical", "major"}:
                out[f"{i['check_id']}:{i['severity']}"] += 1 / max(len(clean_runs), 1)
    return {k: round(v, 1) for k, v in sorted(out.items(), key=lambda kv: -kv[1])}


def prf(tp: int, fp: int, fn: int) -> dict:
    p = tp / (tp + fp) if tp + fp else 0.0
    r = tp / (tp + fn) if tp + fn else 0.0
    f = 2 * p * r / (p + r) if p + r else 0.0
    return {"recall": round(r, 3), "precision": round(p, 3), "f1": round(f, 3)}


def aggregate(scored: list[Scored]) -> dict:
    """N1: overall and per type / amendment category from per-protocol Scored results."""
    tp = sum(len(s.tp) for s in scored)
    fn = sum(len(s.fn) for s in scored)
    fp = sum(len(s.fp) for s in scored)
    per_type: dict[str, list[int]] = defaultdict(lambda: [0, 0])  # [n, found]
    per_cat: dict[str, list[int]] = defaultdict(lambda: [0, 0])
    for s in scored:
        for e, _ in s.tp:
            per_type[e["type"]][1] += 1
            per_cat[TYPES[e["type"]].amendment_category][1] += 1
        for e in [*s.fn, *(e for e, _ in s.tp)]:
            per_type[e["type"]][0] += 1
            per_cat[TYPES[e["type"]].amendment_category][0] += 1
    return {
        "test_set": {"injected_errors": tp + fn},
        "overall": prf(tp, fp, fn),
        "by_type": [{"type": t, "name": TYPES[t].name, "n": n, "found": f, "recall": round(f / n, 3) if n else 0.0}
                    for t, (n, f) in sorted(per_type.items())],
        "by_category": [{"amendment_category": c, "n": n, "recall": round(f / n, 3) if n else 0.0}
                        for c, (n, f) in sorted(per_cat.items())],
    }


def false_alarms_per_clean(clean_runs: list[list[dict]]) -> float:
    """N2: critical + major flags per clean protocol. Real issues in real protocols are included here on purpose;
    adjudicate them as real / debatable / false before reporting (EVALUATION.md N2)."""
    if not clean_runs:
        return 0.0
    n = sum(1 for run in clean_runs for i in run if i["severity"] in {"critical", "major"})
    return round(n / len(clean_runs), 2)
