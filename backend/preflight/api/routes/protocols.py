import asyncio
import hashlib
import re
from pathlib import Path
from typing import Literal

from fastapi import APIRouter, File, Form, Header, HTTPException, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlmodel import or_, select

from preflight.api import service
from preflight.db import Protocol, Run, now, session
from preflight.graph.models import ProtocolGraph
from preflight.ingest.entities import extract_meta
from preflight.ingest.pdf import read_pdf

router = APIRouter(prefix="/api")


class RunIn(BaseModel):
    mode: Literal["full", "rules_only"] = "full"
    version_label: str | None = None


def _workspace(value: str | None) -> str | None:
    """X-Workspace: a random id the browser keeps, so uploads stay out of other people's lists. Not authentication."""
    return value if value and re.fullmatch(r"[A-Za-z0-9-]{8,64}", value) else None


def _quick_meta(path: str) -> dict:
    if path.endswith(".json"):
        m = ProtocolGraph.model_validate_json(Path(path).read_text()).meta
        return {"title": m.title, "pages": None, "nct_id": m.nct_id, "phase": m.phase, "condition": m.condition}
    doc = read_pdf(path)
    m = extract_meta(doc, [])
    return {"title": m.title, "pages": doc.pages, "nct_id": m.nct_id, "phase": m.phase, "condition": None}


@router.post("/protocols", status_code=201)
async def upload_protocol(
    file: UploadFile = File(...), nct_id: str | None = Form(None), x_workspace: str | None = Header(None)
):
    workspace = _workspace(x_workspace)
    name = file.filename or "protocol.pdf"
    ext = name.rsplit(".", 1)[-1].lower()
    if ext not in ("pdf", "json"):
        raise HTTPException(400, "Upload a PDF or a Protocol Graph JSON file")
    data = await file.read()
    if ext == "pdf" and not data.startswith(b"%PDF"):
        raise HTTPException(400, f"{name} is not a PDF")
    pid = "prt_" + hashlib.sha256(data + (workspace or "").encode()).hexdigest()[:8]
    service.UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    path = service.UPLOAD_DIR / f"{pid}.{ext}"
    path.write_bytes(data)
    try:
        meta = await asyncio.to_thread(_quick_meta, str(path))
    except Exception as e:
        raise HTTPException(400, f"Could not read {name}: {e}") from e

    with session() as s:
        p = s.get(Protocol, pid) or Protocol(id=pid, filename=name, path=str(path), uploaded_at=now(),
                                             workspace=workspace)
        p.filename, p.path = name, str(path)
        p.title, p.pages, p.phase = meta["title"], meta["pages"], meta["phase"]
        p.nct_id = nct_id or meta["nct_id"]
        p.condition = p.condition or meta["condition"]
        s.add(p)
        s.commit()
        return service.protocol_dict(p)


@router.get("/protocols")
def list_protocols(x_workspace: str | None = Header(None)):
    visible = or_(Protocol.workspace.is_(None), Protocol.workspace == _workspace(x_workspace))
    with session() as s:
        rows = s.exec(select(Protocol).where(visible).order_by(Protocol.uploaded_at.desc())).all()
        return {"items": [service.protocol_dict(p, s) for p in rows]}


@router.get("/protocols/{protocol_id}/pdf")
def protocol_pdf(protocol_id: str):
    with session() as s:
        p = service.get_or_404(s, Protocol, protocol_id, "Protocol")
        if not p.path.endswith(".pdf"):
            raise HTTPException(404, f"Protocol {protocol_id} was uploaded as JSON and has no PDF")
        return FileResponse(p.path, media_type="application/pdf", filename=p.filename)


@router.post("/protocols/{protocol_id}/runs", status_code=202)
async def start_run(protocol_id: str, body: RunIn | None = None):
    body = body or RunIn()
    with session() as s:
        service.get_or_404(s, Protocol, protocol_id, "Protocol")
        run = Run(id=service.new_id("run"), protocol_id=protocol_id, mode=body.mode,
                  version_label=body.version_label, status="queued", started_at=now())
        s.add(run)
        s.commit()
        run_id = run.id
    service.start(run_id)
    return {"run_id": run_id, "status": "queued"}


@router.get("/protocols/{protocol_id}/runs")
def list_runs(protocol_id: str):
    with session() as s:
        service.get_or_404(s, Protocol, protocol_id, "Protocol")
        runs = s.exec(select(Run).where(Run.protocol_id == protocol_id).order_by(Run.started_at.desc())).all()
        return {"items": [service.run_dict(r, s) for r in runs]}
