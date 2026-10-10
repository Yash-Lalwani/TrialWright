from fastapi.testclient import TestClient

from preflight.api.main import app
from preflight.api.stubs import example
from preflight.graph.issues import Issue

client = TestClient(app)

GET_ROUTES = {
    "/api/health": "health",
    "/api/protocols": "protocols_list",
    "/api/runs/run_31c9": "run",
    "/api/protocols/prt_8f2a/runs": "runs_list",
    "/api/runs/run_31c9/issues": "issues",
    "/api/runs/run_31c9/completeness": "completeness",
    "/api/runs/run_31c9/diff/run_52aa": "diff",
    "/api/runs/run_31c9/trace": "trace",
}


def test_get_routes_match_contract():
    for path, name in GET_ROUTES.items():
        r = client.get(path)
        assert r.status_code == 200, path
        assert set(r.json()) == set(example(name)), path


def test_issue_example_fits_model():
    for item in client.get("/api/runs/run_31c9/issues").json()["items"]:
        Issue.model_validate(item)


def test_post_routes():
    r = client.post("/api/protocols", files={"file": ("p.pdf", b"%PDF-1.4", "application/pdf")})
    assert r.status_code == 201 and set(r.json()) == set(example("protocol"))
    r = client.post("/api/protocols/prt_8f2a/runs", json={"mode": "full", "version_label": "v1"})
    assert r.status_code == 202 and r.json() == {"run_id": "run_31c9", "status": "queued"}
    decision = {"decision": "accepted", "note": "x", "user": "reviewer"}
    r = client.post("/api/issues/iss_01/decision", json=decision)
    assert set(r.json()) == {"issue_id", "status", "audit_id", "score"}


def test_events_stream_steps_in_order():
    body = client.get("/api/runs/run_31c9/events").text
    assert body.index('"step": "ingest"') < body.index('"step": "score"')
    assert body.rstrip().endswith('{"run_id": "run_31c9"}')


def test_exports_and_pdf():
    for fmt in ["usdm", "docx", "report_pdf", "report_csv"]:
        r = client.get(f"/api/runs/run_31c9/export?format={fmt}")
        assert r.status_code == 200 and "attachment" in r.headers["content-disposition"]
    assert client.get("/api/protocols/prt_8f2a/pdf").content.startswith(b"%PDF")


def test_error_shape():
    r = client.get("/api/runs/run_31c9/export?format=nope")
    assert r.status_code == 422 and set(r.json()["error"]) == {"code", "message"}
