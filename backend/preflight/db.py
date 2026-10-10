import os
from datetime import datetime, UTC

from sqlalchemy import JSON, Column
from sqlmodel import Field, Session, SQLModel, create_engine


def now() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


class Protocol(SQLModel, table=True):
    __tablename__ = "protocols"
    id: str = Field(primary_key=True)
    filename: str
    path: str
    title: str | None = None
    pages: int | None = None
    nct_id: str | None = None
    phase: str | None = None
    condition: str | None = None
    graph: dict | None = Field(default=None, sa_column=Column(JSON))
    uploaded_at: str = Field(default_factory=now)


class Run(SQLModel, table=True):
    __tablename__ = "runs"
    id: str = Field(primary_key=True)
    protocol_id: str = Field(foreign_key="protocols.id", index=True)
    version_label: str | None = None
    mode: str = "full"
    status: str = "queued"
    started_at: str | None = None
    finished_at: str | None = None
    duration_s: float | None = None
    llm_cost_usd: float = 0.0
    score: dict | None = Field(default=None, sa_column=Column(JSON))
    completeness: dict | None = Field(default=None, sa_column=Column(JSON))
    verifier: dict | None = Field(default=None, sa_column=Column(JSON))
    error: str | None = None


class IssueRow(SQLModel, table=True):
    __tablename__ = "issues"
    id: str = Field(primary_key=True)
    run_id: str = Field(foreign_key="runs.id", index=True)
    status: str = "open"
    data: dict = Field(sa_column=Column(JSON))


class Decision(SQLModel, table=True):
    __tablename__ = "decisions"
    id: str = Field(primary_key=True)
    issue_id: str = Field(foreign_key="issues.id", index=True)
    decision: str
    user: str | None = None
    note: str | None = None
    at: str = Field(default_factory=now)


class LLMCall(SQLModel, table=True):
    __tablename__ = "llm_calls"
    id: int | None = Field(default=None, primary_key=True)
    run_id: str | None = Field(default=None, index=True)
    step: str
    model: str
    tokens_in: int = 0
    tokens_out: int = 0
    latency_s: float = 0.0
    cost_usd: float = 0.0
    cache_hit: bool = False
    at: str = Field(default_factory=now)


class StepLog(SQLModel, table=True):
    __tablename__ = "step_logs"
    id: int | None = Field(default=None, primary_key=True)
    run_id: str = Field(index=True)
    step: str
    status: str
    started_at: str = Field(default_factory=now)
    duration_s: float | None = None
    message: str | None = None


engine = create_engine(
    os.getenv("DATABASE_URL", "sqlite:///./preflight.db"),
    connect_args={"check_same_thread": False},
)


_ready = False


def init_db():
    global _ready
    SQLModel.metadata.create_all(engine)
    _ready = True


def session() -> Session:
    if not _ready:
        init_db()
    return Session(engine)
