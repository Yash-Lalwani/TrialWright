# ruff: noqa: E501
import importlib
import json

from preflight.burden import burden, peers
from tests.test_checks import graph, soa

ps = importlib.import_module("preflight.burden.peer_soa")
FULL = {"v1": {"p1": True, "p2": True, "p3": False}, "v2": {"p1": True, "p2": True, "p3": False}, "v3": {"p1": True, "p2": False, "p3": True}}


def test_summary_marks_unusable_schedules_with_a_reason():
    assert ps.summary("NCT1", graph())["reason"] == "no extractable schedule"
    assert ps.summary("NCT1", graph(soa=soa(FULL)))["reason"] == "schedule too small to trust"      # 3 procedures < MIN_PROCS


def test_summary_of_a_usable_schedule_matches_compute_burden(monkeypatch):
    monkeypatch.setattr(ps, "MIN_PROCS", 1)
    g = graph(soa=soa(FULL))
    rec = ps.summary("NCT1", g)
    rep = burden.compute(g)
    assert rec["usable"] and rec["patient_hours"] == rep.per_patient.patient_hours and rec["visits"] == rep.per_patient.visits


def test_percentiles_use_only_usable_peers_in_the_peer_set_and_need_enough(tmp_path, monkeypatch):
    monkeypatch.setattr(ps, "DIR", tmp_path)
    rep = burden.compute(graph(soa=soa(FULL)))
    own = rep.per_patient
    for i in range(10):
        ps.save({"nct_id": f"NCT{i:08d}", "usable": True, "patient_hours": own.patient_hours + i - 4.5, "procedures_total": own.procedures_total + i - 4.5, "visits": own.visits + i - 4.5})
    ps.save({"nct_id": "NCT99999999", "usable": False, "reason": "x"})
    ps.save({"nct_id": "NCT88888888", "usable": True, "patient_hours": 1e6, "procedures_total": 1e6, "visits": 1e6})   # not in the peer set: ignored
    ids = {f"NCT{i:08d}" for i in range(10)} | {"NCT99999999", "NCT12345678"}
    p = ps.percentiles(rep, ids)
    assert p.n_peers_with_soa == 10 and p.patient_hours == 50.0 and p.visits == 50.0
    assert ps.percentiles(rep, {f"NCT{i:08d}" for i in range(5)}) is None          # < MIN_PEERS: no comparison, not a guess


def test_record_roundtrip(tmp_path, monkeypatch):
    monkeypatch.setattr(ps, "DIR", tmp_path)
    ps.save({"nct_id": "NCT1", "usable": False, "reason": "r"})
    assert ps.load("NCT1")["reason"] == "r" and ps.load("NCT2") is None
    assert json.loads((tmp_path / "NCT1.json").read_text())["usable"] is False
    assert peers.percentile(5, [5, 5]) == 50.0
