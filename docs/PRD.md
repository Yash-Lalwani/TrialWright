# Protocol Pre-Flight: Product Requirements

Status: final scope, agreed 2026-10-10. Track: Regeneron Prize, HackRU Fall 2026.

## 1. Problem

A clinical trial protocol is the rulebook every site, ethics board, regulator and downstream system follows. When it contains a gap, contradiction or unworkable rule, the sponsor issues an amendment and every site re-approves, re-trains and sometimes re-consents patients.

- 57% of protocols have at least one substantial amendment; 45% of those were judged avoidable (Getz et al., 2016).
- Median direct cost per amendment: $141,000 (Phase II), $535,000 (Phase III) (Getz et al., 2016).
- Trials with an amendment took about 3 months longer (Applied Clinical Trials).
- 22.3% of procedures in protocols are non-core, and 15 to 30% of collected data is never used in the NDA (Tufts CSDD, cited in ERG/HHS 2014).
- Industry trust in AI is held back by lack of proven use cases (48%) and unclear ROI (35%) (Lamberti et al., Tufts 2025).

Today, consistency is checked by tired humans across hundreds of pages, eligibility rules are copied from old trials, and patient burden is rarely quantified before finalization.

## 2. Product

Pre-Flight reviews a protocol (PDF, structured USDM JSON, or a short design brief) and returns:

- a list of issues, each with where (section, page, highlighted quote), why (rule, standard reference, amendment category), and a suggested fix;
- a Pre-Flight Score (0 to 100) with four sub-scores: Completeness, Consistency, Burden, Amendment Risk;
- burden and peer benchmarks against similar ClinicalTrials.gov trials;
- for a design brief, a draft in ICH M11 structure plus USDM JSON, citing precedent trials, which Pre-Flight then checks itself.

User: protocol author or study designer at a drug company (medical writer, clinical scientist, statistician, clinical operations reviewer).

The tool assists authors. It does not approve protocols. The UI says so on every page.

## 3. Scope

### 3.1 Required: Good / Better / Best from the starter sheet

| ID | Feature | Tier |
|---|---|---|
| A1 | Parse PDF into sections with page numbers and text coordinates | Good |
| A2 | Map sections to the ICH M11 table of contents | Good |
| A3 | Extract the Schedule of Activities into a visit x procedure matrix | Better |
| A4 | Build the Protocol Graph (objectives, endpoints, assessments, visits, population, arms, doses, sample size, analyses) | Better |
| A5 | Accept PDF, USDM JSON, .docx, or a design brief | Best |
| B1 | Completeness vs ICH M11 template: present / missing / thin, with page refs | Good |
| B2 | Completeness vs SPIRIT 2025 (34 items) | Good |
| B3 | "Thin" defined by required sub-elements, not only word count | Good |
| C1 | Every endpoint timepoint has an SoA visit where that assessment happens | Better |
| C2 | Every SoA procedure serves an objective, endpoint or safety need (orphan procedures) | Better |
| C3 | Every objective has an endpoint; every endpoint has an analysis method | Better |
| C4 | Numbers agree across sections: ages, doses, durations, sample size, arms, ratio | Better |
| D1 | Burden score: visits, procedures, invasive procedures, patient hours, site hours, cost per patient (labelled assumptions) | Better |
| D2 | Peer benchmarking vs similar ClinicalTrials.gov trials (percentiles) | Better |
| D3 | Amendment-risk hotspots (eligibility, visit schedule, safety assessments) vs peers | Best |
| E1 | Suggested fix for every issue | Best |
| E2 | Human accept / reject on every suggestion, with audit trail | Best |
| E3 | Design brief to M11-structured draft plus USDM JSON, citing precedent trials | Best |
| E4 | Export: USDM JSON (schema-validated), clean M11 .docx, issue report (PDF/CSV/JSON) | Best |
| F4 | "Assists, does not approve" banner | Rules |

### 3.2 Additions beyond Best (agreed)

| ID | Feature | Why |
|---|---|---|
| C5 | Design-logic checks (e.g., "double-blind" with no blinding or unblinding procedure; conflicting phase or design labels) | Named in the M11 use case doc |
| C6 | Visit windows that overlap or are impossible; durations that do not add up | Cheap rule, common real error |
| C7 | Recompute sample size from stated alpha, power, effect size, dropout; flag mismatch | Biostatistics judges; LLMs get this wrong |
| C8 | Eligibility contradictions and lab unit or threshold conflicts | Eligibility is the top amendment category |
| C9 | Broken cross-references and undefined abbreviations | Cheap rule |
| C10 | Protocol vs ClinicalTrials.gov registry record (age, primary outcome timeframe, enrollment) | Real-world consistency |
| C11 | AI clinical advisories (e.g., missing monitoring expected for the drug class), labelled advisory, excluded from benchmark score | Clinical depth without risking precision |
| E5 | Version diff: upload v2, see resolved and new issues, score change | Strongest demo moment |
| E6 | Side-by-side precedent view: what similar trials chose for endpoints, eligibility, visit schedule, sample size | Makes precedent concrete |
| E7 | Self-check: Pre-Flight runs its checks on every draft it generates | A tool that verifies its own output |
| F1 | Grammarly-style workspace: PDF with highlights left, issue panel right | Core UX |
| F2 | Pre-Flight Score with four transparent sub-scores | Single number for the story |
| F3 | Evidence page: live benchmark results in the app | Numbers visible in the product |
| F5 | Confidential mode: rules only, nothing leaves the machine | Privacy; also the ablation baseline |
| CLI | `preflight` command-line tool (check, inject, bench, fetch) | Needed by the eval harness anyway |

### 3.3 Stretch (only if time is left, in this order)

1. D5: What-if burden simulator (drop a procedure, see hours, cost and score change live)
2. F7: MCP server exposing Pre-Flight checks as tools
3. F6: GitHub Action that runs Pre-Flight on protocol files in CI
4. D4: Learned amendment-risk model trained on real ClinicalTrials.gov record-version changes

### 3.4 Out of scope

- D6 eligibility realism from NHANES (off-target for oncology)
- Redlined (tracked-changes) .docx export; the accept/reject audit trail covers change history
- Approving or certifying protocols
- Any patient-level data

## 4. User stories

1. As a medical writer, I upload a draft protocol and see every missing or thin M11 section with a page reference, so I can fix gaps before committee review.
2. As a clinical scientist, I see every endpoint whose timepoint has no matching visit or assessment, so the trial actually measures what it claims.
3. As a statistician, I see whether the stated sample size is reproducible from the stated assumptions, and whether every endpoint has an analysis method.
4. As a clinical operations reviewer, I see patient hours, visits and invasive procedures compared with similar trials, and which procedures serve no objective.
5. As a study designer, I see where my eligibility rules or visit schedule are much heavier than peers, with the peer trials listed, so I can justify or relax them.
6. As any reviewer, I click an issue and the PDF jumps to the highlighted text, with why it matters and a suggested fix I can accept or reject.
7. As a protocol lead, I upload v2 and see which issues were resolved and how the score changed.
8. As a study designer, I enter a short design brief and get an M11-structured draft that cites similar trials, already checked by Pre-Flight, exportable as USDM JSON.
9. As a sponsor with confidentiality rules, I can run rules-only mode so no text leaves my machine.
10. As an evaluator, I can reproduce every benchmark number from a clean clone with one command.

## 5. Success metrics (proved in docs/EVALUATION.md)

| ID | Metric | Target |
|---|---|---|
| N1 | Recall, precision, F1 on PreflightBench, overall and per error type | Recall at least 0.85, precision at least 0.80 |
| N2 | False alarms per clean protocol (critical and major only) | At most 2 |
| N3 | Ablation: rules-only vs LLM-only vs hybrid | Hybrid best on F1 |
| N4 | Hallucinated AI flags before vs after verifier | 0% shown after verifier |
| N5 | Human baseline: humans (20 min) vs Pre-Flight on the same injected protocol | Dropped for time (not measured) |
| N6 | Real-protocol findings, precision on a hand-adjudicated sample | Report as measured |
| N7 | Retrospective case studies: later registry changes flagged in the earlier version | 2 to 3 case studies |
| N8 | Burden metrics with peer percentiles | Shown for every demo protocol |
| N9 | Expected avoidable amendment cost and delay, with sensitivity range | Formula in EVALUATION.md |
| N10 | Seconds and dollars per protocol review | Under 3 min, under $0.50 |

Targets are goals, not claims. We report what we measure.

## 6. Judging criteria map

| Criterion (source) | How we meet it |
|---|---|
| Solves the problem (starter sheet); Utility (HackRU, Princeton) | Catches the amendment categories Tufts identifies; burden and risk vs peers; ROI in dollars and months |
| It works, runs from clean clone (starter sheet); Readiness (all) | MIT license, `docker compose up`, record/replay LLM cache so it runs without a key, one-command benchmark, CI, deployed demo |
| Smart use of data (starter sheet) | Real oncology protocols from ClinicalTrials.gov, documented injected errors, real peer data, real registry version history |
| Explains itself (starter sheet) | Every issue: page, highlighted quote, rule, standard reference (M11 section or SPIRIT item), amendment category, fix |
| Craft and demo (starter sheet); Design and Packaging (HackRU, Princeton) | Workspace UI, 3-minute video, 10-12 slide deck, README, PRD, architecture and evaluation docs |
| Relevance (Princeton) | Demo corpus is oncology, Regeneron-sponsored protocols where available |
| Privacy, security, cloud deployment (Princeton) | Confidential rules-only mode, no patient data, Docker images, Jenkinsfile, CI |

## 7. Sources

- Getz KA et al. 2016, Therapeutic Innovation & Regulatory Science. https://journals.sagepub.com/doi/10.1177/2168479016632271
- Applied Clinical Trials, cycle-time impact of amendments. https://www.appliedclinicaltrialsonline.com/view/acknowledging-cycle-time-impact-protocol-amendments
- Lamberti MJ et al. 2025, The Adoption and Use of AI and ML in Clinical Development, TIRS 59:1074-1086.
- Eastern Research Group for HHS ASPE 2014, Examination of Clinical Trial Costs and Barriers for Drug Development.
- Landman R et al. 2024, Using LLMs for safety-related table summarization in CSRs, JAMIA Open 7(2).
- ICH M11 template (FDA copy). https://www.fda.gov/media/192647/download
- SPIRIT 2025. https://www.ncbi.nlm.nih.gov/pmc/articles/PMC12035670/
- CDISC USDM / DDF-RA. https://github.com/cdisc-org/DDF-RA
- ClinicalTrials.gov API v2. https://clinicaltrials.gov/data-api/api
