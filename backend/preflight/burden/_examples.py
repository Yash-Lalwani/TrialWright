# ruff: noqa: E501
"""Example payloads copied from docs/CONTRACTS.md 4.8 to 4.10. Used by the H2 stubs only."""

BURDEN = {
    "per_patient": {"visits": 18, "procedures_total": 214, "invasive": 6, "patient_hours": 61.5, "site_hours": 88.0, "cost_usd": 18400},
    "by_visit": [
        {"visit": "Screening", "study_day": -28, "patient_minutes": 240, "site_minutes": 310,
         "procedures": ["Informed consent", "CT/MRI", "Hematology", "Chemistry", "ECG"]},
        {"visit": "C1D1", "study_day": 1, "patient_minutes": 300, "site_minutes": 360,
         "procedures": ["Vitals", "PK sample", "Infusion"]},
    ],
    "orphan_procedures": [{"name": "Exploratory skin biopsy", "occurrences": 3, "patient_minutes": 135, "cost_usd": 2100}],
    "peer_percentiles": {"patient_hours": 82, "procedures_total": 77, "visits": 64, "n_peers_with_soa": 24, "scope": "condition"},
    "assumptions": {"file": "data/assumptions/procedure_costs.csv", "version": "2026-10-11"},
}

PEERS = {
    "query": {"condition": "Non-small cell lung cancer", "phase": "PHASE3", "start_year_min": 2015},
    "n": 143,
    "metrics": [
        {"metric": "n_inclusion_criteria", "label": "Inclusion criteria", "value": 14, "percentile": 71, "peer_median": 11,
         "peer_p25": 8, "peer_p75": 15, "distribution": [6, 8, 9, 11, 11, 12, 15, 19]},
        {"metric": "n_exclusion_criteria", "label": "Exclusion criteria", "value": 31, "percentile": 88, "peer_median": 19,
         "peer_p25": 14, "peer_p75": 25, "distribution": [10, 14, 17, 19, 21, 25, 30]},
    ],
    "hotspot_issue_ids": ["iss_19", "iss_20"],
    "trials": [{"nct_id": "NCT00000001", "title": "Study of Drug Y in NSCLC", "sponsor": "Sponsor Co", "phase": "PHASE3",
                "enrollment": 610, "start_date": "2019-03"}],
}

PRECEDENT = {
    "this_protocol": {"primary_endpoint": "ORR per RECIST 1.1", "primary_timeframe": "Week 24",
                      "key_eligibility": ["ECOG 0", "Age 18-75"], "enrollment": 420, "n_visits": 18},
    "rows": [{"nct_id": "NCT00000001", "title": "Study of Drug Y in NSCLC", "sponsor": "Sponsor Co", "phase": "PHASE3",
              "similarity": 0.82, "primary_endpoint": "PFS per RECIST 1.1", "primary_timeframe": "Up to 36 months",
              "key_eligibility": ["ECOG 0-1", "Age 18+"], "enrollment": 610, "n_visits": 14}],
}

# STUB hotspot issues; ids match PEERS["hotspot_issue_ids"]. category/amendment_category follow CONTRACTS 2.
HOTSPOT_ISSUES = [
    {"id": "iss_19", "check_id": "D3", "source": "rule", "category": "amendment_risk", "severity": "major",
     "title": "ECOG 0 only is stricter than 91% of similar trials",
     "where": {"section": "5.2 Inclusion Criteria", "page": 23, "bbox": [72.0, 210.0, 540.0, 232.0], "quote": "ECOG performance status of 0"},
     "related": [],
     "why": {"explanation": "Restricting to ECOG 0 shrinks the eligible pool; 91% of peer trials allow ECOG 0-1. Narrow eligibility is the most common amendment category.",
             "standard_ref": "ICH M11 5.2", "amendment_category": "eligibility"},
     "fix": {"suggestion": "Allow ECOG 0-1 or justify the restriction (peers: NCT00000001, NCT00000002).", "patch": None},
     "confidence": 0.9, "verified": True, "status": "open"},
    {"id": "iss_20", "check_id": "D3", "source": "rule", "category": "amendment_risk", "severity": "minor",
     "title": "31 exclusion criteria is more than 88% of similar trials",
     "where": {"section": "5.3 Exclusion Criteria", "page": 24, "bbox": [72.0, 100.0, 540.0, 120.0], "quote": "Exclusion Criteria"},
     "related": [],
     "why": {"explanation": "Protocols with many exclusion criteria see more eligibility amendments and slower enrollment.",
             "standard_ref": "ICH M11 5.3", "amendment_category": "eligibility"},
     "fix": {"suggestion": "Review exclusion criteria against peers and drop those without a safety rationale.", "patch": None},
     "confidence": 0.8, "verified": True, "status": "open"},
]
