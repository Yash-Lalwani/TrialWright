from typing import Literal

from pydantic import BaseModel


class Span(BaseModel):
    page: int
    bbox: list[float] | None = None
    quote: str


class Section(BaseModel):
    id: str
    m11_id: str | None
    title: str
    level: int
    page_start: int
    page_end: int
    text: str


class Endpoint(BaseModel):
    id: str
    text: str
    measure: str
    timepoints_weeks: list[float]
    analysis_ids: list[str]
    span: Span


class Objective(BaseModel):
    id: str
    level: Literal["primary", "secondary", "exploratory"]
    text: str
    endpoint_ids: list[str]
    span: Span


class Criterion(BaseModel):
    id: str
    kind: Literal["inclusion", "exclusion"]
    text: str
    thresholds: list[dict]
    span: Span


class Visit(BaseModel):
    id: str
    name: str
    study_day: float | None
    window_minus: float | None
    window_plus: float | None


class Procedure(BaseModel):
    id: str
    name: str
    normalized_name: str


class SoA(BaseModel):
    visits: list[Visit]
    procedures: list[Procedure]
    cells: dict[str, dict[str, bool]]
    span: Span | None


class Arm(BaseModel):
    name: str
    type: str
    dose: str | None
    route: str | None
    frequency: str | None
    duration_weeks: float | None


class Stats(BaseModel):
    sample_size: int | None
    alpha: float | None
    sided: int | None
    power: float | None
    effect_size: float | None
    effect_type: str | None
    control_rate: float | None
    dropout: float | None
    analyses: list[dict]


class NumberFact(BaseModel):
    kind: Literal["age_min", "age_max", "dose", "duration_weeks", "sample_size", "ratio", "arms"]
    value: float | str
    unit: str | None
    span: Span


class Meta(BaseModel):
    title: str
    nct_id: str | None
    phase: str | None
    condition: str | None
    sponsor: str | None
    masking: str | None
    allocation: str | None
    n_arms: int | None
    ratio: str | None


class ProtocolGraph(BaseModel):
    protocol_id: str
    meta: Meta
    sections: list[Section]
    objectives: list[Objective]
    endpoints: list[Endpoint]
    criteria: list[Criterion]
    min_age: float | None
    max_age: float | None
    arms: list[Arm]
    soa: SoA | None
    stats: Stats
    numbers: list[NumberFact]
    xrefs: list[dict]
    abbreviations: dict
