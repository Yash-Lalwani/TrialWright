from fastapi import APIRouter

from preflight.api.stubs import example

router = APIRouter(prefix="/api")


@router.get("/runs/{run_id}/trace")
def get_trace(run_id: str):
    return example("trace")
