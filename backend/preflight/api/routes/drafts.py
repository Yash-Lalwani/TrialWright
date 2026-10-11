# ruff: noqa: E501
"""CONTRACTS 4.11: co-author drafts. B owns this file; A's main.py mounts it automatically.

POST /api/drafts runs coauthor.draft_from_brief in the background; progress goes to an in-memory event list (same SSE
format as runs). Finished drafts are kept in memory and written to UPLOAD_DIR/drafts/{id}.json so a restart does not
lose them. This avoids adding a table to A's db.py.
"""
import asyncio
import json
import logging
import secrets

from fastapi import APIRouter, HTTPException
from fastapi.responses import Response, StreamingResponse

from preflight.api import service
from preflight.coauthor import draft as coauthor
from preflight.coauthor.models import Brief, DraftSection
from preflight.export import m11_docx, usdm

router = APIRouter(prefix="/api")
log = logging.getLogger(__name__)

DRAFTS: dict[str, dict] = {}
EVENTS: dict[str, list[tuple[str, dict]]] = {}
_TASKS: set[asyncio.Task] = set()
DIR = service.UPLOAD_DIR / "drafts"


def _sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"


def _load(draft_id: str) -> dict:
    if draft_id in DRAFTS:
        return DRAFTS[draft_id]
    path = DIR / f"{draft_id}.json"
    if path.exists():
        DRAFTS[draft_id] = json.loads(path.read_text())
        return DRAFTS[draft_id]
    raise HTTPException(404, f"Draft {draft_id} not found")


def _save(draft_id: str) -> None:
    DIR.mkdir(parents=True, exist_ok=True)
    (DIR / f"{draft_id}.json").write_text(json.dumps(DRAFTS[draft_id]))


async def _execute(draft_id: str, brief: Brief) -> None:
    async def progress(step: str, status: str, message: str) -> None:
        EVENTS[draft_id].append(("progress", {"step": step, "status": status, "message": message}))

    try:
        out = await coauthor.draft_from_brief(brief, progress)
        DRAFTS[draft_id] = {"draft_id": draft_id, **out}
        _save(draft_id)
        EVENTS[draft_id].append(("complete", {"draft_id": draft_id}))
    except Exception as e:
        log.exception("Draft %s failed", draft_id)
        DRAFTS[draft_id] = {"draft_id": draft_id, "status": "failed", "brief": brief.model_dump(), "error": str(e)}
        EVENTS[draft_id].append(("error", {"message": str(e)}))


@router.post("/drafts", status_code=202)
async def create_draft(brief: Brief):
    draft_id = f"drf_{secrets.token_hex(4)}"
    DRAFTS[draft_id] = {"draft_id": draft_id, "status": "queued", "brief": brief.model_dump()}
    EVENTS[draft_id] = []
    task = asyncio.create_task(_execute(draft_id, brief))
    _TASKS.add(task)
    task.add_done_callback(_TASKS.discard)
    return {"draft_id": draft_id, "status": "queued"}


@router.get("/drafts/{draft_id}/events")
async def draft_events(draft_id: str):
    draft = _load(draft_id)

    async def stream():
        if draft_id not in EVENTS:     # finished before this server process started
            yield _sse("complete" if draft["status"] == "complete" else "error", {"draft_id": draft_id} if draft["status"] == "complete" else {"message": draft.get("error", "Draft failed")})
            return
        sent, idle = 0, 0.0
        while True:
            while sent < len(EVENTS[draft_id]):
                event, data = EVENTS[draft_id][sent]
                sent += 1
                yield _sse(event, data)
                if event in ("complete", "error"):
                    return
            await asyncio.sleep(0.2)
            idle += 0.2
            if idle >= 15:
                idle = 0.0
                yield ": keepalive\n\n"

    return StreamingResponse(stream(), media_type="text/event-stream", headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@router.get("/drafts/{draft_id}")
def get_draft(draft_id: str):
    return _load(draft_id)


@router.get("/drafts/{draft_id}/export")
def export_draft(draft_id: str, format: str = "docx"):
    if format not in ("usdm", "docx"):
        raise HTTPException(422, "format must be usdm or docx")
    draft = _load(draft_id)
    if draft["status"] != "complete":
        raise HTTPException(409, f"Draft {draft_id} is {draft['status']}")
    brief = Brief.model_validate(draft["brief"])
    sections = [DraftSection.model_validate(s) for s in draft["sections"]]
    size = coauthor.compute_sample_size(brief)
    graph = coauthor.build_graph(brief, sections, size)
    if format == "docx":
        body = m11_docx.to_docx(graph, [s.model_dump() for s in sections])
        media, suffix = "application/vnd.openxmlformats-officedocument.wordprocessingml.document", "m11.docx"
    else:
        doc = usdm.to_usdm(graph)
        errors = usdm.validate(doc)
        if errors:
            raise HTTPException(500, f"USDM export failed schema validation: {errors[0]}")
        body, media, suffix = json.dumps(doc, indent=2).encode(), "application/json", "usdm.json"
    return Response(body, media_type=media, headers={"Content-Disposition": f'attachment; filename="{draft_id}_{suffix}"'})
