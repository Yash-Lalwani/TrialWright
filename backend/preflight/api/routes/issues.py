from typing import Literal

from fastapi import APIRouter
from pydantic import BaseModel

from preflight.api import service
from preflight.db import Decision, IssueRow, Run, session

router = APIRouter(prefix="/api")


class DecisionIn(BaseModel):
    decision: Literal["accepted", "rejected", "open"]
    note: str | None = None
    user: str | None = None


@router.get("/runs/{run_id}/issues")
def list_issues(run_id: str, severity: str | None = None, category: str | None = None,
                source: str | None = None, status: str | None = None):
    with session() as s:
        service.get_or_404(s, Run, run_id, "Run")
        items = [service.issue_dict(r) for r in service.run_issues(s, run_id)]
    filters = {"severity": severity, "category": category, "source": source, "status": status}
    items = [i for i in items if all(v is None or i[k] == v for k, v in filters.items())]
    return {"total": len(items), "items": items}


@router.post("/issues/{issue_id}/decision")
def decide(issue_id: str, body: DecisionIn):
    with session() as s:
        row = service.get_or_404(s, IssueRow, issue_id, "Issue")
        row.status = body.decision
        audit = Decision(id=service.new_id("aud"), issue_id=issue_id, decision=body.decision, user=body.user,
                         note=body.note)
        s.add_all([row, audit])
        s.commit()
        run = s.get(Run, row.run_id)
        run.score = service.rescore(s, run)
        s.add(run)
        s.commit()
        return {"issue_id": issue_id, "status": row.status, "audit_id": audit.id, "score": run.score}
