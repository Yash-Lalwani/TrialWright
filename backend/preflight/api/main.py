import importlib
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException

from preflight.api.routes import exports, issues, protocols, runs, trace
from preflight.db import init_db


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(title="Protocol Pre-Flight", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)

CODES = {400: "bad_request", 404: "not_found", 405: "method_not_allowed",
         409: "conflict", 422: "invalid_request"}


def error(status: int, message: str, code: str | None = None) -> JSONResponse:
    code = code or CODES.get(status, "error")
    return JSONResponse({"error": {"code": code, "message": message}}, status_code=status)


@app.exception_handler(HTTPException)
async def http_error(request: Request, exc: HTTPException):
    return error(exc.status_code, str(exc.detail))


@app.exception_handler(RequestValidationError)
async def validation_error(request: Request, exc: RequestValidationError):
    return error(422, "; ".join(f"{'.'.join(map(str, e['loc']))}: {e['msg']}" for e in exc.errors()))


@app.get("/api/health")
def health():
    return {
        "status": "ok",
        "llm_mode": os.getenv("LLM_MODE", "replay"),
        "model": os.getenv("PREFLIGHT_MODEL", "deepseek/deepseek-v4-flash-20260731"),
    }


for r in (protocols, runs, issues, exports, trace):
    app.include_router(r.router)

# B's routes (CONTRACTS 4.8 to 4.12) are picked up as soon as their files exist, so B never edits this file.
for name in ("analysis", "drafts", "benchmark"):
    try:
        module = importlib.import_module(f"preflight.api.routes.{name}")
    except ModuleNotFoundError as e:
        if e.name != f"preflight.api.routes.{name}":
            raise
        continue
    app.include_router(module.router)
