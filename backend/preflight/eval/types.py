# ruff: noqa: E501
"""Error taxonomy T01-T18 (docs/EVALUATION.md section 2): expected checks and amendment categories."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ErrorType:
    id: str
    name: str
    expected_checks: tuple[str, ...]
    amendment_category: str
    needs_llm: bool  # the expected check only fires when A's LLM extraction ran (endpoints, criteria, stats)
    title_hint: str | None = None  # regex a flag title must match, for checks shared by several types (C4, C6, C8, C3)
    document_level: bool = False  # the check compares two statements far apart (power vs N): any NEW flag of the check counts, wherever it cites


TYPES: dict[str, ErrorType] = {t.id: t for t in [
    ErrorType("T01", "Endpoint visit removed from SoA", ("C1",), "visit_schedule", True),
    ErrorType("T02", "Endpoint timepoint changed in one place", ("C1", "C4"), "endpoints", True),
    ErrorType("T03", "Orphan procedure added to SoA", ("C2",), "visit_schedule", True),
    ErrorType("T04", "Secondary objective's endpoint deleted", ("C3",), "endpoints", True, r"objective has no endpoint"),
    ErrorType("T05", "Endpoint analysis removed from statistics", ("C3",), "statistics", True, r"no analysis method"),
    ErrorType("T06", "Age range changed in one place", ("C4",), "eligibility", False, r"\bage\b"),
    ErrorType("T07", "Dose changed in one place", ("C4",), "intervention", False, r"\bdos(e|ing)\b"),
    ErrorType("T08", "Sample size changed in one place", ("C4",), "statistics", False, r"sample size|enrol"),
    ErrorType("T09", "Power/effect changed so N not reproducible", ("C7",), "statistics", True, None, True),
    ErrorType("T10", "Randomisation ratio changed in one place", ("C4",), "design", False, r"ratio|randomi[sz]ation"),
    ErrorType("T11", "Blinding / unblinding text removed", ("C5", "B3"), "design", False),
    ErrorType("T12", "Exclusion criterion contradicts an inclusion criterion", ("C8",), "eligibility", True, r"inclusion and exclusion|conflict"),
    ErrorType("T13", "Lab threshold value conflicts between mentions", ("C8",), "eligibility", True, r"unit|threshold"),
    ErrorType("T14", "Cross-reference to a nonexistent section", ("C9",), "clerical", False),
    ErrorType("T15", "Required M11 section removed", ("B1", "B3"), "completeness", False),
    ErrorType("T16", "Visit windows made to overlap", ("C6",), "visit_schedule", False, r"window|overlap"),
    ErrorType("T17", "Treatment/follow-up duration no longer adds up", ("C6",), "design", False, r"duration|add up|total"),
    ErrorType("T18", "Enrollment differs from registry record", ("C10",), "registry", False),
]}
