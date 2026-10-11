# ruff: noqa: E501
import asyncio
import importlib

import pytest

from preflight.coauthor.models import Brief

draft = importlib.import_module("preflight.coauthor.draft")

BRIEF = Brief(condition="Melanoma", phase="PHASE2", intervention="Drug X 350 mg IV Q3W", comparator="Docetaxel", primary_question="Does Drug X improve ORR vs docetaxel?",
              population="Adults with previously treated advanced melanoma", duration_weeks=52, expected_effect={"type": "proportions", "control": 0.12, "treatment": 0.27}, dropout=0.1)


def with_effect(effect, **kw):
    return Brief.model_validate({**BRIEF.model_dump(), "expected_effect": effect, **kw})


def test_sample_size_matches_the_checker_calculator():
    s = draft.compute_sample_size(BRIEF)
    # 12% vs 27%: h = 2asin(sqrt(.27)) - 2asin(sqrt(.12)) = 0.385; n = 2 (1.96 + 0.842)^2 / h^2 = 105.8 -> 106 per arm; 212 / 0.9 dropout -> 236 enrolled
    assert s.n_total == 236 and s.n_per_arm == 118 and "z-test" in s.method
    assert s.inputs["control"] == 0.12 and s.inputs["treatment"] == 0.27
    assert draft.compute_sample_size(with_effect({"type": "proportions", "control": 0.12})) is None   # not enough to compute: say so, do not guess


def test_without_an_llm_every_section_is_a_template_and_citations_stay_empty(monkeypatch):
    from preflight.llm.client import LLMUnavailable

    async def boom(*a, **k):
        raise LLMUnavailable("no key")
    monkeypatch.setattr("preflight.llm.client.complete_json", boom)
    monkeypatch.setattr(draft.burden, "find_peers", lambda g: None)
    out = asyncio.run(draft.draft_from_brief(BRIEF))
    assert out["llm_used"] is False and out["precedent"]["rows"] == []
    ids = [s["m11_id"] for s in out["sections"]]
    assert ids == ["2.1", "3", "4.1", "5.2", "5.3", "6.1", "10.11"] and all(s["citations"] == [] for s in out["sections"])
    assert "[TBD" in next(s for s in out["sections"] if s["m11_id"] == "5.3")["markdown"]       # unknowns are marked, not invented
    assert out["self_check"]["score"]["overall"] is not None and out["burden"]["per_patient"]["visits"] == 0
    m = out["sample_size"]
    assert f"{m['n_total']} participants" in next(s for s in out["sections"] if s["m11_id"] == "10.11")["markdown"]


def test_citations_are_limited_to_the_precedent_list(monkeypatch):
    from preflight.burden.models import PrecedentRow, PrecedentTable, ThisProtocol

    table = PrecedentTable(this_protocol=ThisProtocol(primary_endpoint="", primary_timeframe="", key_eligibility=[], enrollment=None, n_visits=0),
                           rows=[PrecedentRow(nct_id="NCT00000001", title="T", sponsor="S", phase="PHASE2", similarity=0.5, primary_endpoint="ORR", primary_timeframe="w24", key_eligibility=[], enrollment=50, n_visits=None)])

    async def fake(step, system, user, schema, **k):
        return schema(markdown="Rationale per NCT00000001 and also NCT99999999.")
    monkeypatch.setattr("preflight.llm.client.complete_json", fake)
    sec = asyncio.run(draft._write_section(BRIEF, table, "2.1", "Purpose of Trial", "x"))
    assert sec.citations == ["NCT00000001"] and "NCT99999999" not in sec.markdown and "unverified citation removed" in sec.markdown and sec.source == "llm"


def test_graph_built_from_the_draft_carries_criteria_and_the_computed_sample_size():
    size = draft.compute_sample_size(BRIEF)
    secs = [draft.DraftSection(m11_id="5.2", title="Inclusion", markdown="- Age 18 or older\n- ECOG 0-1", citations=[]), draft.sample_size_section(size, BRIEF)]
    g = draft.build_graph(BRIEF, secs, size)
    assert [c.text for c in g.criteria] == ["Age 18 or older", "ECOG 0-1"] and g.stats.sample_size == size.n_total
    assert [n.value for n in g.numbers] == [size.n_total] and g.meta.condition == "Melanoma" and len(g.arms) == 2


@pytest.mark.parametrize("effect", [{"type": "mean_diff_sd", "effect": 0.5}, {"type": "hazard_ratio", "effect": 0.7, "event_rate": 0.6}])
def test_other_effect_types(effect):
    s = draft.compute_sample_size(with_effect(effect, dropout=None))
    assert s is not None and s.n_total > 0
