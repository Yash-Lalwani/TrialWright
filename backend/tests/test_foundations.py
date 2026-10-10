import pytest
from pydantic import BaseModel

from preflight.checks import registry
from preflight.graph.issues import Issue, Where, Why
from preflight.graph.models import Meta, ProtocolGraph, Stats
from preflight.llm import cache, client


def tiny_graph() -> ProtocolGraph:
    return ProtocolGraph(
        protocol_id="prt_test",
        meta=Meta(title="T", nct_id=None, phase=None, condition=None, sponsor=None,
                  masking=None, allocation=None, n_arms=None, ratio=None),
        sections=[], objectives=[], endpoints=[], criteria=[], min_age=None, max_age=None, arms=[],
        soa=None,
        stats=Stats(sample_size=None, alpha=None, sided=None, power=None, effect_size=None,
                    effect_type=None, control_rate=None, dropout=None, analyses=[]),
        numbers=[], xrefs=[], abbreviations={},
    )


def test_check_decorator_registers_and_runs():
    @registry.check(id="T0", category="consistency", amendment_category="clerical",
                    standard_ref="test", severity="minor")
    def t0(graph, ctx):
        return [Issue(id="iss_t0", check_id="T0", source="rule", category="consistency", severity="minor",
                      title=graph.meta.title, where=Where(section=None, page=1, bbox=None, quote=None),
                      why=Why(explanation="x", standard_ref="test", amendment_category="clerical"),
                      fix=None, confidence=1.0, verified=True)]

    issues = registry.run_checks(tiny_graph(), registry.CheckContext())
    assert [i.id for i in issues if i.check_id == "T0"] == ["iss_t0"]
    del registry.CHECKS["T0"]


class Answer(BaseModel):
    value: int


async def test_replay_hits_cache_and_misses_raise(tmp_path, monkeypatch):
    monkeypatch.setattr(cache, "CACHE_DIR", tmp_path)
    monkeypatch.setenv("LLM_MODE", "replay")
    with pytest.raises(client.LLMCacheMiss):
        await client.complete_json("t", "sys", "user", Answer)

    system = client.json_system("sys", Answer)
    cache.put(cache.key(client.model(), system, "user", "Answer"),
              {"content": '```json\n{"value": 3}\n```', "tokens_in": 1, "tokens_out": 1})
    assert (await client.complete_json("t", "sys", "user", Answer)).value == 3
    assert client._client is None
