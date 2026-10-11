# ruff: noqa: E501
from fastapi.testclient import TestClient

from preflight.api.main import app
from preflight.api.routes import benchmark
from preflight.db import IssueRow, Protocol, Run, now, session
from tests.test_checks import graph


def res(set_, config, recall, stamp):
    return {"set": set_, "config": config, "generated_at": stamp, "llm_enabled": config != "rules_only", "test_set": {"protocols": 3, "injected_errors": 10},
            "overall": {"recall": recall, "precision": 0.9, "f1": 0.8}, "by_type": [], "by_category": [], "false_alarms_per_clean_protocol": 1.0}


def test_headline_prefers_test_over_dev_and_full_over_rules_only():
    rs = [res("dev", "full", 0.9, "2026-10-12T00:00:00Z"), res("test", "rules_only", 0.5, "2026-10-11T00:00:00Z"), res("test", "full", 0.7, "2026-10-10T00:00:00Z")]
    assert benchmark.headline(rs)["config"] == "full" and benchmark.headline(rs)["set"] == "test"
    body = benchmark.shape(rs)
    assert body["set"] == "test" and [a["config"] for a in body["ablation"]] == ["rules_only", "full"]   # dev results never mix into a test ablation
    assert body["human_baseline"] is None and body["hallucination"] is None                             # missing sections stay null


def test_no_results_means_none():
    assert benchmark.shape([]) is None


def test_benchmark_404_without_results(monkeypatch, tmp_path):
    monkeypatch.setattr(benchmark, "RESULTS_DIR", tmp_path)
    with TestClient(app) as c:
        assert c.get("/api/benchmark").status_code == 404


def test_run_routes_404_unknown_and_409_without_graph():
    with TestClient(app) as c:
        assert c.get("/api/runs/run_nope/burden").status_code == 404
        with session() as s:
            s.add(Protocol(id="prt_b1", filename="x.pdf", path="x.pdf", graph=None))
            s.add(Run(id="run_b1", protocol_id="prt_b1", status="queued", started_at=now()))
            s.commit()
        for ep in ("burden", "peers", "precedent"):
            assert c.get(f"/api/runs/run_b1/{ep}").status_code == 409


def test_burden_and_precedent_work_from_stored_graph_and_peers_lists_hotspot_ids(monkeypatch):
    from preflight import burden
    monkeypatch.setattr(burden, "find_peers", lambda g: None)
    g = graph()
    with TestClient(app) as c:
        with session() as s:
            s.add(Protocol(id="prt_b2", filename="x.pdf", path="x.pdf", graph=g.model_dump()))
            s.add(Run(id="run_b2", protocol_id="prt_b2", status="complete", started_at=now()))
            s.add(IssueRow(id="iss_01", run_id="run_b2", data={"check_id": "D3"}))
            s.commit()
        assert set(c.get("/api/runs/run_b2/burden").json()) >= {"per_patient", "by_visit", "orphan_procedures", "assumptions"}
        assert c.get("/api/runs/run_b2/precedent").json()["rows"] == []                  # no peers: empty table, not invented rows
        assert c.get("/api/runs/run_b2/peers").status_code == 404                         # no peers: said plainly
        monkeypatch.setattr(burden, "find_peers", lambda g: burden.PeerSet.model_validate(burden._examples.PEERS))
        assert c.get("/api/runs/run_b2/peers").json()["hotspot_issue_ids"] == ["iss_01"]


def test_draft_roundtrip_without_llm_and_exports(monkeypatch):
    import time

    from preflight import burden
    from preflight.llm.client import LLMUnavailable

    async def boom(*a, **k):
        raise LLMUnavailable("no key")
    monkeypatch.setattr("preflight.llm.client.complete_json", boom)
    monkeypatch.setattr(burden, "find_peers", lambda g: None)
    brief = {"condition": "Melanoma", "phase": "PHASE2", "intervention": "Drug X 350 mg IV Q3W", "comparator": "Docetaxel", "primary_question": "Does Drug X improve ORR?",
             "population": "Adults with advanced melanoma", "duration_weeks": 52, "expected_effect": {"type": "proportions", "control": 0.12, "treatment": 0.27}, "dropout": 0.1}
    with TestClient(app) as c:
        r = c.post("/api/drafts", json=brief)
        assert r.status_code == 202 and r.json()["status"] == "queued"
        did = r.json()["draft_id"]
        for _ in range(100):
            d = c.get(f"/api/drafts/{did}").json()
            if d["status"] != "queued":
                break
            time.sleep(0.1)
        assert d["status"] == "complete" and d["sample_size"]["n_total"] == 236
        assert {"precedent", "sections", "burden", "self_check", "brief"} <= set(d)
        assert "event: complete" in c.get(f"/api/drafts/{did}/events").text
        assert c.get(f"/api/drafts/{did}/export?format=docx").content[:2] == b"PK"
        assert c.get(f"/api/drafts/{did}/export?format=usdm").json()
        assert c.get("/api/drafts/drf_nope").status_code == 404 and c.get(f"/api/drafts/{did}/export?format=zip").status_code == 422
        assert c.post("/api/drafts", json={"condition": "x"}).status_code == 422
