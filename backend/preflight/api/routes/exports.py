import json
from typing import Literal

from fastapi import APIRouter, HTTPException
from fastapi.responses import Response

from preflight.api import service
from preflight.db import Protocol, Run, session
from preflight.export import m11_docx, report, usdm
from preflight.graph.models import ProtocolGraph

router = APIRouter(prefix="/api")

FORMATS = {
    "usdm": ("application/json", "usdm.json"),
    "docx": ("application/vnd.openxmlformats-officedocument.wordprocessingml.document", "m11.docx"),
    "report_pdf": ("application/pdf", "issues.pdf"),
    "report_csv": ("text/csv", "issues.csv"),
}


@router.get("/runs/{run_id}/export")
def export(run_id: str, format: Literal["usdm", "docx", "report_pdf", "report_csv"]):
    with session() as s:
        run = service.get_or_404(s, Run, run_id, "Run")
        if run.status != "complete":
            raise HTTPException(409, f"Run {run_id} is {run.status}")
        protocol = s.get(Protocol, run.protocol_id)
        issues = [service.issue_dict(r) for r in service.run_issues(s, run_id)]
        run_info = service.run_dict(run, s)
        graph = ProtocolGraph.model_validate(protocol.graph) if protocol.graph else None

    if format in ("usdm", "docx") and graph is None:
        raise HTTPException(409, f"Run {run_id} has no Protocol Graph")
    if format == "usdm":
        doc = usdm.to_usdm(graph)
        errors = usdm.validate(doc)
        if errors:
            raise HTTPException(500, f"USDM export failed schema validation: {errors[0]}")
        body = json.dumps(doc, indent=2).encode()
    elif format == "docx":
        body = m11_docx.to_docx(graph)
    elif format == "report_pdf":
        body = report.to_pdf(protocol.title or protocol.filename, run_info, issues)
    else:
        body = report.to_csv(issues)

    media_type, suffix = FORMATS[format]
    filename = f"{run_id}_{suffix}"
    return Response(body, media_type=media_type, headers={"Content-Disposition": f'attachment; filename="{filename}"'})
