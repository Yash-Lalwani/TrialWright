import pymupdf

from preflight.graph.issues import Issue, Where, Why
from preflight.pipeline import check_graph, ingest_file
from preflight.reviewers.committee import Finding, ReviewerOut
from preflight.reviewers.verifier import attach_fixes, verify
from tests.test_checks import graph


def finding(quote, page=1, explanation="Explained.", title="Unclear dosing text"):
    return Finding(title=title, quote=quote, page=page, section="4.1", category="consistency", severity="major",
                   explanation=explanation, fix="Rewrite it.")


def test_verifier_drops_ungrounded_and_keeps_grounded(tmp_path):
    path = str(tmp_path / "p.pdf")
    doc = pymupdf.open()
    doc.new_page().insert_text((72, 100), "Participants receive 400 mg pralsetinib once daily.", fontsize=11)
    doc.save(path)
    findings = [("clinical_scientist", finding("receive 400 mg pralsetinib once daily")),
                ("clinical_scientist", finding("this sentence is not in the protocol at all")),
                ("biostatistician", finding("receive 400 mg pralsetinib once daily", page=40))]
    issues, stats = verify(findings, graph(), path)
    assert stats == {"ai_findings": 3, "dropped_ungrounded": 2, "shown": 1}
    i = issues[0]
    assert (i.check_id, i.source, i.category, i.severity) == ("C11", "ai:clinical_scientist", "advisory", "advisory")
    assert i.where.page == 1 and len(i.where.bbox) == 4


def test_unknown_numbers_lower_confidence(tmp_path):
    g = graph()
    issues, _ = verify([("biostatistician", finding("abc defgh ijk", explanation="Power should be 90 not 80"))], g,
                       None)
    assert issues == []  # no page text without PDF or sections
    path = str(tmp_path / "p.pdf")
    doc = pymupdf.open()
    doc.new_page().insert_text((72, 100), "The study has 80% power.", fontsize=11)
    doc.save(path)
    issues, _ = verify([("biostatistician", finding("The study has 80% power", explanation="Use 90 not 80"))], g,
                       path)
    assert issues[0].confidence == 0.4


def test_rules_win_over_matching_ai_finding():
    rule = Issue(id="", check_id="C4", source="rule", category="consistency", severity="major",
                 title="Unclear dosing text in section 6", where=Where(section=None, page=3, bbox=None, quote=None),
                 why=Why(explanation="x", standard_ref=None, amendment_category="clerical"), fix=None,
                 confidence=1, verified=True)
    ai = rule.model_copy(update={"check_id": "C11", "source": "ai:medical_writer", "title": "Unclear dosing text",
                                 "fix": rule.fix})
    from preflight.graph.issues import Fix
    ai.fix = Fix(suggestion="State the dose once.")
    assert attach_fixes([rule], [ai]) == [] and rule.fix.suggestion == "State the dose once."


async def test_full_mode_runs_committee_and_verifier(tmp_path, monkeypatch):
    from tests.test_ingest_sections import make_pdf

    path = str(tmp_path / "p.pdf")
    make_pdf(path)
    calls = []

    async def fake(step, system, user, schema, temperature=0):
        calls.append(step)
        if schema is ReviewerOut:
            return ReviewerOut(findings=[finding("The primary objective is ORR at Week 24", page=3,
                                                 title="Primary objective lacks an estimand")])
        raise AssertionError(f"unexpected LLM step {step}")

    monkeypatch.setattr("preflight.llm.client.complete_json", fake)
    g = await ingest_file(path, use_llm=False)
    g = g.model_copy(update={"sections": [s.model_copy(update={"m11_id": "3"}) if s.title.startswith("2 ") else s
                                          for s in g.sections]})
    result = await check_graph(g, "full", pdf_path=path)
    assert any(c.startswith("reviewer:") for c in calls)
    ai = [i for i in result.issues if i.source.startswith("ai:")]
    assert ai and all(i.severity == "advisory" for i in ai)
    assert result.verifier["ai_findings"] >= 1 and result.verifier["shown"] == len(ai)


async def test_rules_only_never_touches_llm(tmp_path, monkeypatch):
    from tests.test_ingest_sections import make_pdf

    async def boom(*a, **k):
        raise AssertionError("LLM called in rules_only mode")

    monkeypatch.setattr("preflight.llm.client.complete_json", boom)
    path = str(tmp_path / "p.pdf")
    make_pdf(path)
    result = await check_graph(await ingest_file(path, use_llm=False), "rules_only", pdf_path=path)
    assert result.verifier is None


def test_quote_on_a_nearby_page_is_relocated_and_soa_rows_ground_on_the_name(tmp_path):
    path = str(tmp_path / "p.pdf")
    doc = pymupdf.open()
    doc.new_page().insert_text((72, 100), "Section 5 Eligibility", fontsize=11)
    doc.new_page().insert_text((72, 100), "Participants with active CNS metastases are excluded.", fontsize=11)
    doc.new_page().insert_text((72, 100), "Urinalysis", fontsize=11)
    doc.save(path)
    from preflight.graph.models import Procedure, SoA, Span

    soa = SoA(visits=[], procedures=[Procedure(id="p1", name="Urinalysis", normalized_name="urinalysis")], cells={},
              span=Span(page=3, bbox=None, quote="SoA"))
    issues, stats = verify([("clinical_scientist", finding("Participants with active CNS metastases are excluded", 1)),
                            ("clinical_ops", finding("Urinalysis | X | X |  | X", page=3)),
                            ("clinical_ops", finding("excluded", page=2))], graph(soa=soa), path)
    assert stats["dropped_ungrounded"] == 1  # a one-word quote that is not an SoA procedure
    assert [i.where.page for i in issues] == [2, 3]
    assert issues[1].where.quote == "Urinalysis"


def test_reused_quote_supports_only_the_first_finding(tmp_path):
    path = str(tmp_path / "p.pdf")
    doc = pymupdf.open()
    doc.new_page().insert_text((72, 100), "The Sponsor has decided to terminate the study early.", fontsize=11)
    doc.save(path)
    q = "The Sponsor has decided to terminate the study early"
    issues, stats = verify([("medical_writer", finding(q, title="Termination not reflected")),
                            ("medical_writer", finding(q, title="No stopping rules"))], graph(), path)
    assert [i.title for i in issues] == ["Termination not reflected"] and stats["dropped_ungrounded"] == 1
