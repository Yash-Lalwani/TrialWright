// Mock issues for the synthetic sample protocol. Every `where` / `related` entry
// names an anchor from document.mjs; the generator fills in page and bbox from the
// rendered PDF and fails if the quote is not found verbatim in the anchor text.
// Shape matches CONTRACTS.md §4.4 once generated.
//
// Mix: 3 critical, 7 major, 6 minor, 4 advisory; 17 open, 2 accepted, 1 rejected;
// every category and every source appears at least once.

export const issues = [
  {
    id: "iss_01",
    check_id: "C1",
    source: "rule",
    category: "consistency",
    severity: "critical",
    title: "Primary endpoint at Week 24 has no Week 24 tumor assessment in the Schedule of Activities",
    where: { anchor: "soa_imaging", section: "1.3 Schedule of Activities", quote: "Tumor imaging (CT/MRI)" },
    related: [
      {
        anchor: "obj_primary",
        section: "3.1 Primary Objective",
        quote: "Objective response rate at Week 24 per RECIST 1.1",
      },
    ],
    why: {
      explanation:
        "The primary endpoint is measured at Week 24, but the Schedule of Activities has no tumor imaging at Week 24. Imaging is scheduled at Week 18 and Week 25 instead. Sites will not collect the primary endpoint as written.",
      standard_ref: "ICH M11 1.3, 3; SPIRIT 2025 item 13",
      amendment_category: "visit_schedule",
    },
    fix: {
      suggestion:
        "Add tumor imaging (CT/MRI) to the Week 24 visit, or change the endpoint timepoint to the nearest scheduled imaging visit (Week 25).",
      patch: { op: "set_soa_cell", visit: "W24", procedure: "Tumor imaging (CT/MRI)", value: true },
    },
    confidence: 0.95,
    verified: true,
    status: "open",
  },
  {
    id: "iss_02",
    check_id: "C7",
    source: "rule",
    category: "consistency",
    severity: "critical",
    title: "Stated sample size (420) is below the 492 required by the stated assumptions",
    where: {
      anchor: "sample_size",
      section: "10.2 Sample Size Determination",
      quote: "approximately 420 participants (210 per arm) will be randomized",
    },
    related: [{ anchor: "syn_n", section: "1.1 Synopsis", quote: "Approximately 420 participants (210 per arm)." }],
    why: {
      explanation:
        "A two-sided two-proportion z-test with alpha 0.05, 80% power and ORR 12% vs 22% needs 221 participants per arm. Inflating for 10% dropout gives 246 per arm, 492 in total. The stated 420 is 15% lower, so the study is underpowered for the stated effect.",
      standard_ref: "ICH M11 10; ICH E9",
      amendment_category: "statistics",
    },
    fix: {
      suggestion:
        "Increase enrollment to 492 participants (246 per arm), or restate the assumptions (effect size, power or dropout) that support 420.",
      patch: { op: "set_number", kind: "sample_size", value: 492 },
    },
    confidence: 0.97,
    verified: true,
    status: "open",
  },
  {
    id: "iss_03",
    check_id: "C8",
    source: "rule",
    category: "consistency",
    severity: "critical",
    title: "Inclusion and exclusion ANC thresholds contradict each other",
    where: {
      anchor: "exc_anc",
      section: "5.2 Exclusion Criteria",
      quote: "Absolute neutrophil count (ANC) < 2.0 x10^9/L at screening.",
    },
    related: [
      {
        anchor: "inc_anc",
        section: "5.1 Inclusion Criteria",
        quote: "absolute neutrophil count (ANC) >= 1.5 x10^9/L",
      },
    ],
    why: {
      explanation:
        "Inclusion criterion 6 admits participants with ANC from 1.5 x10^9/L, but exclusion criterion 2 removes anyone below 2.0 x10^9/L. Candidates with ANC between 1.5 and 1.99 are both eligible and excluded, and sites will apply the rule inconsistently.",
      standard_ref: "ICH M11 5.1, 5.2",
      amendment_category: "eligibility",
    },
    fix: {
      suggestion:
        "Use one ANC threshold. Either delete exclusion criterion 2 or change inclusion criterion 6 to ANC >= 2.0 x10^9/L.",
      patch: { op: "delete_criterion", kind: "exclusion", index: 2 },
    },
    confidence: 0.96,
    verified: true,
    status: "open",
  },
  {
    id: "iss_04",
    check_id: "C4",
    source: "rule",
    category: "consistency",
    severity: "major",
    title: "Upper age limit differs between Synopsis (75) and Inclusion Criteria (80)",
    where: { anchor: "inc_age", section: "5.1 Inclusion Criteria", quote: "Age 18 to 80 years" },
    related: [{ anchor: "syn_population", section: "1.1 Synopsis", quote: "Adults aged 18 to 75 years" }],
    why: {
      explanation:
        "The Synopsis limits enrollment to 18 to 75 years while inclusion criterion 1 allows 18 to 80. Registry entries, consent forms and site screening logs will disagree.",
      standard_ref: "ICH M11 1.1, 5.1",
      amendment_category: "eligibility",
    },
    fix: {
      suggestion: "Choose one upper age limit and use it in both the Synopsis and inclusion criterion 1.",
      patch: { op: "set_number", kind: "age_max", value: 75 },
    },
    confidence: 0.94,
    verified: true,
    status: "open",
  },
  {
    id: "iss_05",
    check_id: "C4",
    source: "rule",
    category: "consistency",
    severity: "major",
    title: "Drug X dose differs between Synopsis (300 mg) and Section 6.1 (350 mg)",
    where: { anchor: "dose_sec6", section: "6.1 Description of Trial Intervention", quote: "Drug X 350 mg" },
    related: [{ anchor: "syn_dose", section: "1.1 Synopsis", quote: "Drug X 300 mg IV every 3 weeks (Q3W)." }],
    why: {
      explanation:
        "The intervention dose is stated as 300 mg in the Synopsis and 350 mg in Section 6.1. Pharmacy manuals and the IRT system cannot be configured until one dose is confirmed.",
      standard_ref: "ICH M11 1.1, 6.1",
      amendment_category: "intervention",
    },
    fix: { suggestion: "Confirm the intended dose and correct the other section.", patch: null },
    confidence: 0.93,
    verified: true,
    status: "open",
  },
  {
    id: "iss_06",
    check_id: "C6",
    source: "rule",
    category: "consistency",
    severity: "major",
    title: "Treatment (48 weeks) plus follow-up (12 weeks) does not equal the stated 52-week duration",
    where: {
      anchor: "design_duration",
      section: "4.1 Overall Design",
      quote: "The total duration of participation is 52 weeks",
    },
    related: [],
    why: {
      explanation:
        "Section 4.1 describes up to 48 weeks of treatment and 12 weeks of follow-up, which is 60 weeks, but states a total of 52 weeks.",
      standard_ref: "ICH M11 4.1",
      amendment_category: "design",
    },
    fix: {
      suggestion: "Change the total duration to 60 weeks, or shorten the treatment or follow-up period.",
      patch: { op: "set_number", kind: "duration_weeks", value: 60 },
    },
    confidence: 0.92,
    verified: true,
    status: "open",
  },
  {
    id: "iss_07",
    check_id: "C3",
    source: "rule",
    category: "completeness",
    severity: "minor",
    title: "Secondary endpoint PFS has no analysis in the Statistical Considerations",
    where: {
      anchor: "obj_pfs",
      section: "3.2 Secondary Objectives",
      quote: "To compare progression-free survival (PFS) per RECIST 1.1.",
    },
    related: [
      {
        anchor: "secondary_analysis",
        section: "10.5 Secondary Endpoint Analyses",
        quote: "Overall survival will be compared using a stratified log-rank test.",
      },
    ],
    why: {
      explanation:
        "Section 10.5 describes analyses for overall survival and duration of response but none for progression-free survival, which is a stated secondary objective.",
      standard_ref: "ICH M11 3, 10",
      amendment_category: "statistics",
    },
    fix: {
      suggestion:
        "Add a PFS analysis to Section 10.5 (for example, a stratified log-rank test with Kaplan-Meier estimates), or remove PFS from the secondary objectives.",
      patch: null,
    },
    confidence: 0.91,
    verified: true,
    status: "open",
  },
  {
    id: "iss_08",
    check_id: "B1",
    source: "rule",
    category: "completeness",
    severity: "major",
    title: "Estimand attributes are not described for the primary objective",
    where: {
      anchor: "estimands",
      section: "3.3 Estimands",
      quote: "The primary estimand will be described in the statistical analysis plan.",
    },
    related: [],
    why: {
      explanation:
        "ICH M11 expects the protocol itself to define the estimand for each primary objective: population, variable, intercurrent events and their handling, and population-level summary. Section 3.3 defers all of these to the statistical analysis plan.",
      standard_ref: "ICH M11 3; ICH E9(R1)",
      amendment_category: "completeness",
    },
    fix: {
      suggestion:
        "Define the primary estimand in Section 3.3, including how treatment discontinuation and new anticancer therapy are handled.",
      patch: null,
    },
    confidence: 0.9,
    verified: true,
    status: "open",
  },
  {
    id: "iss_09",
    check_id: "C11",
    source: "ai:biostatistician",
    category: "consistency",
    severity: "major",
    title: "Primary analysis uses the per-protocol population, but Section 10.3 names ITT as primary",
    where: {
      anchor: "primary_analysis",
      section: "10.4 Primary Endpoint Analysis",
      quote: "ORR will be compared between arms in the per-protocol population",
    },
    related: [
      {
        anchor: "pop_itt",
        section: "10.3 Analysis Populations",
        quote: "The ITT population is the primary population for efficacy analyses.",
      },
    ],
    why: {
      explanation:
        "Section 10.3 states that ITT is the primary efficacy population, yet Section 10.4 runs the primary analysis on the per-protocol population. In a superiority trial the per-protocol analysis can overstate the treatment effect, and regulators will expect ITT as primary.",
      standard_ref: "ICH E9",
      amendment_category: "statistics",
    },
    fix: {
      suggestion:
        "Run the primary analysis on the ITT population and keep the per-protocol analysis as a sensitivity analysis.",
      patch: null,
    },
    confidence: 0.84,
    verified: true,
    status: "open",
  },
  {
    id: "iss_10",
    check_id: "C11",
    source: "ai:clinical_scientist",
    category: "consistency",
    severity: "major",
    title: "Brain metastases are both allowed (if treated) and excluded (any history)",
    where: { anchor: "exc_brain", section: "5.2 Exclusion Criteria", quote: "Any history of brain metastases." },
    related: [
      {
        anchor: "inc_brain",
        section: "5.1 Inclusion Criteria",
        quote: "Participants with brain metastases are eligible if the metastases were treated",
      },
    ],
    why: {
      explanation:
        "Inclusion criterion 7 admits participants with treated, stable brain metastases, while exclusion criterion 4 removes anyone with any history of brain metastases. The exclusion makes the inclusion criterion unreachable.",
      standard_ref: "ICH M11 5.1, 5.2",
      amendment_category: "eligibility",
    },
    fix: {
      suggestion:
        "Change exclusion criterion 4 to 'Untreated or symptomatic brain metastases' so it matches inclusion criterion 7.",
      patch: null,
    },
    confidence: 0.86,
    verified: true,
    status: "open",
  },
  {
    id: "iss_11",
    check_id: "C9",
    source: "rule",
    category: "consistency",
    severity: "minor",
    title: "Cross-reference to Section 12.4 points to a section that does not exist",
    where: { anchor: "xref", section: "6.4 Concomitant Therapy", quote: "listed in Section 12.4" },
    related: [],
    why: {
      explanation: "Section 12 ends at 12.3. The list of prohibited and permitted medications is missing or misnumbered.",
      standard_ref: "ICH M11 6.4",
      amendment_category: "clerical",
    },
    fix: {
      suggestion: "Add Section 12.4 with the concomitant medication lists, or correct the reference.",
      patch: null,
    },
    confidence: 0.99,
    verified: true,
    status: "accepted",
  },
  {
    id: "iss_12",
    check_id: "C9",
    source: "rule",
    category: "consistency",
    severity: "minor",
    title: "Abbreviation 'irAE' is used but not defined",
    where: { anchor: "irae", section: "9.1 Adverse Events of Special Interest", quote: "report all irAEs of Grade 2 or higher" },
    related: [],
    why: {
      explanation: "irAE does not appear in the abbreviation list in Section 12.1 and is not spelled out at first use.",
      standard_ref: "ICH M11 12.1",
      amendment_category: "clerical",
    },
    fix: {
      suggestion: "Add 'irAE: immune-related adverse event' to Section 12.1 and spell it out at first use.",
      patch: { op: "add_abbreviation", abbreviation: "irAE", definition: "immune-related adverse event" },
    },
    confidence: 0.98,
    verified: true,
    status: "accepted",
  },
  {
    id: "iss_13",
    check_id: "C2",
    source: "rule",
    category: "burden",
    severity: "minor",
    title: "Exploratory skin biopsy is not linked to any objective or endpoint",
    where: { anchor: "soa_biopsy", section: "1.3 Schedule of Activities", quote: "Exploratory skin biopsy" },
    related: [
      {
        anchor: "biopsy",
        section: "8.3 Exploratory Skin Biopsy",
        quote: "A 4 mm punch skin biopsy is collected at screening, Week 6 and Week 12",
      },
    ],
    why: {
      explanation:
        "Three invasive biopsies per participant are scheduled, but no objective or endpoint in Section 3 uses the samples. Orphan procedures add burden and are a common reason for later amendments.",
      standard_ref: "ICH M11 1.3, 8",
      amendment_category: "visit_schedule",
    },
    fix: {
      suggestion: "Add an exploratory objective that uses the biopsies, make them optional, or remove them.",
      patch: null,
    },
    confidence: 0.89,
    verified: true,
    status: "open",
  },
  {
    id: "iss_14",
    check_id: "C11",
    source: "ai:medical_writer",
    category: "completeness",
    severity: "advisory",
    title: "Benefit/risk assessment does not name known or potential risks",
    where: {
      anchor: "benefit_risk",
      section: "2.3 Benefit/Risk Assessment",
      quote: "Drug X is expected to provide clinical benefit in this population.",
    },
    related: [],
    why: {
      explanation:
        "The section asserts benefit and close monitoring but does not list identified or potential risks of Drug X or docetaxel, or the measures that mitigate them.",
      standard_ref: "ICH M11 2.3",
      amendment_category: "safety",
    },
    fix: {
      suggestion:
        "Summarize the key identified and potential risks of each treatment and the mitigation for each (monitoring, dose holds, exclusion criteria).",
      patch: null,
    },
    confidence: 0.78,
    verified: true,
    status: "open",
  },
  {
    id: "iss_15",
    check_id: "C11",
    source: "ai:clinical_ops",
    category: "burden",
    severity: "minor",
    title: "Cycle 1 Day 1 PK schedule requires an 8-hour post-infusion clinic stay",
    where: {
      anchor: "pk",
      section: "8.4 Pharmacokinetics",
      quote: "at 0.5, 1, 2, 4 and 8 hours after the end of infusion",
    },
    related: [],
    why: {
      explanation:
        "With a 60-minute infusion and an 8-hour post-infusion sample, participants stay at least 9 hours on Cycle 1 Day 1. Long first visits reduce enrollment at community sites.",
      standard_ref: null,
      amendment_category: "visit_schedule",
    },
    fix: {
      suggestion:
        "Consider sparse sampling (end of infusion and 4 hours) on C1D1 with population PK modelling, or limit full profiles to a PK subset.",
      patch: null,
    },
    confidence: 0.74,
    verified: true,
    status: "open",
  },
  {
    id: "iss_16",
    check_id: "C11",
    source: "ai:medical_writer",
    category: "consistency",
    severity: "minor",
    title: "Primary endpoint assessor differs: investigator (Synopsis) vs BICR (Section 8.1)",
    where: {
      anchor: "eff_bicr",
      section: "8.1 Efficacy Assessments",
      quote: "assessed per RECIST 1.1 by blinded independent central review (BICR)",
    },
    related: [
      { anchor: "syn_endpoint", section: "1.1 Synopsis", quote: "ORR per RECIST 1.1 at Week 24, assessed by the investigator." },
    ],
    why: {
      explanation:
        "The Synopsis says ORR is assessed by the investigator; Section 8.1 says by BICR. In an open-label study the assessor of the primary endpoint matters for bias and must be stated once, consistently.",
      standard_ref: "ICH M11 1.1, 8.1",
      amendment_category: "endpoints",
    },
    fix: {
      suggestion: "State BICR as the primary assessment in both places and investigator assessment as supportive.",
      patch: null,
    },
    confidence: 0.82,
    verified: true,
    status: "open",
  },
  {
    id: "iss_17",
    check_id: "C11",
    source: "ai:clinical_ops",
    category: "advisory",
    severity: "advisory",
    title: "Visit windows are not stated after Week 12",
    where: {
      anchor: "soa_footnote",
      section: "1.3 Schedule of Activities",
      quote: "Visit windows are +/- 3 days through Week 12.",
    },
    related: [],
    why: {
      explanation:
        "Windows are defined only through Week 12. Later visits, including the Week 25 imaging visit, have no window, which leads to protocol deviations when visits slip.",
      standard_ref: "ICH M11 1.3",
      amendment_category: "visit_schedule",
    },
    fix: { suggestion: "Add windows for all visits after Week 12 (for example, +/- 7 days).", patch: null },
    confidence: 0.72,
    verified: true,
    status: "rejected",
  },
  {
    id: "iss_18",
    check_id: "C11",
    source: "ai:biostatistician",
    category: "advisory",
    severity: "advisory",
    title: "No multiplicity control is described for the secondary endpoints",
    where: {
      anchor: "secondary_analysis",
      section: "10.5 Secondary Endpoint Analyses",
      quote: "Duration of response will be summarized descriptively.",
    },
    related: [],
    why: {
      explanation:
        "Several secondary endpoints are tested, but the protocol does not say whether they are tested hierarchically or how the type I error is controlled.",
      standard_ref: "ICH E9",
      amendment_category: "statistics",
    },
    fix: null,
    confidence: 0.7,
    verified: true,
    status: "open",
  },
  {
    id: "iss_19",
    check_id: "D3",
    source: "rule",
    category: "amendment_risk",
    severity: "major",
    title: "ECOG 0 only is stricter than 91% of peer trials",
    where: { anchor: "inc_ecog", section: "5.1 Inclusion Criteria", quote: "ECOG performance status of 0." },
    related: [],
    why: {
      explanation:
        "In the peer set of similar Phase 3 NSCLC trials, 91% allow ECOG 0 to 1. Restricting to ECOG 0 shrinks the eligible population and is a frequent target of eligibility amendments.",
      standard_ref: null,
      amendment_category: "eligibility",
    },
    fix: { suggestion: "Allow ECOG performance status 0 to 1, as most peer trials do.", patch: null },
    confidence: 0.88,
    verified: true,
    status: "open",
  },
  {
    id: "iss_20",
    check_id: "D3",
    source: "rule",
    category: "amendment_risk",
    severity: "advisory",
    title: "6-week washout of prior anticancer therapy is longer than most peer trials",
    where: {
      anchor: "exc_washout",
      section: "5.2 Exclusion Criteria",
      quote: "Anticancer therapy within 6 weeks before the first dose of study treatment.",
    },
    related: [],
    why: {
      explanation:
        "Most peer trials use 4 weeks or 5 half-lives, whichever is shorter. A longer washout delays treatment for participants who are progressing.",
      standard_ref: null,
      amendment_category: "eligibility",
    },
    fix: {
      suggestion: "Use 4 weeks or 5 half-lives, whichever is shorter.",
      patch: null,
    },
    confidence: 0.8,
    verified: true,
    status: "open",
  },
];
