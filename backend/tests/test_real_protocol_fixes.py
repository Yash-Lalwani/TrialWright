"""Regression tests for false positives found by running a real, amended protocol (TRUNCATE-TB) through Pre-Flight.
Each test pins one fix and also checks that the genuine finding is still reported."""
from types import SimpleNamespace

from preflight.graph.models import NumberFact, Section
from preflight.ingest import entities
from preflight.ingest.pdf import Line
from tests.test_checks import CHECKS, CTX, graph, span


def line(text, page=1):
    return Line(page=page, text=text, bbox=[72, 100, 540, 112], size=11, bold=False)


def arms(*texts):
    return sorted(f.value for f in entities.extract_numbers([line(t) for t in texts]) if f.kind == "arms")


# ---- fix 1: arm counts -------------------------------------------------------------------------------------------
def test_arm_headings_and_labels_are_not_arm_counts():
    assert arms("6.3.3 Arm D: 8 weeks rifapentine, isoniazid", "6.3.5 Arm F: 8 weeks delamanid") == []
    assert arms("Arm 3: 8 weeks of treatment", "regimens B-F: 2 months") == []


def test_a_comparison_inside_a_larger_design_is_not_the_design_size():
    assert arms("the difference between the two arms in the proportion of patients with a satisfactory outcome") == []
    assert arms("results for the two arms will be pooled") == []


def test_a_statement_of_the_design_size_is_still_an_arm_count():
    assert arms("This is a randomised three-arm trial.") == [3.0]
    assert arms("Patients are randomised to 2 treatment arms.") == [2.0]


# ---- fix 2: durations of different regimens ---------------------------------------------------------------------
def duration_issues(*quotes):
    nums = [NumberFact(kind="duration_weeks", value=8.0, unit="weeks", span=span(p, q))
            for p, q in enumerate(quotes, 1)]
    return CHECKS["C6D"].fn(graph(numbers=nums), CTX)


def test_different_named_regimens_may_have_different_durations():
    assert duration_issues("a management strategy using an initial 6 month standard treatment regimen",
                           "a management strategy using an initial 2 month boosted treatment regimen") == []


def test_the_same_duration_stated_two_ways_is_still_reported():
    out = duration_issues("the treatment phase lasts 12 weeks after randomisation",
                          "the treatment phase lasts 18 weeks after randomisation")
    assert len(out) == 1 and "Duration disagrees" in out[0].title


# ---- fix 3: abbreviations -----------------------------------------------------------------------------------------
def abbreviations(lines, sections=()):
    doc = SimpleNamespace(lines=[line(t, p) for p, t in lines])
    return entities.extract_abbreviations(doc, list(sections))["used"]


def test_author_initials_in_references_are_not_abbreviations():
    refs = [(5, "Dawson R, Diacon AH, Everitt D, Donald PR, Burger DA. Efficiency and safety. Lancet 2015; 385:1738"),
            (5, "Dietze R, Hadad DJ, McGee B, Maciel EL. Early and extended bactericidal activity")]
    assert abbreviations(refs) == []
    section = Section(id="s9", m11_id="14", title="References", level=1, page_start=9, page_end=12, text="")
    assert abbreviations([(10, "Smith AH and Jones DJ wrote this up")], [section]) == []


def test_a_real_undefined_abbreviation_is_still_found():
    assert "ULN" in abbreviations([(3, "ALT must be below 3 times the ULN at screening")])


def test_a_short_form_of_a_defined_hyphenated_abbreviation_counts_as_defined():
    lines = [(1, "Patients with multi-drug resistant tuberculosis (MDR-TB) are excluded"),
             (2, "Rifampicin resistant MDR strains were found in the sample")]
    assert "MDR" not in abbreviations(lines)


# ---- the trial's own NCT number ---------------------------------------------------------------------------
def test_nct_comes_from_the_cover_not_from_reference_links():
    assert entities._own_nct("Short Title TRUNCATE-TB NCT #: NCT03474198 Version 2.0") == "NCT03474198"
    assert entities._own_nct("see https://www.clinicaltrials.gov/ct2/show/NCT01994460 and more") is None
    assert entities._own_nct("Short Title Truncate-Tb Nct #: Version 1.0") is None
