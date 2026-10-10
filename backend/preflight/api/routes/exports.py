import json
from typing import Literal

from fastapi import APIRouter
from fastapi.responses import Response

from preflight.api.stubs import example

router = APIRouter(prefix="/api")

FORMATS = {
    "usdm": ("application/json", "json"),
    "docx": ("application/vnd.openxmlformats-officedocument.wordprocessingml.document", "docx"),
    "report_pdf": ("application/pdf", "pdf"),
    "report_csv": ("text/csv", "csv"),
}


def _stub_body(run_id: str, format: str) -> bytes:
    if format == "usdm":
        return json.dumps({"stub": True, "run_id": run_id}).encode()
    if format == "report_csv":
        rows = ["id,check_id,severity,title,page"]
        rows += [f'{i["id"]},{i["check_id"]},{i["severity"]},"{i["title"]}",{i["where"]["page"]}'
                 for i in example("issues")["items"]]
        return "\n".join(rows).encode()
    if format == "report_pdf":
        import fitz

        doc = fitz.open()
        doc.new_page().insert_text((72, 72), f"Stub issue report for {run_id}")
        return doc.tobytes()
    import io

    from docx import Document

    buf = io.BytesIO()
    d = Document()
    d.add_paragraph(f"Stub M11 export for {run_id}")
    d.save(buf)
    return buf.getvalue()


@router.get("/runs/{run_id}/export")
def export(run_id: str, format: Literal["usdm", "docx", "report_pdf", "report_csv"]):
    media_type, ext = FORMATS[format]
    filename = f"{run_id}_{format}.{ext}"
    return Response(_stub_body(run_id, format), media_type=media_type,
                    headers={"Content-Disposition": f'attachment; filename="{filename}"'})
