import fitz
from fastapi import APIRouter, File, Form, UploadFile
from fastapi.responses import Response

from preflight.api.stubs import example

router = APIRouter(prefix="/api")


@router.post("/protocols", status_code=201)
async def upload_protocol(file: UploadFile = File(...), nct_id: str | None = Form(None)):
    return example("protocol")


@router.get("/protocols")
def list_protocols():
    return example("protocols_list")


@router.get("/protocols/{protocol_id}/pdf")
def protocol_pdf(protocol_id: str):
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 72), f"Stub PDF for {protocol_id}")
    return Response(doc.tobytes(), media_type="application/pdf")


@router.post("/protocols/{protocol_id}/runs", status_code=202)
def start_run(protocol_id: str, body: dict | None = None):
    return example("run_created")


@router.get("/protocols/{protocol_id}/runs")
def list_runs(protocol_id: str):
    return example("runs_list")
