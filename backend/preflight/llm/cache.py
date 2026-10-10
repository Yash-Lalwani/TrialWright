import hashlib
import json
import os
from pathlib import Path

CACHE_DIR = Path(os.getenv("LLM_CACHE_DIR", Path(__file__).resolve().parents[3] / "data" / "llm_cache"))


def key(model: str, system: str, user: str, schema_name: str) -> str:
    raw = json.dumps([model, system, user, schema_name])
    return hashlib.sha256(raw.encode()).hexdigest()[:32]


def get(k: str) -> dict | None:
    path = CACHE_DIR / f"{k}.json"
    return json.loads(path.read_text()) if path.exists() else None


def put(k: str, entry: dict) -> None:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    (CACHE_DIR / f"{k}.json").write_text(json.dumps(entry, indent=1))
