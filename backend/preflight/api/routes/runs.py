import asyncio
import json

from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from preflight.api import service
from preflight.checks.completeness import Completeness
from preflight.db import Run, session

router = APIRouter(prefix="/api")


def _sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"


@router.get("/runs/{run_id}/events")
async def run_events(run_id: str):
    with session() as s:
        run = service.get_or_404(s, Run, run_id, "Run")
        status, error = run.status, run.error

    async def stream():
        if run_id not in service.EVENTS:
            # Run finished before this server process started: send its final state.
            if status == "complete":
                yield _sse("complete", {"run_id": run_id})
            elif status == "failed":
                yield _sse("error", {"message": error or "Run failed"})
            return
        sent, idle = 0, 0.0
        while True:
            events = service.EVENTS[run_id]
            while sent < len(events):
                event, data = events[sent]
                sent += 1
                yield _sse(event, data)
                if event in ("complete", "error"):
                    return
            await asyncio.sleep(0.2)
            idle += 0.2
            if idle >= 15:
                idle = 0.0
                yield ": keepalive\n\n"

    return StreamingResponse(stream(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@router.get("/runs/{run_id}")
def get_run(run_id: str):
    with session() as s:
        return service.run_dict(service.get_or_404(s, Run, run_id, "Run"), s)


@router.get("/runs/{run_id}/completeness")
def get_completeness(run_id: str):
    with session() as s:
        run = service.get_or_404(s, Run, run_id, "Run")
        if run.completeness is None:
            return Completeness.model_validate(
                {"summary": {"present": 0, "thin": 0, "missing": 0, "required": 0}, "items": []}).model_dump()
        return run.completeness


@router.get("/runs/{from_run_id}/diff/{to_run_id}")
def get_diff(from_run_id: str, to_run_id: str):
    with session() as s:
        a = service.get_or_404(s, Run, from_run_id, "Run")
        b = service.get_or_404(s, Run, to_run_id, "Run")
        old = {service.match_key(i): i for i in map(service.issue_dict, service.run_issues(s, a.id))}
        new = {service.match_key(i): i for i in map(service.issue_dict, service.run_issues(s, b.id))}

        def plain(score):
            return {k: v for k, v in (score or {}).items() if k != "weights"}

        return {
            "from_run": a.id, "to_run": b.id,
            "score_from": plain(a.score), "score_to": plain(b.score),
            "resolved": [i for k, i in old.items() if k not in new],
            "new": [i for k, i in new.items() if k not in old],
            "unchanged": [i for k, i in new.items() if k in old],
        }
