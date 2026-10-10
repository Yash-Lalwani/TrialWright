"""Corpus manifest: build from NCT ids, and re-download everything in it (`preflight fetch`)."""
from __future__ import annotations

import csv
from datetime import datetime, timezone
from pathlib import Path

import pymupdf

from . import client

COLUMNS = ["nct_id", "title", "sponsor", "phase", "condition", "pages",
           "source_url", "downloaded_at", "split"]
MANIFEST = client.CORPUS_DIR / "manifest.csv"


async def manifest_row(nct_id: str, split: str) -> dict:
    study = await client.get_study(nct_id)
    pm = study["protocolSection"]
    files = client.protocol_files(study)
    path = await client.download_protocol(nct_id)
    if not path or not files:
        raise RuntimeError(f"{nct_id}: no protocol document")
    with pymupdf.open(path) as d:
        pages = len(d)
    mtime = datetime.fromtimestamp(Path(path).stat().st_mtime, timezone.utc)
    return {
        "nct_id": nct_id,
        "title": pm["identificationModule"]["briefTitle"],
        "sponsor": pm["sponsorCollaboratorsModule"]["leadSponsor"]["name"],
        "phase": "/".join(pm["designModule"].get("phases", [])),
        "condition": "; ".join(pm["conditionsModule"]["conditions"]),
        "pages": pages,
        "source_url": client.pdf_url(nct_id, files[0]),
        "downloaded_at": mtime.strftime("%Y-%m-%d"),
        "split": split,
    }


def write_manifest(rows: list[dict], path: Path = MANIFEST) -> None:
    with path.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=COLUMNS)
        w.writeheader()
        w.writerows(sorted(rows, key=lambda r: (r["split"], r["nct_id"])))


def read_manifest(path: Path = MANIFEST) -> list[dict]:
    with path.open() as f:
        return list(csv.DictReader(f))


async def fetch_corpus(path: Path = MANIFEST, split: str | None = None) -> list[str]:
    """Download every protocol in the manifest (skips files already present)."""
    got = []
    for row in read_manifest(path):
        if split and row["split"] != split:
            continue
        p = await client.download_protocol(row["nct_id"], str(path.parent))
        if p is None:
            raise RuntimeError(f"{row['nct_id']}: protocol not available at source")
        got.append(p)
    return got
