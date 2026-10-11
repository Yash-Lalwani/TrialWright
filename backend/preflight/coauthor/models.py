# ruff: noqa: E501
"""Brief and Draft models (CONTRACTS 4.11). Shapes follow the contract; the extra fields are additive and marked."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel


class ExpectedEffect(BaseModel):
    """proportions: control + treatment rates. mean_diff_sd: effect = standardised difference d. hazard_ratio: effect = HR, event_rate = overall event probability."""
    type: Literal["proportions", "mean_diff_sd", "hazard_ratio"]
    control: float | None = None
    treatment: float | None = None
    effect: float | None = None
    event_rate: float | None = None


class Brief(BaseModel):
    condition: str
    phase: str
    intervention: str
    comparator: str | None = None
    primary_question: str
    population: str
    duration_weeks: float | None = None
    alpha: float = 0.05
    power: float = 0.8
    expected_effect: ExpectedEffect
    dropout: float | None = None
    ratio: str = "1:1"


class SampleSizeOut(BaseModel):
    n_total: int
    n_per_arm: int
    method: str
    inputs: dict


class DraftSection(BaseModel):
    m11_id: str
    title: str
    markdown: str
    citations: list[str]
    source: Literal["llm", "template", "calculation"] = "template"      # ADDITIVE: how the text was produced
