# ruff: noqa: E501
"""Procedure burden assumptions (data/assumptions/procedure_costs.csv) and name matching."""
from __future__ import annotations

import csv
import re
from dataclasses import dataclass
from pathlib import Path

PATH = Path(__file__).resolve().parents[3] / "data" / "assumptions" / "procedure_costs.csv"
VISIT_OVERHEAD = "clinic visit overhead"


@dataclass(frozen=True)
class Procedure:
    name: str
    keywords: tuple[str, ...]
    category: str
    patient_minutes: float
    site_minutes: float
    cost_usd: float
    invasive: bool
    source: str


def load(path: Path = PATH) -> tuple[str, list[Procedure]]:
    """(version, rows). Lines starting with '#' are comments; the version is read from the first one."""
    text = path.read_text()
    version = (re.search(r"VERSION\s+(\S+?)[.\s]", text) or [None, "unknown"])[1]
    rows = csv.DictReader(line for line in text.splitlines() if not line.startswith("#"))
    return version, [Procedure(r["normalized_name"], tuple(k.strip().lower() for k in r["match_keywords"].split("|")),
                               r["category"], float(r["patient_minutes"]), float(r["site_minutes"]), float(r["cost_usd"]),
                               r["invasive"] == "true", r["source"]) for r in rows]


def match(name: str, procedures: list[Procedure]) -> Procedure | None:
    """Row whose longest keyword occurs in the procedure name, or None.

    A keyword must start at a word boundary but may be followed by anything, so footnote letters that PDF extraction
    glues onto names ('Physical Examinationg', '12-Lead ECGk') still match while 'ct' does not match inside 'effect'."""
    low = name.lower()
    best, best_len = None, 0
    for p in procedures:
        for k in p.keywords:
            if k != "__visit__" and len(k) > best_len and re.search(r"(?<![a-z0-9])" + re.escape(k), low):
                best, best_len = p, len(k)
    return best
