import asyncio
import logging
import os
import re
import secrets
import time
from pathlib import Path

from fastapi import HTTPException
from sqlmodel import Session, func, select

from preflight import score
from preflight.db import IssueRow, LLMCall, Protocol, Run, StepLog, now, session
from preflight.graph.issues import Issue
from preflight.llm.client import current_run_id
from preflight.pipeline import check_graph, ingest_file

log = logging.getLogger(__name__)

UPLOAD_DIR = Path(os.getenv("UPLOAD_DIR", Path(__file__).resolve().parents[2] / "uploads"))
STEPS = ["ingest", "map_sections", "extract_soa", "extract_entities", "rules",
         "reviewers", "verify", "burden", "peers", "score"]
SEVERITIES = ["critical", "major", "minor", "advisory"]

EVENTS: dict[str, list[tuple[str, dict]]] = {}
_TASKS: set[asyncio.Task] = set()


def new_id(prefix: str) -> str:
    return f"{prefix}_{secrets.token_hex(4)}"


def get_or_404(s: Session, model, key: str, label: str):
    row = s.get(model, key)
    if row is None:
        raise HTTPException(404, f"{label} {key} not found")
    return row


def protocol_dict(p: Protocol, s: Session | None = None) -> dict:
    out = {"protocol_id": p.id, "filename": p.filename, "title": p.title, "pages": p.pages, "nct_id": p.nct_id,
           "phase": p.phase, "condition": p.condition, "uploaded_at": p.uploaded_at}
    if s is not None:
        run = s.exec(select(Run).where(Run.protocol_id == p.id).order_by(Run.started_at.desc())).first()
        out["latest_run"] = ({"run_id": run.id, "score": (run.score or {}).get("overall"), "status": run.status}
                             if run else None)
    return out


def run_dict(run: Run, s: Session) -> dict:
    rows = s.exec(select(IssueRow).where(IssueRow.run_id == run.id)).all()
    counts = {k: 0 for k in SEVERITIES} | {"open": 0, "accepted": 0, "rejected": 0}
    for r in rows:
        counts[r.data["severity"]] = counts.get(r.data["severity"], 0) + 1
        counts[r.status] = counts.get(r.status, 0) + 1
    return {"run_id": run.id, "protocol_id": run.protocol_id, "version_label": run.version_label, "mode": run.mode,
            "status": run.status, "started_at": run.started_at, "finished_at": run.finished_at,
            "duration_s": run.duration_s, "llm_cost_usd": run.llm_cost_usd, "score": run.score, "counts": counts}


def issue_dict(row: IssueRow) -> dict:
    return {**row.data, "status": row.status}


async def _emit(run_id: str, event: str, data: dict) -> None:
    EVENTS.setdefault(run_id, []).append((event, data))


async def execute(run_id: str) -> None:
    current_run_id.set(run_id)
    with session() as s:
        run = s.get(Run, run_id)
        protocol = s.get(Protocol, run.protocol_id)
        run.status, run.started_at = "running", now()
        s.add(run)
        s.commit()
        path, nct_id, mode = protocol.path, protocol.nct_id, run.mode
    start = last = time.monotonic()

    async def progress(step: str, status: str, message: str) -> None:
        nonlocal last
        elapsed, last = time.monotonic() - last, time.monotonic()
        with session() as s:
            s.add(StepLog(run_id=run_id, step=step, status=status, duration_s=round(elapsed, 2), message=message))
            s.commit()
        pct = round(100 * (STEPS.index(step) + 1) / len(STEPS)) if step in STEPS else 0
        await _emit(run_id, "progress", {"step": step, "status": status, "pct": pct, "message": message})

    try:
        graph = await ingest_file(path, nct_id=nct_id, use_llm=mode == "full", progress=progress)
        result = await check_graph(graph, mode, progress=progress)
        suffix = run_id.split("_", 1)[1][:6]
        with session() as s:
            for issue in result.issues:
                iid = f"iss_{suffix}{issue.id.split('_')[1]}"
                s.add(IssueRow(id=iid, run_id=run_id, status="open", data=issue.model_dump() | {"id": iid}))
            run = s.get(Run, run_id)
            protocol = s.get(Protocol, run.protocol_id)
            protocol.graph = graph.model_dump()
            protocol.title = graph.meta.title or protocol.title
            protocol.phase, protocol.condition = graph.meta.phase or protocol.phase, graph.meta.condition
            protocol.nct_id = graph.meta.nct_id or protocol.nct_id
            cost = s.exec(select(func.sum(LLMCall.cost_usd)).where(LLMCall.run_id == run_id)).one() or 0.0
            run.score, run.completeness = result.score.model_dump(), result.completeness.model_dump()
            run.status, run.finished_at = "complete", now()
            run.duration_s, run.llm_cost_usd = round(time.monotonic() - start, 1), round(float(cost), 4)
            s.add_all([run, protocol])
            s.commit()
        await _emit(run_id, "complete", {"run_id": run_id})
    except Exception as e:
        log.exception("Run %s failed", run_id)
        with session() as s:
            run = s.get(Run, run_id)
            run.status, run.error, run.finished_at = "failed", str(e), now()
            s.add(run)
            s.commit()
        await _emit(run_id, "error", {"message": str(e)})


def start(run_id: str) -> None:
    EVENTS[run_id] = []
    task = asyncio.create_task(execute(run_id))
    _TASKS.add(task)
    task.add_done_callback(_TASKS.discard)


def run_issues(s: Session, run_id: str) -> list[IssueRow]:
    return s.exec(select(IssueRow).where(IssueRow.run_id == run_id).order_by(IssueRow.id)).all()


def rescore(s: Session, run: Run) -> dict:
    issues = [Issue.model_validate(issue_dict(r)) for r in run_issues(s, run.id)]
    summary = (run.completeness or {}).get("summary", {})
    burden = (run.score or {}).get("burden", 50)
    return score.compute(issues, summary.get("present", 0), summary.get("thin", 0), summary.get("required", 0),
                         burden).model_dump()


def match_key(issue: dict) -> tuple:
    title = re.sub(r"[^a-z0-9 ]", "", issue["title"].lower())
    return issue["check_id"], re.sub(r"\s+", " ", title).strip(), (issue["where"] or {}).get("section")
