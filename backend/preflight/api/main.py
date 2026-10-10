import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="Protocol Pre-Flight")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
def health():
    return {
        "status": "ok",
        "llm_mode": os.getenv("LLM_MODE", "replay"),
        "model": os.getenv("PREFLIGHT_MODEL", "deepseek/deepseek-v4-flash-20260731"),
    }
