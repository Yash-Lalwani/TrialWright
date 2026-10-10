from pydantic import BaseModel


class Where(BaseModel):
    section: str | None
    page: int | None
    bbox: list[float] | None
    quote: str | None


class Why(BaseModel):
    explanation: str
    standard_ref: str | None
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
    fix: Fix | None
    confidence: float
    verified: bool
    status: str = "open"
