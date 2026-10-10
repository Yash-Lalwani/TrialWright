# ruff: noqa: E501
from preflight.burden import costs

VERSION, ROWS = costs.load()


def test_every_row_is_labelled_and_numbers_are_sane():
    assert VERSION == "2026-10-10" and len(ROWS) >= 40
    for r in ROWS:
        assert r.source == "assumption"
        assert r.patient_minutes >= 0 and r.site_minutes > 0 and r.cost_usd > 0 and r.keywords
    assert len({r.name for r in ROWS}) == len(ROWS)


def test_visit_overhead_row_exists_and_is_never_name_matched():
    assert any(r.name == costs.VISIT_OVERHEAD for r in ROWS)
    assert costs.match("__visit__", ROWS) is None


def test_matches_real_soa_names_even_with_footnote_letters():
    names = {"Physical Examinationg": "physical examination", "Vital Signsh": "vital signs", "12-Lead ECGk": "12-lead ECG",
             "Tumor Biopsyq": "tumor biopsy", "Pharmacokinetic Samplingn": "pharmacokinetic sampling",
             "Disease Assessment (radiographic imaging)r": "CT scan", "Informed Consent": "informed consent",
             "Thyroid Function Testsl": "thyroid function", "Long-Term Survival Follow-Up Phone Call": "telephone follow-up"}
    for raw, want in names.items():
        got = costs.match(raw, ROWS)
        assert got and got.name == want, (raw, got and got.name)


def test_longest_keyword_wins_and_unknowns_are_none():
    assert costs.match("Tumor Biopsy", ROWS).invasive is True
    assert costs.match("Bone marrow biopsy", ROWS).name == "bone marrow biopsy"   # not the generic 'biopsy'
    assert costs.match("Quarterly team lunch", ROWS) is None


def test_invasive_rows_are_the_expected_kind():
    inv = {r.name for r in ROWS if r.invasive}
    assert {"tumor biopsy", "bone marrow biopsy", "lumbar puncture", "IV infusion of study drug"} <= inv
    assert "hematology" not in inv


def test_keywords_anchor_at_word_start_not_mid_word():
    assert costs.match("Treatment effect review", ROWS) is None            # 'ct' inside 'effect'
    assert costs.match("Navigation training", ROWS) is None                # 'iga' inside 'navigation'
    assert costs.match("Chest CT", ROWS).name == "CT scan"
    assert costs.match("Abdominal CT with contrast", ROWS).name == "CT scan"
