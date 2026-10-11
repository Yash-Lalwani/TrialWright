# Protocol Pre-Flight: Evaluation Plan

How we prove Pre-Flight is useful. Every number here is reproducible with `preflight bench` from a clean clone.

## 1. Corpus

| Set | Count | Contents | Use |
|---|---|---|---|
| Dev | 3 protocols | Real ClinicalTrials.gov protocol PDFs | Building and tuning checks |
| Test | 7 protocols | Real protocol PDFs, held out | All reported benchmark numbers |
| Peers | 50-200 per protocol | ClinicalTrials.gov structured records, plus about 30 peer protocol PDFs | Burden percentiles, hotspots, precedent |
| History | Trials with record versions | ClinicalTrials.gov registry versions | Retrospective case studies (N7) |

Selection: oncology first, Regeneron-sponsored where a protocol PDF is attached, then other oncology sponsors, plus 2 non-oncology protocols to show it generalizes. Mix of Phase 2 and 3 and of lengths. Each file is listed in data/corpus/manifest.csv with NCT id, source URL and download date.

Checks are tuned only on the dev set. The test set is not opened while writing rules, so the numbers are not overfit.

## 2. Error taxonomy and injector

`preflight inject` edits the original PDF with PyMuPDF (redact plus insert text), so the benchmark exercises the full pipeline from PDF. Each injected file gets an answer key: data/bench/{protocol}_{seed}.json with error id, type, page, original text, new text and expected check.

| Type | Injection | Expected check | Amendment category |
|---|---|---|---|
| T01 | Remove the assessment mark for the primary endpoint at its timepoint visit in the SoA | C1 | Visit schedule |
| T02 | Change an endpoint timepoint in one place only (e.g., Week 24 to Week 26 in synopsis) | C1, C4 | Endpoints |
| T03 | Add a procedure row to the SoA that no objective uses | C2 | Visit schedule |
| T04 | Delete the endpoint of a secondary objective | C3 | Endpoints |
| T05 | Remove an endpoint's analysis from the statistics section | C3 | Statistics |
| T06 | Change the age range in the synopsis only | C4 | Eligibility |
| T07 | Change a dose in one section only | C4 | Intervention |
| T08 | Change the sample size in the synopsis only | C4 | Statistics |
| T09 | Change stated power or effect size so N is no longer reproducible | C7 | Statistics |
| T10 | Change randomization ratio or number of arms in one section | C4 | Design |
| T11 | Remove blinding or emergency unblinding text from a double-blind protocol | C5, B3 | Design |
| T12 | Add an exclusion criterion that contradicts an inclusion criterion | C8 | Eligibility |
| T13 | Change a lab threshold's unit or value so two mentions conflict | C8 | Eligibility, safety |
| T14 | Point a cross-reference to a section that does not exist | C9 | Clerical |
| T15 | Remove a required M11 section (e.g., safety reporting or estimands) | B1 | Completeness |
| T16 | Make two visit windows overlap | C6 | Visit schedule |
| T17 | Change treatment or follow-up duration so the total no longer adds up | C6 | Design |
| T18 | Change enrollment or primary timeframe vs the registry record | C10 | Registry |

Each test protocol gets 8 to 12 errors sampled across types with a fixed seed, giving about 70 to 90 injected errors in the test set. Types that cannot be injected cleanly into a given PDF are skipped and recorded in the key.

## 3. Matching rule

A flag counts as a true positive if its check maps to the error type (table above) and its location overlaps the injected location (same page, or same extracted entity for cross-section errors). Each injected error can be matched once.

Real protocols already contain real issues, so precision must not count those as false alarms. We run Pre-Flight on the clean original and on the injected version:

- TP: flags in the injected run that match an injected error
- FN: injected errors with no matching flag
- FP: flags in the injected run that match no injected error and do not appear in the clean run

## 4. Metrics

| ID | Metric | Method |
|---|---|---|
| N1 | Recall, precision, F1 | Overall and per error type on the test set; also per amendment category |
| N2 | False alarms per clean protocol | Critical and major flags on clean originals, adjudicated by two team members as real, debatable or false |
| N3 | Ablation | Same test set, three configurations: (a) rules-only, (b) LLM-only baseline: one "find all problems" prompt per chunk, which is what a typical GPT wrapper does, (c) hybrid Pre-Flight |
| N4 | Hallucination rate | Share of AI findings dropped by the Verifier because the quote does not exist on the cited page. Report before and after; after must be 0% shown |
| N5 | Human baseline | Section 5 |
| N6 | Real findings precision | Sample 30 flags from clean real protocols; two adjudicators label each; report precision and agreement (Cohen's kappa) |
| N7 | Retrospective case studies | Section 6 |
| N8 | Burden | Visits, procedures, invasive procedures, patient hours, site hours, cost per patient, peer percentiles, for every demo protocol |
| N9 | ROI | Section 7 |
| N10 | Speed and cost | Wall-clock seconds and LLM dollars per protocol from the trace log |
| Extra | SoA extraction accuracy | Cell-level accuracy of the extracted SoA matrix vs a hand-built matrix for 3 protocols |

Results are written to data/bench/results/{timestamp}.json and rendered into docs/RESULTS.md and the /evidence page. CI fails if test-set recall drops by more than 5 points.

## 5. Human baseline (N5): dropped

Not run in this release: there was not enough time to schedule reviewers. The benchmark API returns `human_baseline: null` and the Evidence page omits it. The method below is kept for future work.

### Planned method

The question it answers: does Pre-Flight catch more, faster, than a careful human?

- Participants: 3 to 5 people (Regeneron mentors if they agree, otherwise other hackers). No personal data collected.
- Material: one injected test protocol (a shorter one, 60 to 100 pages) with 10 to 12 errors. Participants are told errors were injected but not how many or which types.
- Task: 20 minutes to list problems on a simple form (page, what is wrong).
- Scoring: same matching rule as section 3. Record time to first finding.
- Comparison: Pre-Flight on the same file: errors found, time taken.
- Report: "Humans found X of 12 on average in 20 minutes; Pre-Flight found Y of 12 in Z seconds." Report every participant's result, not only the average.

## 6. Retrospective case studies (N7)

The question it answers: does Pre-Flight flag the areas that real trials later changed?

1. For candidate trials (oncology, Phase 2 or 3), pull registry versions.
2. Keep trials where eligibility criteria or outcome measures changed after the study started (status Recruiting or later).
3. Run eligibility hotspots (D3), C8 and peer comparison on the earliest version's registry text.
4. For each changed area, record whether Pre-Flight flagged it on the earlier version.
5. Present 2 to 3 as case studies, for example: "Version 1 required ECOG 0; changed to ECOG 0-1 eight months later. Pre-Flight flagged the ECOG 0 rule as stricter than most peers on version 1."

This is registry text, not the full protocol, and registry changes are a proxy for amendments. We say so on the slide. If enough trials qualify, report the catch rate; that is also the starting dataset for stretch item D4.

## 7. ROI model (N9)

Inputs, all from the starter sheet's sources unless marked:

| Input | Phase II | Phase III | Source |
|---|---|---|---|
| P(at least one substantial amendment) | 0.57 | 0.57 | Getz 2016 |
| Share avoidable | 0.45 (conservative: 0.33) | 0.45 (conservative: 0.33) | Getz 2016; ERG 2014 cites about one third |
| Median direct cost per amendment | $141,000 | $535,000 | Getz 2016 |
| Delay for trials with an amendment | about 3 months | about 3 months | Applied Clinical Trials |
| Catch rate | Pre-Flight recall on amendment-type errors (N1) | same | Measured |

Formula, per protocol:

```
expected avoidable cost = P(amend) x share_avoidable x cost_per_amendment
expected avoided cost   = expected avoidable cost x catch_rate
expected avoided delay  = P(amend) x share_avoidable x 3 months x catch_rate
```

Before the catch rate:

| | Phase II | Phase III |
|---|---|---|
| Expected avoidable cost (45% avoidable) | about $36,000 | about $137,000 |
| Expected avoidable cost (33% avoidable) | about $27,000 | about $102,000 |
| Expected avoidable delay (45%) | about 0.77 months (23 days) | same |

This assumes one substantial amendment per amended protocol, which understates cost for protocols with several. The /evidence page has sliders for each input so judges can test their own assumptions. Burden savings (patient hours and cost per patient from removing orphan procedures) are reported separately, not added to this figure.

## 8. What we will not claim

- That injected errors cover every real protocol problem.
- That registry changes equal protocol amendments.
- That the ROI figure is a forecast for any specific trial.
- That Pre-Flight replaces review committees.
