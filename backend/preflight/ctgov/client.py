"""ClinicalTrials.gov API v2 client with on-disk caching.

JSON responses are cached under data/peers/ (keyed by request hash); protocol
PDFs are streamed to data/corpus/ (or dest_dir) and renamed atomically.
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import os
from pathlib import Path

import httpx

API = "https://clinicaltrials.gov/api/v2"
CDN = "https://cdn.clinicaltrials.gov/large-docs"
ROOT = Path(__file__).resolve().parents[3]  # repo root
CACHE_DIR = Path(os.environ.get("PREFLIGHT_PEER_CACHE", ROOT / "data" / "peers"))
CORPUS_DIR = Path(os.environ.get("PREFLIGHT_CORPUS_DIR", ROOT / "data" / "corpus"))

_MIN_INTERVAL = 0.15  # seconds between live requests
_last_call = 0.0
_lock = asyncio.Lock()


async def _throttle() -> None:
    global _last_call
    async with _lock:
        wait = _MIN_INTERVAL - (asyncio.get_event_loop().time() - _last_call)
        if wait > 0:
            await asyncio.sleep(wait)
        _last_call = asyncio.get_event_loop().time()


def _cache_path(path: str, params: dict) -> Path:
    key = json.dumps([path, sorted(params.items())], sort_keys=True)
    h = hashlib.sha256(key.encode()).hexdigest()[:16]
    return CACHE_DIR / "api" / f"{h}.json"


async def _get_json(path: str, params: dict | None = None, *, use_cache: bool = True,
                    client: httpx.AsyncClient | None = None) -> dict:
    params = params or {}
    cp = _cache_path(path, params)
    if use_cache and cp.exists():
        return json.loads(cp.read_text())
    own = client is None
    client = client or httpx.AsyncClient(timeout=60, follow_redirects=True)
    try:
        for attempt in range(5):
            await _throttle()
            r = await client.get(f"{API}{path}", params=params)
            if r.status_code in (429, 500, 502, 503, 504):
                await asyncio.sleep(2 ** attempt)
                continue
            r.raise_for_status()
            data = r.json()
            cp.parent.mkdir(parents=True, exist_ok=True)
            tmp = cp.with_suffix(".tmp")
            tmp.write_text(json.dumps(data))
            tmp.replace(cp)
            return data
        r.raise_for_status()
        raise RuntimeError("unreachable")
    finally:
        if own:
            await client.aclose()


async def get_study(nct_id: str) -> dict:
    """Full study record (API v2 /studies/{nct})."""
    return await _get_json(f"/studies/{nct_id}")


async def search_studies(params: dict, limit: int = 200) -> list[dict]:
    """Generic paged /studies search; follows nextPageToken up to `limit`."""
    out: list[dict] = []
    p = {"pageSize": min(limit, 100), **params}
    token = None
    while len(out) < limit:
        q = dict(p, **({"pageToken": token} if token else {}))
        data = await _get_json("/studies", q)
        out.extend(data.get("studies", []))
        token = data.get("nextPageToken")
        if not token:
            break
    return out[:limit]


PEER_FIELDS = ("NCTId,BriefTitle,LeadSponsorName,Phase,EnrollmentCount,StartDate,PrimaryCompletionDate,CompletionDate,"
               "EligibilityCriteria,MinimumAge,MaximumAge,PrimaryOutcomeMeasure,SecondaryOutcomeMeasure,ArmGroupLabel,Condition")


async def search_peers(condition: str, phase: str | None, start_year_min: int = 2015,
                       limit: int = 200, fields: str | None = None) -> list[dict]:
    """Peer trials: same condition/phase, DRUG or BIOLOGICAL, started >= start_year_min."""
    adv = [f"AREA[StartDate]RANGE[{start_year_min}-01-01,MAX]",
           "(AREA[InterventionType]DRUG OR AREA[InterventionType]BIOLOGICAL)"]
    if phase:
        adv.append(f"AREA[Phase]{phase}")
    params = {"query.cond": condition, "filter.advanced": " AND ".join(adv)}
    if fields:
        params["fields"] = fields
    return await search_studies(params, limit)


def protocol_files(study: dict) -> list[str]:
    """Filenames of attached large docs flagged hasProtocol (works on partial or full records)."""
    docs = (study.get("documentSection", {}).get("largeDocumentModule", {}).get("largeDocs", []))
    return [d["filename"] for d in docs if d.get("hasProtocol")]


def pdf_url(nct_id: str, filename: str) -> str:
    return f"{CDN}/{nct_id[-2:]}/{nct_id}/{filename}"


async def download_protocol(nct_id: str, dest_dir: str | None = None) -> str | None:
    """Download the protocol PDF; returns local path, or None if the study has none.

    Streams to a temp file then renames, so a failed download never leaves a partial PDF.
    """
    study = await get_study(nct_id)
    files = protocol_files(study)
    if not files:
        return None
    dest = Path(dest_dir) if dest_dir else CORPUS_DIR
    dest.mkdir(parents=True, exist_ok=True)
    target = dest / f"{nct_id}_protocol.pdf"
    if target.exists() and target.stat().st_size > 0:
        return str(target)
    url = pdf_url(nct_id, files[0])
    tmp = target.with_suffix(".part")
    async with httpx.AsyncClient(timeout=300, follow_redirects=True) as c:
        for attempt in range(3):
            try:
                await _throttle()
                async with c.stream("GET", url) as r:
                    r.raise_for_status()
                    with tmp.open("wb") as f:
                        async for chunk in r.aiter_bytes(1 << 16):
                            f.write(chunk)
                if tmp.read_bytes()[:5] != b"%PDF-":
                    raise ValueError(f"{url} did not return a PDF")
                tmp.replace(target)
                return str(target)
            except (httpx.HTTPError, ValueError):
                tmp.unlink(missing_ok=True)
                if attempt == 2:
                    raise
                await asyncio.sleep(2 ** attempt)
    return None


class VersionsUnavailable(RuntimeError):
    """The registry's record history cannot be fetched by a script (see get_versions)."""


async def get_versions(nct_id: str) -> list[dict]:
    """Registry version history (N7 case studies).

    VERIFIED 2026-10-10: clinicaltrials.gov/api/int/ (the endpoint behind the 'Record History' tab) answers HTTP 403 to
    every non-browser client (any user agent, headers or cookies), the public v2 API has no history route, and the
    Wayback Machine has no snapshots. So this reads a pre-saved file, data/peers/versions/{nct}.json, and raises
    VersionsUnavailable if there is none, instead of returning [] (which would look like 'no changes').
    See data/peers/versions/HOWTO.txt for saving histories from a real browser session.
    """
    cp = CACHE_DIR / "versions" / f"{nct_id}.json"
    if cp.exists():
        return json.loads(cp.read_text())
    async with httpx.AsyncClient(timeout=60, follow_redirects=True) as c:
        await _throttle()
        r = await c.get(f"https://clinicaltrials.gov/api/int/studies/{nct_id}", params={"history": "true"},
                        headers={"Accept": "application/json"})
    if r.status_code != 200:
        raise VersionsUnavailable(
            f"{nct_id}: record history returned HTTP {r.status_code}; save it from a browser into {cp}")
    data = r.json().get("history", {}).get("changes", [])
    cp.parent.mkdir(parents=True, exist_ok=True)
    cp.write_text(json.dumps(data))
    return data
