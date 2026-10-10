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


def score_run(errors: list[dict], injected_issues: list[dict], clean_issues: list[dict]) -> Scored:
    clean_keys = {flag_key(i) for i in clean_issues}
    flags = [i for i in injected_issues if i["severity"] in SCORED_SEVERITIES and flag_key(i) not in clean_keys]
    used: set[int] = set()
    out = Scored(scored_flags=len(flags))
    for e in errors:
        expected = TYPES[e["type"]].expected_checks
        hit = next((n for n, i in enumerate(flags) if n not in used and i["check_id"] in expected
                    and location_match(e, i)), None)
        if hit is None:
            out.fn.append(e)
        else:
            used.add(hit)
            out.tp.append((e, flags[hit]))
    out.fp = [i for n, i in enumerate(flags) if n not in used]
    return out


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
