// Content of the synthetic sample protocol used for UI testing until Person A
// supplies the real demo PDF and issues_real.json (CONTRACTS.md §5).
//
// It describes no real study, drug or sponsor. Errors are planted on purpose so
// the mock issues in issues.json point at text that really exists on the page.
// Blocks with an `id` are anchors: the generator records their page and bbox.
//
// Only WinAnsi characters are allowed (pdf-lib standard fonts), so ">=" is
// written instead of the symbol and "x10^9/L" instead of a superscript.

export const PROTOCOL_NUMBER = "PF-DEMO-001";
export const TITLE =
  "A Phase 3, Randomized, Open-Label Study of Drug X Versus Chemotherapy in Advanced NSCLC";

const SOA_COLUMNS = ["Scr", "C1D1", "W3", "W6", "W9", "W12", "W18", "W24", "W25", "EOT", "FU"];
const WEEKS = ["-4-0", "0", "3", "6", "9", "12", "18", "24", "25", "", "+12"];

/** Build a SoA row from the visit columns that are marked. */
function row(label, marked, id) {
  return { label, cells: SOA_COLUMNS.map((c) => (marked.includes(c) ? "X" : "")), id };
}

const ALL_ON_TREATMENT = ["C1D1", "W3", "W6", "W9", "W12", "W18", "W24"];

export const pages = [
  // 1
  [
    { t: "label", text: "SYNTHETIC SAMPLE PROTOCOL FOR SOFTWARE TESTING" },
    { t: "space", h: 16 },
    { t: "title", text: TITLE },
    { t: "space", h: 18 },
    { t: "kv", key: "Protocol number", value: PROTOCOL_NUMBER },
    { t: "kv", key: "Registry identifier", value: "NCT00000000 (placeholder, not registered)" },
    { t: "kv", key: "Phase", value: "3" },
    { t: "kv", key: "Sponsor", value: "Example Sponsor (fictional)" },
    { t: "kv", key: "Version", value: "1.0, 1 September 2026" },
    { t: "space", h: 18 },
    {
      t: "p",
      text:
        "This document is a synthetic protocol written to test Protocol Pre-Flight. It describes no real study, drug, sponsor or participant. Inconsistencies were placed in it deliberately so that review findings can be demonstrated against real page coordinates.",
    },
  ],
  // 2
  [
    { t: "h1", text: "Table of Contents" },
    ...[
      ["1 Protocol Summary", 3],
      ["1.1 Synopsis", 3],
      ["1.2 Trial Schema", 4],
      ["1.3 Schedule of Activities", 5],
      ["2 Introduction", 6],
      ["3 Trial Objectives and Associated Estimands", 8],
      ["4 Trial Design", 9],
      ["5 Trial Population", 10],
      ["6 Trial Intervention", 13],
      ["7 Discontinuation and Participant Withdrawal", 15],
      ["8 Trial Assessments and Procedures", 16],
      ["9 Adverse Events and Serious Adverse Events", 18],
      ["10 Statistical Considerations", 19],
      ["11 Trial Oversight and Other General Considerations", 21],
      ["12 Supporting Documentation", 22],
      ["13 References", 23],
      ["Appendix A Protocol Amendment History", 24],
    ].map(([key, page]) => ({ t: "toc", key, value: String(page) })),
  ],
  // 3
  [
    { t: "h1", text: "1 Protocol Summary" },
    { t: "h2", text: "1.1 Synopsis" },
    { t: "kv", key: "Title", value: TITLE },
    { t: "kv", key: "Phase", value: "3" },
    {
      t: "kv",
      key: "Population",
      id: "syn_population",
      value:
        "Adults aged 18 to 75 years with advanced or metastatic NSCLC that progressed after one prior platinum-based chemotherapy regimen.",
    },
    {
      t: "kv",
      key: "Primary objective",
      value: "To compare the objective response rate (ORR) at Week 24 between Drug X and docetaxel.",
    },
    {
      t: "kv",
      key: "Interventions",
      id: "syn_dose",
      value:
        "Drug X 300 mg IV every 3 weeks (Q3W). Comparator: docetaxel 75 mg/m2 IV Q3W.",
    },
    { t: "kv", key: "Design", value: "Randomized 1:1, open-label, multicenter, parallel group." },
    {
      t: "kv",
      key: "Sample size",
      id: "syn_n",
      value: "Approximately 420 participants (210 per arm).",
    },
    {
      t: "kv",
      key: "Duration",
      value: "Treatment for up to 48 weeks, followed by 12 weeks of safety follow-up.",
    },
  ],
  // 4
  [
    { t: "h2", text: "1.1 Synopsis (continued)" },
    {
      t: "kv",
      key: "Primary endpoint",
      id: "syn_endpoint",
      value: "ORR per RECIST 1.1 at Week 24, assessed by the investigator.",
    },
    {
      t: "kv",
      key: "Secondary endpoints",
      value: "Progression-free survival (PFS), overall survival (OS), duration of response, safety.",
    },
    {
      t: "kv",
      key: "Key eligibility",
      value: "Measurable disease per RECIST 1.1; ECOG performance status 0; adequate organ function.",
    },
    { t: "space", h: 8 },
    { t: "h2", text: "1.2 Trial Schema" },
    {
      t: "p",
      id: "schema_text",
      text:
        "Participants are screened for up to 28 days, randomized 1:1 to Drug X or docetaxel, treated in 21-day cycles for up to 48 weeks, and followed for 12 weeks after the last dose. A schema figure is not provided in this version.",
    },
  ],
  // 5
  [
    { t: "h2", text: "1.3 Schedule of Activities" },
    {
      t: "table",
      columns: SOA_COLUMNS,
      subheader: { label: "Study week", cells: WEEKS },
      rows: [
        row("Informed consent", ["Scr"]),
        row("Medical history and demographics", ["Scr"]),
        row("Physical examination", ["Scr", ...ALL_ON_TREATMENT, "EOT"]),
        row("Vital signs", ["Scr", ...ALL_ON_TREATMENT, "W25", "EOT"]),
        row("ECOG performance status", ["Scr", "C1D1", "W6", "W12", "W18", "W24", "EOT"]),
        row("Hematology", ["Scr", ...ALL_ON_TREATMENT, "EOT"]),
        row("Chemistry", ["Scr", ...ALL_ON_TREATMENT, "EOT"]),
        row("12-lead ECG", ["Scr", "W12", "EOT"]),
        row("Tumor imaging (CT/MRI)", ["Scr", "W6", "W12", "W18", "W25", "EOT"], "soa_imaging"),
        row("PK sampling", ["C1D1", "W3", "W12"]),
        row("Exploratory skin biopsy", ["Scr", "W6", "W12"], "soa_biopsy"),
        row("Study drug administration", ALL_ON_TREATMENT),
        row("Adverse event review", [...ALL_ON_TREATMENT, "W25", "EOT", "FU"]),
        row("Survival follow-up", ["FU"]),
      ],
    },
    { t: "space", h: 10 },
    {
      t: "small",
      id: "soa_footnote",
      text:
        "Imaging per RECIST 1.1 at screening, every 6 weeks through Week 18, then at Week 25 and end of treatment (EOT). Visit windows are +/- 3 days through Week 12.",
    },
    {
      t: "small",
      text: "Scr = screening; C1D1 = Cycle 1 Day 1; W = week; EOT = end of treatment; FU = follow-up.",
    },
  ],
  // 6
  [
    { t: "h1", text: "2 Introduction" },
    { t: "h2", text: "2.1 Background" },
    {
      t: "p",
      text:
        "Non-small cell lung cancer (NSCLC) accounts for most lung cancer diagnoses. Patients whose disease progresses after platinum-based chemotherapy have limited options, and single-agent docetaxel remains a common comparator in this setting.",
    },
    {
      t: "p",
      text:
        "Drug X is a fictional monoclonal antibody used only in this synthetic document. Its properties are invented for the purpose of software testing and must not be interpreted as clinical information.",
    },
    { t: "h2", text: "2.2 Rationale" },
    {
      t: "p",
      text:
        "This study compares Drug X with docetaxel in participants with previously treated advanced NSCLC to determine whether Drug X improves objective response.",
    },
  ],
  // 7
  [
    { t: "h2", text: "2.3 Benefit/Risk Assessment" },
    {
      t: "p",
      id: "benefit_risk",
      text:
        "Drug X is expected to provide clinical benefit in this population. Participants will be monitored closely for adverse events throughout the study.",
    },
  ],
  // 8
  [
    { t: "h1", text: "3 Trial Objectives and Associated Estimands" },
    { t: "h2", text: "3.1 Primary Objective" },
    {
      t: "p",
      id: "obj_primary",
      text:
        "Objective response rate at Week 24 per RECIST 1.1 in participants randomized to Drug X compared with docetaxel.",
    },
    { t: "h2", text: "3.2 Secondary Objectives" },
    { t: "li", label: "1.", id: "obj_pfs", text: "To compare progression-free survival (PFS) per RECIST 1.1." },
    { t: "li", label: "2.", text: "To compare overall survival (OS)." },
    { t: "li", label: "3.", text: "To evaluate duration of response in responding participants." },
    { t: "li", label: "4.", text: "To characterize the safety and tolerability of Drug X." },
    { t: "h2", text: "3.3 Estimands" },
    {
      t: "p",
      id: "estimands",
      text: "The primary estimand will be described in the statistical analysis plan.",
    },
  ],
  // 9
  [
    { t: "h1", text: "4 Trial Design" },
    { t: "h2", text: "4.1 Overall Design" },
    {
      t: "p",
      text:
        "This is a randomized, open-label, multicenter Phase 3 study. Participants are randomized 1:1 to Drug X or docetaxel, stratified by PD-L1 expression and histology.",
    },
    {
      t: "p",
      id: "design_duration",
      text:
        "The treatment period lasts up to 48 weeks and is followed by a 12-week safety follow-up period. The total duration of participation is 52 weeks, excluding screening.",
    },
    { t: "h2", text: "4.2 Scientific Rationale for Design" },
    {
      t: "p",
      text:
        "An open-label design is used because the infusion schedules and premedication requirements of the two treatments differ.",
    },
    { t: "h2", text: "4.3 End of Trial Definition" },
    {
      t: "p",
      text: "The end of the trial is the date of the last visit of the last participant.",
    },
  ],
  // 10
  [
    { t: "h1", text: "5 Trial Population" },
    {
      t: "p",
      text: "Participants must meet all inclusion criteria and none of the exclusion criteria.",
    },
    { t: "h2", text: "5.1 Inclusion Criteria" },
    { t: "li", label: "1.", id: "inc_age", text: "Age 18 to 80 years at the time of signing informed consent." },
    { t: "li", label: "2.", text: "Histologically or cytologically confirmed stage IIIB, IIIC or IV NSCLC." },
    {
      t: "li",
      label: "3.",
      text: "Disease progression during or after one prior platinum-based chemotherapy regimen.",
    },
    { t: "li", label: "4.", text: "At least one measurable lesion per RECIST 1.1." },
    { t: "li", label: "5.", id: "inc_ecog", text: "ECOG performance status of 0." },
    {
      t: "li",
      label: "6.",
      id: "inc_anc",
      text:
        "Adequate bone marrow function: absolute neutrophil count (ANC) >= 1.5 x10^9/L, platelets >= 100 x10^9/L, hemoglobin >= 9.0 g/dL.",
    },
    {
      t: "li",
      label: "7.",
      id: "inc_brain",
      text:
        "Participants with brain metastases are eligible if the metastases were treated and have been stable for at least 4 weeks.",
    },
    { t: "li", label: "8.", text: "Life expectancy of at least 12 weeks." },
  ],
  // 11
  [
    { t: "h2", text: "5.1 Inclusion Criteria (continued)" },
    {
      t: "li",
      label: "9.",
      text: "Adequate hepatic function: total bilirubin <= 1.5 x ULN; AST and ALT <= 2.5 x ULN.",
    },
    {
      t: "li",
      label: "10.",
      text:
        "Willing to use highly effective contraception during treatment and for 6 months after the last dose.",
    },
    { t: "h2", text: "5.2 Exclusion Criteria" },
    { t: "li", label: "1.", text: "Prior treatment with docetaxel." },
    {
      t: "li",
      label: "2.",
      id: "exc_anc",
      text: "Absolute neutrophil count (ANC) < 2.0 x10^9/L at screening.",
    },
    {
      t: "li",
      label: "3.",
      text: "Active autoimmune disease requiring systemic treatment within the past 2 years.",
    },
    { t: "li", label: "4.", id: "exc_brain", text: "Any history of brain metastases." },
    { t: "li", label: "5.", text: "Interstitial lung disease or pneumonitis that required steroids." },
    {
      t: "li",
      label: "6.",
      id: "exc_washout",
      text: "Anticancer therapy within 6 weeks before the first dose of study treatment.",
    },
  ],
  // 12
  [
    { t: "h2", text: "5.2 Exclusion Criteria (continued)" },
    { t: "li", label: "7.", text: "Known HIV infection with a detectable viral load." },
    { t: "li", label: "8.", text: "Pregnant or breastfeeding." },
    { t: "h2", text: "5.3 Lifestyle Considerations" },
    {
      t: "p",
      text: "No dietary restrictions apply. Participants should avoid strenuous activity on infusion days.",
    },
    { t: "h2", text: "5.4 Screen Failures" },
    {
      t: "p",
      text:
        "Individuals who do not meet the criteria may be rescreened once. A minimal data set is recorded for every screen failure.",
    },
  ],
  // 13
  [
    { t: "h1", text: "6 Trial Intervention" },
    { t: "h2", text: "6.1 Description of Trial Intervention" },
    {
      t: "p",
      id: "dose_sec6",
      text:
        "Drug X 350 mg is administered as an intravenous infusion over 60 minutes on Day 1 of each 21-day cycle (Q3W).",
    },
    {
      t: "p",
      text: "Docetaxel 75 mg/m2 is administered intravenously over 60 minutes on Day 1 of each 21-day cycle.",
    },
    { t: "h2", text: "6.2 Preparation, Handling and Storage" },
    {
      t: "p",
      text: "Study drug is stored at 2 to 8 C and prepared by site pharmacy staff according to the pharmacy manual.",
    },
    { t: "h2", text: "6.3 Dose Modifications" },
    {
      t: "p",
      text:
        "Dose reductions of Drug X are not permitted. Treatment may be withheld for up to 12 weeks to manage toxicity.",
    },
  ],
  // 14
  [
    { t: "h2", text: "6.4 Concomitant Therapy" },
    {
      t: "p",
      id: "xref",
      text: "Prohibited and permitted concomitant medications are listed in Section 12.4.",
    },
    { t: "h2", text: "6.5 Treatment Compliance" },
    {
      t: "p",
      text: "Infusion start and stop times and the administered volume are recorded for every dose.",
    },
  ],
  // 15
  [
    { t: "h1", text: "7 Discontinuation and Participant Withdrawal" },
    { t: "h2", text: "7.1 Discontinuation of Trial Intervention" },
    {
      t: "p",
      text:
        "Treatment is discontinued for disease progression, unacceptable toxicity, pregnancy, or participant decision.",
    },
    { t: "h2", text: "7.2 Participant Withdrawal" },
    {
      t: "p",
      text: "Participants may withdraw consent at any time without affecting their medical care.",
    },
    { t: "h2", text: "7.3 Lost to Follow-up" },
    {
      t: "p",
      text: "A participant is considered lost to follow-up after three documented contact attempts.",
    },
  ],
  // 16
  [
    { t: "h1", text: "8 Trial Assessments and Procedures" },
    { t: "h2", text: "8.1 Efficacy Assessments" },
    {
      t: "p",
      id: "eff_bicr",
      text:
        "Tumor response will be assessed per RECIST 1.1 by blinded independent central review (BICR). CT or MRI of the chest, abdomen and pelvis is performed at screening, every 6 weeks through Week 18, at Week 25 and at end of treatment.",
    },
    { t: "h2", text: "8.2 Safety Assessments" },
    {
      t: "p",
      text:
        "Safety is assessed through physical examinations, vital signs, laboratory tests, ECGs and adverse event review as shown in the Schedule of Activities.",
    },
    { t: "h2", text: "8.3 Exploratory Skin Biopsy" },
    {
      t: "p",
      id: "biopsy",
      text:
        "A 4 mm punch skin biopsy is collected at screening, Week 6 and Week 12 for exploratory biomarker research.",
    },
  ],
  // 17
  [
    { t: "h2", text: "8.4 Pharmacokinetics" },
    {
      t: "p",
      id: "pk",
      text:
        "On Cycle 1 Day 1, PK samples are drawn before infusion and at 0.5, 1, 2, 4 and 8 hours after the end of infusion. Single trough samples are drawn at Week 3 and Week 12.",
    },
    { t: "h2", text: "8.5 Biomarkers" },
    {
      t: "p",
      text: "Archival tumor tissue is collected at screening for PD-L1 testing by a central laboratory.",
    },
  ],
  // 18
  [
    { t: "h1", text: "9 Adverse Events and Serious Adverse Events" },
    {
      t: "p",
      text:
        "Adverse events are recorded from the first dose until 90 days after the last dose and graded using CTCAE version 5.0.",
    },
    { t: "h2", text: "9.1 Adverse Events of Special Interest" },
    {
      t: "p",
      id: "irae",
      text:
        "Investigators must report all irAEs of Grade 2 or higher within 24 hours, using the same process as for serious adverse events.",
    },
    { t: "h2", text: "9.2 Reporting Period" },
    {
      t: "p",
      text: "Serious adverse events are reported to the sponsor within 24 hours of awareness.",
    },
  ],
  // 19
  [
    { t: "h1", text: "10 Statistical Considerations" },
    { t: "h2", text: "10.1 Statistical Hypotheses" },
    {
      t: "p",
      text:
        "The null hypothesis is that the ORR is equal in the two arms. The alternative is that the ORR differs between arms.",
    },
    { t: "h2", text: "10.2 Sample Size Determination" },
    {
      t: "p",
      id: "sample_size",
      text:
        "Assuming an ORR of 12% with docetaxel and 22% with Drug X, a two-sided alpha of 0.05, 80% power and a dropout rate of 10%, approximately 420 participants (210 per arm) will be randomized.",
    },
  ],
  // 20
  [
    { t: "h2", text: "10.3 Analysis Populations" },
    {
      t: "li",
      label: "-",
      id: "pop_itt",
      text:
        "Intent-to-treat (ITT) population: all randomized participants. The ITT population is the primary population for efficacy analyses.",
    },
    {
      t: "li",
      label: "-",
      text: "Per-protocol (PP) population: ITT participants without major protocol deviations.",
    },
    { t: "li", label: "-", text: "Safety population: all participants who received any study treatment." },
    { t: "h2", text: "10.4 Primary Endpoint Analysis" },
    {
      t: "p",
      id: "primary_analysis",
      text:
        "ORR will be compared between arms in the per-protocol population using a Cochran-Mantel-Haenszel test stratified by the randomization factors.",
    },
    { t: "h2", text: "10.5 Secondary Endpoint Analyses" },
    {
      t: "p",
      id: "secondary_analysis",
      text:
        "Overall survival will be compared using a stratified log-rank test. Duration of response will be summarized descriptively.",
    },
  ],
  // 21
  [
    { t: "h1", text: "11 Trial Oversight and Other General Considerations" },
    { t: "h2", text: "11.1 Regulatory and Ethical Considerations" },
    {
      t: "p",
      text:
        "The study is conducted in accordance with ICH E6 Good Clinical Practice and applicable regulations.",
    },
    { t: "h2", text: "11.2 Informed Consent" },
    { t: "p", text: "Written informed consent is obtained before any study-specific procedure." },
    { t: "h2", text: "11.3 Data Protection" },
    { t: "p", text: "Participant data are pseudonymized before transfer to the sponsor." },
  ],
  // 22
  [
    { t: "h1", text: "12 Supporting Documentation" },
    { t: "h2", text: "12.1 Abbreviations" },
    ...[
      ["AE", "adverse event"],
      ["BICR", "blinded independent central review"],
      ["CT", "computed tomography"],
      ["ECOG", "Eastern Cooperative Oncology Group"],
      ["ITT", "intent-to-treat"],
      ["MRI", "magnetic resonance imaging"],
      ["NSCLC", "non-small cell lung cancer"],
      ["ORR", "objective response rate"],
      ["OS", "overall survival"],
      ["PFS", "progression-free survival"],
      ["PK", "pharmacokinetics"],
      ["Q3W", "every 3 weeks"],
      ["RECIST", "Response Evaluation Criteria in Solid Tumours"],
      ["ULN", "upper limit of normal"],
    ].map(([key, value]) => ({ t: "kv", key, value, compact: true })),
    { t: "h2", text: "12.2 Clinical Laboratory Tests" },
    { t: "p", text: "Hematology and chemistry panels are analyzed by local laboratories." },
    { t: "h2", text: "12.3 Contraceptive Guidance" },
    { t: "p", text: "Highly effective methods are those with a failure rate below 1% per year." },
  ],
  // 23
  [
    { t: "h1", text: "13 References" },
    {
      t: "li",
      label: "1.",
      text:
        "Eisenhauer EA, et al. New response evaluation criteria in solid tumours: revised RECIST guideline (version 1.1). Eur J Cancer. 2009;45(2):228-247.",
    },
    {
      t: "li",
      label: "2.",
      text: "ICH M11 Clinical electronic Structured Harmonised Protocol (CeSHarP) template.",
    },
  ],
  // 24
  [
    { t: "h1", text: "Appendix A Protocol Amendment History" },
    { t: "p", text: "Version 1.0 is the original protocol. There are no amendments." },
  ],
];
