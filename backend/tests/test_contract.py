import time

import pytest
from fastapi.testclient import TestClient

from preflight.api.main import app
from preflight.api.stubs import example
from preflight.graph.issues import Issue
from tests.test_ingest_sections import make_pdf
from tests.test_soa import make_soa_pdf


def same_keys(actual, expected, path="$"):
    if isinstance(expected, dict) and isinstance(actual, dict):
        assert set(actual) == set(expected), f"{path}: {sorted(set(actual) ^ set(expected))}"
        for k in expected:
            if actual[k] is not None and expected[k] is not None:
                same_keys(actual[k], expected[k], f"{path}.{k}")
    elif isinstance(expected, list) and isinstance(actual, list) and expected and actual:
        same_keys(actual[0], expected[0], f"{path}[0]")


@pytest.fixture(scope="module")
def run(tmp_path_factory):
    import pymupdf

    tmp = tmp_path_factory.mktemp("pdf")
    make_pdf(str(tmp / "protocol.pdf"))
    make_soa_pdf(str(tmp / "soa.pdf"))
    doc = pymupdf.open(str(tmp / "protocol.pdf"))
    doc.insert_pdf(pymupdf.open(str(tmp / "soa.pdf")))
    doc.save(str(tmp / "both.pdf"))
    both = tmp / "both.pdf"

    with TestClient(app) as client:
        r = client.post("/api/protocols", files={"file": ("NCT00000000_protocol.pdf", both.read_bytes(),
                                                          "application/pdf")}, data={"nct_id": "NCT00000000"})
        assert r.status_code == 201, r.text
        protocol = r.json()
        r = client.post(f"/api/protocols/{protocol['protocol_id']}/runs", json={"mode": "rules_only",
                                                                               "version_label": "v1"})
        assert r.status_code == 202
        run_id = r.json()["run_id"]
        events = client.get(f"/api/runs/{run_id}/events").text
        for _ in range(100):
            if client.get(f"/api/runs/{run_id}").json()["status"] in ("complete", "failed"):
                break
            time.sleep(0.1)
        yield client, protocol, run_id, events


def test_health():
    with TestClient(app) as client:
        same_keys(client.get("/api/health").json(), example("health"))


def test_upload_and_list(run):
    client, protocol, run_id, _ = run
    same_keys(protocol, example("protocol"))
    assert protocol["nct_id"] == "NCT00000000" and protocol["pages"] == 4
    listing = client.get("/api/protocols").json()
    same_keys(listing, example("protocols_list"))
    assert listing["items"][0]["latest_run"]["run_id"] == run_id
    assert client.get(f"/api/protocols/{protocol['protocol_id']}/pdf").content.startswith(b"%PDF")


def test_events_follow_contract_order(run):
    _, _, run_id, events = run
    steps = [line.split('"step": "')[1].split('"')[0] for line in events.splitlines() if '"step"' in line]
    assert steps == ["ingest", "map_sections", "extract_soa", "extract_entities", "rules", "reviewers", "verify",
                     "burden", "peers", "score"]
    assert '"step": "reviewers", "status": "skipped"' in events
    assert events.rstrip().endswith(f'{{"run_id": "{run_id}"}}')


def test_run_issues_completeness(run):
    client, protocol, run_id, _ = run
    r = client.get(f"/api/runs/{run_id}").json()
    assert r["status"] == "complete", r
    same_keys(r, example("run"))
    same_keys(client.get(f"/api/protocols/{protocol['protocol_id']}/runs").json(), example("runs_list"))

    issues = client.get(f"/api/runs/{run_id}/issues").json()
    same_keys(issues, example("issues"))
    assert issues["total"] == len(issues["items"]) > 0
    for item in issues["items"]:
        Issue.model_validate(item)
    sev = issues["items"][0]["severity"]
    assert all(i["severity"] == sev for i in client.get(f"/api/runs/{run_id}/issues?severity={sev}").json()["items"])
    same_keys(client.get(f"/api/runs/{run_id}/completeness").json(), example("completeness"))


def test_decision_updates_score_and_audit(run):
    client, _, run_id, _ = run
    issues = client.get(f"/api/runs/{run_id}/issues").json()["items"]
    target = next((i for i in issues if i["category"] == "consistency" and i["severity"] != "advisory"), issues[0])
    before = client.get(f"/api/runs/{run_id}").json()["score"]
    r = client.post(f"/api/issues/{target['id']}/decision",
                    json={"decision": "accepted", "note": "fixed", "user": "reviewer"}).json()
    same_keys(r, example("decision"))
    if target["category"] == "consistency":
        assert r["score"]["consistency"] > before["consistency"]
    trace = client.get(f"/api/runs/{run_id}/trace").json()
    same_keys(trace, example("trace"))
    assert trace["audit"][-1]["issue_id"] == target["id"] and len(trace["steps"]) == 10


def test_diff_between_runs(run):
    client, protocol, run_id, _ = run
    r = client.post(f"/api/protocols/{protocol['protocol_id']}/runs", json={"mode": "rules_only"}).json()
    for _ in range(100):
        if client.get(f"/api/runs/{r['run_id']}").json()["status"] == "complete":
            break
        time.sleep(0.1)
    diff = client.get(f"/api/runs/{run_id}/diff/{r['run_id']}").json()
    same_keys(diff, example("diff"))
    assert diff["resolved"] == [] and diff["new"] == [] and len(diff["unchanged"]) > 0


def test_exports_and_errors(run):
    client, _, run_id, _ = run
    for fmt, magic in [("usdm", b"{"), ("docx", b"PK"), ("report_pdf", b"%PDF"), ("report_csv", b"id,")]:
        r = client.get(f"/api/runs/{run_id}/export?format={fmt}")
        assert r.status_code == 200 and "attachment" in r.headers["content-disposition"]
        assert r.content.startswith(magic), fmt
    r = client.get("/api/runs/run_missing")
    assert r.status_code == 404 and r.json() == {"error": {"code": "not_found", "message": "Run run_missing not found"}}
    r = client.post("/api/protocols", files={"file": ("x.txt", b"hello", "text/plain")})
    assert r.status_code == 400 and r.json()["error"]["code"] == "bad_request"
