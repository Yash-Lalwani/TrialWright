"""Import A's graph models; fall back to a TEMPORARY copy of CONTRACTS.md 3.1 until A's land.

Delete the fallback block (and this file) once graph/models.py and graph/issues.py are on main.
"""
from __future__ import annotations

try:  # A owns these
    from preflight.graph.issues import Fix, Issue, Where, Why  # type: ignore
    from preflight.graph.models import ProtocolGraph  # type: ignore

    USING_FALLBACK = False
except ImportError:  # TEMPORARY, copied from docs/CONTRACTS.md 3.1
    from typing import Literal

    from pydantic import BaseModel

    USING_FALLBACK = True

    class Span(BaseModel):
        page: int
        bbox: list[float] | None = None
        quote: str

    class Meta(BaseModel):
        title: str
        nct_id: str | None = None
        phase: str | None = None
        condition: str | None = None
        sponsor: str | None = None
        masking: str | None = None
        allocation: str | None = None
        n_arms: int | None = None
        ratio: str | None = None

    class Visit(BaseModel):
        id: str
        name: str
        study_day: float | None = None
        window_minus: float | None = None
        window_plus: float | None = None

    class Procedure(BaseModel):
        id: str
        name: str
        normalized_name: str

    class SoA(BaseModel):
        visits: list[Visit]
        procedures: list[Procedure]
        cells: dict[str, dict[str, bool]]
        span: Span | None = None

    class Criterion(BaseModel):
        id: str
        kind: Literal["inclusion", "exclusion"]
        text: str
        thresholds: list[dict] = []
        span: Span

    class ProtocolGraph(BaseModel):  # only the fields B reads; A's has more
        protocol_id: str
        meta: Meta
        criteria: list[Criterion] = []
        min_age: float | None = None
        max_age: float | None = None
        soa: SoA | None = None

    class Where(BaseModel):
        section: str | None = None
        page: int | None = None
        bbox: list[float] | None = None
        quote: str | None = None

    class Why(BaseModel):
        explanation: str
        standard_ref: str | None = None
        amendment_category: str

    class Fix(BaseModel):
        suggestion: str
        patch: dict | None = None

    class Issue(BaseModel):
        id: str
        check_id: str
        source: str
        category: str
        severity: str
        title: str
        where: Where
        related: list[Where] = []
        why: Why
        fix: Fix | None = None
        confidence: float
        verified: bool
        status: str = "open"
