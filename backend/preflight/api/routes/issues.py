from fastapi import APIRouter
from pydantic import BaseModel

from preflight.api.stubs import example

router = APIRouter(prefix="/api")


class DecisionIn(BaseModel):
    decision: str
    note: str | None = None
    user: str | None = None


@router.get("/runs/{run_id}/issues")
def list_issues(run_id: str, severity: str | None = None, category: str | None = None,
                source: str | None = None, status: str | None = None):
    data = example("issues")
    filters = {"severity": severity, "category": category, "source": source, "status": status}
    items = [i for i in data["items"] if all(v is None or i[k] == v for k, v in filters.items())]
    return {"total": len(items) if any(filters.values()) else data["total"], "items": items}


@router.post("/issues/{issue_id}/decision")
def decide(issue_id: str, body: DecisionIn):
    return example("decision")
