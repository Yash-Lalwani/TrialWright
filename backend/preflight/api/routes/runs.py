import asyncio
import json

from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from preflight.api.stubs import example

router = APIRouter(prefix="/api")

STEPS = ["ingest", "map_sections", "extract_soa", "extract_entities", "rules",
         "reviewers", "verify", "burden", "peers", "score"]


@router.get("/runs/{run_id}/events")
async def run_events(run_id: str):
    async def stream():
        for i, step in enumerate(STEPS, 1):
            await asyncio.sleep(0.3)
            data = {"step": step, "status": "done", "pct": round(100 * i / len(STEPS)), "message": ""}
            yield f"event: progress\ndata: {json.dumps(data)}\n\n"
        yield f"event: complete\ndata: {json.dumps({'run_id': run_id})}\n\n"

    return StreamingResponse(stream(), media_type="text/event-stream")


@router.get("/runs/{run_id}")
def get_run(run_id: str):
    return example("run")


@router.get("/runs/{run_id}/completeness")
def get_completeness(run_id: str):
    return example("completeness")


@router.get("/runs/{from_run_id}/diff/{to_run_id}")
def get_diff(from_run_id: str, to_run_id: str):
    return example("diff")
