from preflight.graph.models import Section
from preflight.ingest.m11_map import STUB_TOC, map_sections, match


def sec(title, level=2):
    return Section(id="s", m11_id=None, title=title, level=level, page_start=1, page_end=1, text="x")


def test_match_headings_to_m11():
    cases = {
        "5.1 INCLUSION CRITERIA FOR ALL PARTICIPANTS": "5.1",
        "4.2 Exclusion criteria": "5.2",
        "1.3 Schedule of Assessments": "1.3",
        "9.2 SAMPLE SIZE DETERMINATION": "10.1",
        "8.1 Definition of AEs": None,
        "6.3 TREATMENT ASSIGNMENT": None,
    }
    for title, expected in cases.items():
        assert match(sec(title), STUB_TOC) == expected, title
    assert match(sec("9 STATISTICAL CONSIDERATIONS", level=1), STUB_TOC) == "10"


async def test_map_sections_without_llm():
    out = await map_sections([sec("2.1 Primary Objectives"), sec("Signature Page", 1)], use_llm=False)
    assert [s.m11_id for s in out] == ["3.1", None]
