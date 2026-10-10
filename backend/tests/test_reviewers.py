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
                ("biostatistician", finding("receive 400 mg pralsetinib once daily", page=2))]
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
