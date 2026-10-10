import asyncio
import httpx
import pytest

from preflight.ctgov import client as c

STUDY = {"protocolSection": {"identificationModule": {"nctId": "NCT03430063"}},
         "documentSection": {"largeDocumentModule": {"largeDocs": [
             {"hasProtocol": False, "filename": "SAP_001.pdf"},
             {"hasProtocol": True, "filename": "Prot_000.pdf"}]}}}


def test_pdf_url_pattern():
    assert c.pdf_url("NCT03430063", "Prot_000.pdf") == \
        "https://cdn.clinicaltrials.gov/large-docs/63/NCT03430063/Prot_000.pdf"


def test_protocol_files_skips_non_protocol():
    assert c.protocol_files(STUDY) == ["Prot_000.pdf"]
    assert c.protocol_files({}) == []


def test_get_study_caches(tmp_path, monkeypatch):
    monkeypatch.setattr(c, "CACHE_DIR", tmp_path)
    calls = []

    def handler(req):
        calls.append(str(req.url))
        return httpx.Response(200, json=STUDY)

    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as cl:
            a = await c._get_json("/studies/NCT03430063", client=cl)
            b = await c._get_json("/studies/NCT03430063", client=cl)
            return a, b

    a, b = asyncio.run(run())
    assert a == b == STUDY and len(calls) == 1


def test_download_rejects_non_pdf(tmp_path, monkeypatch):
    monkeypatch.setattr(c, "CACHE_DIR", tmp_path / "cache")
    (tmp_path / "cache" / "api").mkdir(parents=True)
    monkeypatch.setattr(c, "get_study", lambda n: asyncio.sleep(0, STUDY))

    RealClient = httpx.AsyncClient

    class FakeClient:
        def __init__(self, *a, **k): pass
        async def __aenter__(self): return self
        async def __aexit__(self, *a): pass
        def stream(self, *a, **k):
            transport = httpx.MockTransport(lambda r: httpx.Response(200, content=b"<html>"))
            return RealClient(transport=transport).stream("GET", "http://x/")

    monkeypatch.setattr(c.httpx, "AsyncClient", FakeClient)
    monkeypatch.setattr(c, "_MIN_INTERVAL", 0)
    with pytest.raises(ValueError):
        asyncio.run(c.download_protocol("NCT03430063", str(tmp_path / "out")))
    assert not list((tmp_path / "out").glob("*"))
