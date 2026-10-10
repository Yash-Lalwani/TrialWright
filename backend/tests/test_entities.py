from preflight.graph.models import Section
from preflight.ingest import entities
from preflight.ingest.pdf import Line
from preflight.pipeline import ingest_file
from tests.test_ingest_sections import make_pdf


def line(text, page=1):
    return Line(page=page, text=text, bbox=[72, 100, 540, 112], size=11, bold=False)


def facts_for(*texts):
    return {(f.kind, f.value) for f in entities.extract_numbers([line(t) for t in texts])}


def test_regex_numbers():
    facts = facts_for(
        "Aged ≥ 18 years and ≤ 75 years;",
        "Participants aged 18 to 80 years",
        "Approximately 226 participants are planned to be enrolled and randomized in a 1:1 ratio",
        "This is a Phase III, randomized, open-label, two-arm study",
        "Pralsetinib 400 mg will be administered orally once daily",
        "The duration of treatment is 24 months",
    )
    assert {("age_min", 18.0), ("age_max", 75.0), ("age_max", 80.0), ("sample_size", 226.0), ("ratio", "1:1"),
            ("arms", 2.0), ("dose", 400.0), ("duration_weeks", 104.0)} <= facts


def test_background_and_references_are_excluded():
    intro = Section(id="s1", m11_id="2", title="1 BACKGROUND", level=1, page_start=1, page_end=1, text="")
    design = Section(id="s2", m11_id="4", title="3 STUDY DESIGN", level=1, page_start=2, page_end=2, text="")
    parts = [(intro, [line("A total of 614 patients were randomized in a 2:1 ratio")]),
             (design, [line("Approximately 300 patients will be randomized in a 1:1 ratio", 2)])]
    facts = {(f.kind, f.value) for f in entities.extract_numbers(entities.body_lines(parts))}
    assert facts == {("sample_size", 300.0), ("ratio", "1:1")}


def test_xrefs_and_abbreviations():
    lines = [line("Adverse events (AE) are defined in detail (see Section 8.6.1)."),
             line("Monitor ALT and AST weekly per the AE schedule.")]
    assert [x["target"] for x in entities.extract_xrefs(lines)] == ["Section 8.6.1"]

    class Doc:
        pass

    doc = Doc()
    doc.lines = lines
    abbr = entities.extract_abbreviations(doc, [])
    assert abbr["defined"] == {"AE": "Adverse events"}
    assert abbr["used"] == ["AE", "ALT", "AST"]


async def test_extract_llm_assembles_graph_parts(monkeypatch):
    async def fake(step, system, user, schema, temperature=0):
        data = {
            "extract_objectives": {"objectives": [{
                "level": "primary", "text": "Compare PFS", "quote": "compare PFS",
                "endpoints": [{"text": "PFS per RECIST 1.1", "measure": "PFS", "timepoints_weeks": [24],
                               "quote": "PFS per RECIST"}]}]},
            "extract_criteria": {"criteria": [{"kind": "inclusion", "text": "ANC >= 1.5", "quote": "ANC",
                                               "thresholds": [{"test": "ANC", "op": ">=", "value": 1.5,
                                                               "unit": "10^9/L"}]}]},
            "extract_stats": {"sample_size": 300, "alpha": 0.05, "power": 0.8,
                              "analyses": [{"endpoint_ids": ["ep_1"], "method": "Log-rank", "quote": "log-rank"}]},
            "extract_design": {"condition": "NSCLC", "arms": [{"name": "A", "type": "experimental", "dose": None,
                                                               "route": None, "frequency": None,
                                                               "duration_weeks": None}]},
        }[step]
        return schema.model_validate(data)

    monkeypatch.setattr("preflight.llm.client.complete_json", fake)
    sec = lambda m11, page: Section(id=m11, m11_id=m11, title=m11, level=1, page_start=page, page_end=page, text="x")  # noqa: E731
    parts = [(sec("3", 5), [line("The primary objective is to compare PFS per RECIST 1.1", 5)]),
             (sec("5.2", 9), [line("ANC ≥ 1.5 × 10^9/L", 9)]),
             (sec("10", 20), [line("PFS will be compared using a stratified log-rank test", 20)]),
             (sec("4.1", 3), [line("Arm A receives drug", 3)])]
    out = await entities.extract_llm(parts)
    assert out["endpoints"][0].analysis_ids == ["ana_1"] and out["endpoints"][0].span.page == 5
    assert out["criteria"][0].id == "inc_1" and out["criteria"][0].span.page == 9
    assert out["stats"].analyses[0]["endpoint_id"] == "ep_1" and out["condition"] == "NSCLC"


async def test_ingest_file_rules_only_and_json_roundtrip(tmp_path):
    pdf = str(tmp_path / "p.pdf")
    make_pdf(pdf)
    graph = await ingest_file(pdf, nct_id="NCT00000000", use_llm=False)
    assert graph.protocol_id.startswith("prt_") and graph.meta.nct_id == "NCT00000000"
    assert [s.title for s in graph.sections][0] == "1 INTRODUCTION"

    js = tmp_path / "g.json"
    js.write_text(graph.model_dump_json())
    assert (await ingest_file(str(js))).model_dump() == graph.model_dump()
