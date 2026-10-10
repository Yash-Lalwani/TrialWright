from fastapi import APIRouter
from sqlmodel import select

from preflight.api import service
from preflight.db import Decision, IssueRow, LLMCall, Run, StepLog, session

router = APIRouter(prefix="/api")


@router.get("/runs/{run_id}/trace")
def get_trace(run_id: str):
    with session() as s:
        run = service.get_or_404(s, Run, run_id, "Run")
        steps = s.exec(select(StepLog).where(StepLog.run_id == run_id).order_by(StepLog.id)).all()
        calls = s.exec(select(LLMCall).where(LLMCall.run_id == run_id).order_by(LLMCall.id)).all()
        audit = s.exec(select(Decision).join(IssueRow, Decision.issue_id == IssueRow.id)
                       .where(IssueRow.run_id == run_id).order_by(Decision.at)).all()
        return {
            "steps": [{"step": x.step, "status": x.status, "started_at": x.started_at, "duration_s": x.duration_s}
                      for x in steps],
            "llm_calls": [{"step": c.step, "model": c.model, "tokens_in": c.tokens_in, "tokens_out": c.tokens_out,
                           "latency_s": round(c.latency_s, 2), "cost_usd": c.cost_usd, "cache_hit": c.cache_hit}
                          for c in calls],
            "verifier": run.verifier or {"ai_findings": 0, "dropped_ungrounded": 0, "shown": 0},
            "audit": [{"audit_id": a.id, "issue_id": a.issue_id, "decision": a.decision, "user": a.user,
                       "note": a.note, "at": a.at} for a in audit],
        }
