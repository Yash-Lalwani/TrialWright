# Protocol Pre-Flight: results

Generated from `data/bench/results` (test split, 7 protocols, 65 injected errors, seed(s) [1]).

## 1. Detection of injected errors (N1, N3)

| Configuration | Recall | Precision | F1 | Flags per clean protocol (critical+major) |
|---|---|---|---|---|
| Rules only | 35% | 88% | 0.51 | 4.57 |
| LLM only (one generic prompt) | 40% | 10% | 0.15 | 36.71 |
| Pre-Flight (rules + LLM + verifier) | 43% | 90% | 0.58 | 6.43 |

Flags on clean protocols are *unadjudicated*: some may be real problems in the original document. Nobody has labelled them yet (see Not measured).
The LLM-only baseline is scored check-agnostically and strictly: a finding counts only if it is on an injected page AND quotes the edited line or names the new value.

### Dev vs test (the rules were tuned on dev)

| Configuration | Dev recall | Test recall | Dev precision | Test precision |
|---|---|---|---|---|
| Rules only | 67% | 35% | 100% | 88% |
| LLM only (one generic prompt) | 59% | 40% | 15% | 10% |
| Pre-Flight (rules + LLM + verifier) | 70% | 43% | 95% | 90% |

The drop from dev to test is the honest estimate of how the tool behaves on protocols it was not tuned on.

### By error type

| Type | Rules only | LLM only (one generic prompt) | Pre-Flight (rules + LLM + verifier) |
|---|---|---|---|
| T02 Endpoint timepoint changed in one place | 1/2 | 0/2 | 1/2 |
| T04 Secondary objective's endpoint deleted | 0/5 | 0/5 | 0/5 |
| T05 Endpoint analysis removed from statistics | 0/7 | 0/7 | 1/7 |
| T06 Age range changed in one place | 2/3 | 1/3 | 2/3 |
| T07 Dose changed in one place | 3/6 | 2/6 | 3/6 |
| T08 Sample size changed in one place | 3/5 | 3/5 | 3/5 |
| T09 Power/effect changed so N not reproducible | 0/4 | 2/4 | 0/4 |
| T10 Randomisation ratio changed in one place | 1/2 | 1/2 | 1/2 |
| T12 Exclusion criterion contradicts an inclusion criterion | 0/6 | 5/6 | 4/6 |
| T13 Lab threshold value conflicts between mentions | 0/6 | 6/6 | 0/6 |
| T14 Cross-reference to a nonexistent section | 7/7 | 5/7 | 7/7 |
| T15 Required M11 section removed | 5/5 | 0/5 | 5/5 |
| T16 Visit windows made to overlap | 0/2 | 0/2 | 0/2 |
| T17 Treatment/follow-up duration no longer adds up | 1/5 | 1/5 | 1/5 |

T01 (endpoint visit removed) and T03 (orphan procedure) are not implemented as injectors; see the answer keys for why.

## 2. Where the false alarms come from

Pre-Flight, critical+major flags per clean protocol by check: `B2:major` 2.1, `B1:major` 1.1, `C1:major` 1.0, `C4:critical` 0.7, `C3:major` 0.4, `C4:major` 0.3, `C5:critical` 0.1, `C7:major` 0.1, `D3:major` 0.1, `C1:critical` 0.1, `C6:major` 0.1.

## 3. Grounding of AI findings (N4)

Pre-Flight: 446 AI findings produced, 60 dropped by the verifier as ungrounded, 386 shown, of which 0 had a quote not found on the cited page (checked independently of the verifier).
LLM only (no verifier): 1159 findings, 93 (8%) with a quote not on the cited page.

## 4. Speed and cost (N10)

Median 30.5 s and $0.0065 per protocol, live over 7 protocols. Cost is the provider-reported charge; the model and price are whatever `PREFLIGHT_MODEL` was at measurement time.

## 5. Retrospective check on registry edits (N7)

200 registered Phase 2 melanoma trials started 2015 or later, DRUG or BIOLOGICAL (the demo protocol's peer set). 111 had at least one registry edit to the Eligibility module after the first posting.

For each trial, the first edit that RELAXED a metric (inclusion or exclusion criteria count down by 2 or more; minimum age lowered; maximum age raised or removed). The pre-edit value was compared with the other 199 trials' latest values using the hotspot rule (>= 85th percentile and above the peer upper quartile). Counts come from the registry's free-text criteria and are approximate. Control: every other trial's latest value on the same metric, same rule.

| Metric | Relaxed trials flagged before the edit | Other trials flagged | Odds ratio | One-sided Fisher p |
|---|---|---|---|---|
| nInc | 9/22 | 24/178 | 4.44 | 0.003 |
| nExc | 3/9 | 26/166 | 2.69 | 0.171 |
| minAge | 0/1 | 2/198 | n/a | n/a |
| maxAge | 0/0 | 4/31 | n/a | n/a |

Caveats:
- Exploratory: four metrics were tested and no multiple-comparison correction was applied; only the inclusion-count result is individually significant.
- The peer distribution is each peer's LATEST record, which includes the edits we are testing against.
- A trial can appear under more than one metric, so metrics are not independent and are not pooled.
- Registry criteria text is free text; counts are bullets or non-empty lines and are approximate.
- This tests only the peer-outlier (hotspot) signal on registry fields, not the whole Pre-Flight pipeline, which reads the protocol PDF; earlier PDFs are not available.

Examples:
- NCT04752826: Exclusion criteria cut from 28 to 14 in registry version 17 (2026-09). Before the edit the trial's 28 exclusion criteria were at the 91st percentile of 199 melanoma Phase 2 peers.
- NCT06070012: Exclusion criteria cut from 35 to 33 in registry version 4 (2024-11). 35 exclusion criteria were at the 97th percentile of peers before the edit.
- NCT02743611: Inclusion criteria cut from 30 to 11 in registry version 12 (2018-10). 30 inclusion criteria were at the 91st percentile of peers before the edit.
- NCT03915678: Inclusion criteria cut from 42 to 21 in registry version 2 (2021-02). 42 inclusion criteria were at the 95th percentile of peers before the edit.

## 6. Limitations

- The corpus has 10 protocols; 3 dev, 7 test. Protocols were kept partly because their Schedule of Activities could be extracted, which favours the tool. Five candidates were dropped for that reason (`data/corpus/soa_assessment.json`).
- Errors are injected by a script, not found in the wild. They test detection, not that real amendments look like them. Real amendment histories are not yet used (N7).
- Absolute burden hours and dollars come from `data/assumptions/procedure_costs.csv`, every row of which is labelled `assumption`. Only relative burden against peers is meaningful. Recurring schedule columns are counted once, so totals are lower bounds.
- Peer schedule percentiles exist only for peer sets we summarised, and only for peers whose schedule extracted plausibly; fewer than 8 such peers means no comparison.
- Drafted protocol text (co-author) can contain general medical statements that are not in the brief. It is a draft for human review, and unsupported sections are left [TBD].
- Pre-Flight assists a reviewer; it does not approve or reject a protocol.

## 7. Not measured

- Human baseline (N5): the kit exists; no participants were available.
- Precision of real findings with a second labeller and kappa (N6) and false-alarm adjudication (N2).
- Whole-pipeline retrospective test on earlier protocol PDFs: not possible, earlier versions of the PDFs are not posted. Section 5 tests only the peer-outlier signal on registry fields.
- Schedule-of-Activities extraction accuracy against hand-labelled cells.

## 8. Reproduce

```
preflight fetch                      # downloads the PDFs in data/corpus/manifest.csv
python -m preflight.eval.cli bench --set dev --config rules_only --llm-graph
python -m preflight.eval.cli bench --set dev --config full
python -m preflight.eval.cli bench --set dev --config llm_only
python -m preflight.eval.speed dev      # live timing and cost
python -m preflight.eval.report
```
