"""Response models for CONTRACTS.md 4.8 (burden), 4.9 (peers), 4.10 (precedent). Shapes are frozen."""
from __future__ import annotations

from pydantic import BaseModel


class PerPatient(BaseModel):
    visits: int
    procedures_total: int
    invasive: int
    patient_hours: float
    site_hours: float
    cost_usd: float


class ByVisit(BaseModel):
    visit: str
    study_day: float | None
    patient_minutes: float
    site_minutes: float
    procedures: list[str]


class OrphanProcedure(BaseModel):
    name: str
    occurrences: int
    patient_minutes: float
    cost_usd: float


class PeerPercentiles(BaseModel):
    patient_hours: float
    procedures_total: float
    visits: float
    n_peers_with_soa: int


class Assumptions(BaseModel):
    file: str
    version: str


class BurdenReport(BaseModel):
    per_patient: PerPatient
    by_visit: list[ByVisit]
    orphan_procedures: list[OrphanProcedure]
    peer_percentiles: PeerPercentiles | None
    assumptions: Assumptions


class PeerQuery(BaseModel):
    condition: str | None
    phase: str | None
    start_year_min: int


class PeerMetric(BaseModel):
    metric: str
    label: str
    value: float
    percentile: float
    peer_median: float
    peer_p25: float
    peer_p75: float
    distribution: list[float]


class PeerTrial(BaseModel):
    nct_id: str
    title: str
    sponsor: str
    phase: str
    enrollment: int | None
    start_date: str | None


class PeerSet(BaseModel):
    query: PeerQuery
    n: int
    metrics: list[PeerMetric]
    hotspot_issue_ids: list[str]
    trials: list[PeerTrial]


class ThisProtocol(BaseModel):
    primary_endpoint: str
    primary_timeframe: str
    key_eligibility: list[str]
    enrollment: int | None
    n_visits: int


class PrecedentRow(BaseModel):
    nct_id: str
    title: str
    sponsor: str
    phase: str
    similarity: float
    primary_endpoint: str
    primary_timeframe: str
    key_eligibility: list[str]
    enrollment: int | None
    n_visits: int | None


class PrecedentTable(BaseModel):
    this_protocol: ThisProtocol
    rows: list[PrecedentRow]
