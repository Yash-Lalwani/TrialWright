# Protocol Pre-Flight: Architecture

Companion to docs/PRD.md (feature IDs) and docs/EVALUATION.md (metrics).

## 1. Design principles

1. Deterministic core, AI at the edges. Everything checkable in code is checked in code. The LLM extracts, reviews and drafts; it never does arithmetic or scoring.
2. Every flag is grounded. An AI flag is shown only if its quoted evidence exists on the cited page.
3. Measured from day one. The benchmark harness exists before the first check, and every check is scored as it lands.
4. Runs from a clean clone. SQLite, Docker, and a committed LLM response cache so the demo works without an API key.

These follow the lessons in the Pfizer CSR challenge (Landman et al. 2024): use structured data instead of raw PDFs where possible, add the protocol as context, use arithmetic modules instead of the model, and keep humans in the loop.

## 2. System overview

```
             +------------------- Next.js frontend -------------------+
             | Upload | Workspace (PDF + issues) | Burden & Peers |   |
             | Compare (diff) | Co-author | Evidence | Audit & Trace |
             +---------------------------+----------------------------+
                                         | REST + SSE
+----------------------------------------v-------------------------------------------+
| FastAPI                                                                            |
|                                                                                    |
|  Ingest -----> Protocol Graph -----> Rules engine ------+                          |
|  (PDF/JSON/     (Pydantic,            B1-B3, C1-C10      |                          |
|   docx/brief)    USDM-aligned)                           +--> Merge, dedupe,        |
|                        |                                 |    severity, score ----> |
|                        +----------> AI Review Committee -+    Issues + Score        |
|                        |            4 reviewers in parallel                         |
|                        |            -> Verifier (grounding)                         |
|                        |                                                            |
|                        +----------> Burden + Peers + Hotspots (D1-D3)               |
|                                                                                    |
|  Co-author: brief -> precedent (E6) -> draft (E3) -> Graph -> same checks (E7)     |
|  Export: USDM JSON, M11 .docx, issue report        Diff: run vs run (E5)           |
|                                                                                    |
|  LLM client (OpenRouter, record/replay cache)   CT.gov client (API v2, cached)     |
|  SQLite: protocols, runs, issues, decisions, llm_calls, peers, bench results       |
+------------------------------------------------------------------------------------+
         ^
         | same Python package
  CLI: preflight fetch | check | inject | bench | export
```

## 3. Tech stack

| Layer | Choice |
|---|---|
| Language and env | Python 3.12, `uv` |
| API | FastAPI, Pydantic v2, Server-Sent Events for run progress |
| PDF | PyMuPDF (text, fonts, coordinates, redaction for error injection), pdfplumber (table cells) |
| LLM | OpenRouter (OpenAI-compatible SDK). Default model `deepseek/deepseek-v4-flash` pinned to a dated id in `.env`. One model setting, swappable |
| Orchestration | Plain asyncio pipeline: steps as functions, independent steps in `asyncio.gather` |
| Stats and units | statsmodels and scipy (power and sample size), pint (lab units) |
| Matching | rapidfuzz (grounding, section titles, procedure names) |
| Data source | ClinicalTrials.gov API v2, cached locally |
| Storage | SQLite via SQLModel |
| Exports | python-docx (M11 .docx), jsonschema (USDM validation), WeasyPrint or ReportLab (issue report PDF) |
| CLI | Typer |
| Tests | pytest |
| Frontend | Next.js (App Router), TypeScript, Tailwind, shadcn/ui, react-pdf (PDF.js) with highlight overlays, Recharts, TanStack Query |
| Packaging | Docker, docker-compose, GitHub Actions (lint, tests, benchmark gate), Jenkinsfile, MIT license |
| Deploy | Render or Fly.io (backend), Vercel or same host (frontend) |

## 4. Protocol Graph (internal model)

Pydantic models, field names aligned with USDM so export is a mapping, not a rewrite.

```
Protocol
  meta: title, nct_id, phase, condition, sponsor, design (allocation, masking, arms count, ratio)
  sections[]: id, m11_id, title, level, page_start, page_end, text, spans[] (page, bbox, text)
  objectives[]: id, level (primary/secondary/exploratory), text, endpoint_ids[]
  endpoints[]: id, text, measure, timepoints[] (normalized to study day/week), analysis_ids[]
  population: min_age, max_age, sex, inclusion[], exclusion[] (each: text, parsed thresholds with units)
  arms[]: name, type, dose, route, frequency, duration
  soa: visits[] (name, study_day, window_minus, window_plus), procedures[] (name, normalized_name), cells[visit_id][procedure_id]
  stats: sample_size, alpha, sidedness, power, effect_size, dropout, analyses[] (endpoint_id, method)
  numbers[]: kind (age/dose/duration/sample_size/ratio), value, unit, span   <- every number with where it was found
  xrefs[]: text, target, span
  abbreviations: defined{}, used{}
```

Every extracted fact carries a span (page, bbox, quote). That is what makes every issue clickable.

## 5. Pipeline

1. Ingest (A1, A5): PyMuPDF gives text blocks with font size and bbox per page. Headings come from numbering patterns plus font size. JSON input loads directly into the graph. A design brief goes through the co-author path.
2. Section mapping (A2): each heading is matched to the M11 TOC (data/standards/m11_toc.yaml, built from the official template) with rapidfuzz plus a synonym list. Unmatched headings go to one LLM batch call for classification.
3. SoA extraction (A3): pdfplumber reads the table cells. If the grid is messy, the LLM normalizes the rows into the visit x procedure schema. Output is validated (every visit has a day, every cell is X or blank) and its accuracy is reported separately.
4. Entity extraction (A4): regex and code first (ages, doses, durations, sample size, ratios, cross-references, abbreviations). Objectives, endpoints, timepoints and eligibility criteria come from section-scoped LLM calls returning JSON that is validated against the Pydantic schema. Every value gets a span.
5. Run, in parallel:
   - Rules engine (B1-B3, C1-C10)
   - AI Review Committee (C11 plus fix text for rule issues)
   - Burden, peers and hotspots (D1-D3)
6. Merge: dedupe (same check family plus overlapping span), assign severity, attach fixes, compute score, persist.

Target: under 3 minutes for a 150-page protocol.

## 6. Rules engine

Each check is a function registered with metadata:

```python
@check(id="C1", category="consistency", amendment_category="visit_schedule",
       standard_ref="ICH M11 1.3 / 8", severity="major")
def endpoint_timepoint_has_visit(graph: ProtocolGraph) -> list[Issue]: ...
```

| ID | Logic |
|---|---|
| B1/B2/B3 | For each required M11 section and SPIRIT item: present if mapped; thin if missing required sub-elements (listed per item in YAML) or under a word floor; missing otherwise |
| C1 | For each endpoint timepoint, find the SoA visit at that study week (within window) and check the endpoint's measure is marked there |
| C2 | For each SoA procedure, check it maps to an endpoint measure, a safety assessment, or an eligibility/screening need; else orphan |
| C3 | Objective without endpoint; endpoint without an analysis in the statistics section |
| C4 | Group numbers by kind; flag disagreements (e.g., age 18-75 in synopsis vs 18-80 in eligibility) |
| C5 | Masking says double-blind but no blinding or emergency unblinding text; phase or design labels disagree across sections |
| C6 | Visit windows overlap; treatment plus follow-up does not equal stated total duration |
| C7 | Recompute N from alpha, power, effect size, dropout with statsmodels (two-sample means, proportions, or log-rank via Schoenfeld for time-to-event); flag if stated N differs by more than 5% |
| C8 | An inclusion criterion requires a condition that an exclusion criterion rules out; the same lab test with conflicting thresholds or units (normalized with pint) |
| C9 | "See Section X" where X does not exist; abbreviation used but never defined |
| C10 | Compare age range, primary outcome timeframe and enrollment with the ClinicalTrials.gov record when an NCT id is known |

## 7. AI Review Committee and guardrails

Four reviewers run in parallel. Each is one structured-output call over its slice of the graph, not a free-roaming agent.

| Reviewer | Input slice | Output |
|---|---|---|
| Medical Writer | Thin sections, synopsis vs body | Clarity and completeness issues, fix text |
| Clinical Scientist | Eligibility, endpoints, safety | Clinical advisories (C11), eligibility concerns |
| Biostatistician | Objectives, estimands, stats section, C7 result | Analysis gaps, estimand issues |
| Clinical Ops | SoA, burden results, peer percentiles | Feasibility concerns, which procedures to cut |

Every reviewer finding must include: quote, page, section, category, explanation, fix.

Guardrails, in order:

1. Schema: output validated by Pydantic. On failure, one retry with the validation error included; then drop.
2. Grounding (Verifier): the quote is normalized and fuzzy-matched (rapidfuzz partial ratio of at least 90) against the cited page text. No match means drop and log as hallucinated (metric N4).
3. Numbers: any number in an AI finding must match an extracted number in the graph; otherwise the finding is downgraded to advisory.
4. Dedupe against rule issues: rules win, and the AI finding's fix text is attached to the rule issue.
5. Human in the loop: no fix is applied without an accept (E2).
6. Banner: "Pre-Flight assists protocol authors. It does not approve protocols."
7. Confidential mode (F5): the LLM client is disabled; only rules, burden and peers run.

## 8. Issue schema

```json
{
  "id": "iss_01",
  "check_id": "C1",
  "source": "rule | ai:biostatistician | ...",
  "category": "completeness | consistency | burden | amendment_risk | advisory",
  "severity": "critical | major | minor | advisory",
  "title": "Week 24 primary endpoint has no Week 24 blood pressure assessment",
  "where": { "section": "1.3 Schedule of Activities", "page": 14, "bbox": [72, 310, 540, 330], "quote": "..." },
  "related": [{ "section": "3 Objectives", "page": 21, "quote": "..." }],
  "why": { "explanation": "...", "standard_ref": "ICH M11 3; SPIRIT item 12", "amendment_category": "visit_schedule" },
  "fix": { "suggestion": "Add BP to Week 24 visit", "patch": { "op": "set_soa_cell", "visit": "W24", "procedure": "BP", "value": "X" } },
  "confidence": 0.92,
  "verified": true,
  "status": "open | accepted | rejected"
}
```

## 9. Burden, peers, hotspots

- Burden (D1): data/assumptions/procedure_costs.csv lists patient minutes, site minutes, cost and invasiveness per normalized procedure, each with a source or a clear "assumption" label. Outputs: visits, procedures, invasive procedures, patient hours, site hours, cost per patient, per-visit timeline.
- Peers (D2): the ClinicalTrials.gov query uses condition, phase, intervention type DRUG/BIOLOGICAL and start year 2015 or later, giving 50 to 200 trials. Compared fields: number of inclusion and exclusion criteria, number of primary and secondary outcomes, enrollment, duration, number of arms, age limits. A smaller set of parsed peer protocol PDFs gives SoA-level burden comparisons.
- Hotspots (D3): "eligibility stricter than X% of peers", "more procedures than X% of peers", restrictive thresholds (age cap, ECOG 0 only, organ function) used by few peers. Each hotspot lists the peer trials as evidence.
- Precedent view (E6): for the top 10 peers, what they chose for primary endpoint, timeframe, key eligibility, sample size and visit count.

## 10. Co-author (E3, E6, E7)

1. Brief form: condition, phase, intervention, comparator, primary question, population, duration.
2. Precedent: peers from step 9, ranked by similarity.
3. Draft: section-by-section LLM generation in M11 order. Each section receives the precedent table and must cite NCT ids for borrowed choices. Sample size comes from the C7 calculator, not the model.
4. Self-check: the draft becomes a Protocol Graph and runs through the same rules engine; issues show next to the draft.
5. Export: USDM JSON validated against the CDISC schema, plus an M11 .docx.

## 11. Score (F2)

```
Completeness   = 100 * (present + thin + 0.25 * missing) / required_items   (M11 + SPIRIT)
Consistency    = max(0, 100 - sum(points of open consistency issues))   critical 10, major 5, minor 2
Burden         = 100 - 0.5 * weighted peer percentile of patient hours (0.5), procedures (0.3), visits (0.2); 50 without peers
Amendment Risk = max(0, 100 - sum(points of hotspots))          critical 15, major 8, minor 3
Pre-Flight     = 0.25*Completeness + 0.35*Consistency + 0.20*Burden + 0.20*Amendment Risk
```

Weights and points live in config/score.yaml and are shown in the UI. Accepted fixes update the score.

## 12. LLM client

- OpenRouter through the OpenAI SDK with `base_url=https://openrouter.ai/api/v1`.
- Settings in `.env`: `OPENROUTER_API_KEY`, `PREFLIGHT_MODEL` (pinned dated id), `LLM_MODE=live|record|replay`.
- Structured output: tested on `deepseek/deepseek-v4-flash-0731` via OpenRouter: `response_format` with a JSON schema works (`LLM_JSON_SCHEMA=true`). The schema is also put in the prompt, and invalid JSON gets one retry with the validation error; a second failure degrades the step instead of failing the run.
- Reasoning is disabled (`reasoning.enabled=false`): DeepSeek V4 otherwise spends about 10k hidden tokens per call. `max_tokens` is capped at 8000, and a truncated answer is never cached.
- Record/replay: responses are keyed by hash(model, prompt, schema version) and stored in data/llm_cache/. The cache for demo and benchmark protocols is committed, so a clean clone reproduces results without a key.
- Every call is logged to `llm_calls` (step, tokens, latency, cost, cache hit). This is the Audit & Trace view.
- OpenRouter provider preference: deny providers that train on or retain prompts.

## 13. Data sources

| Data | How |
|---|---|
| Study records | ClinicalTrials.gov API v2 `/studies` and `/studies/{nct}` |
| Protocol PDFs | `documentSection.largeDocumentModule.largeDocs`; files served from the ClinicalTrials.gov large-docs CDN (verify URL pattern in P0) |
| Registry version history (N7, D4) | The same endpoints the `cthist` R package uses; or run cthist once and commit the CSV |
| M11 TOC | FDA copy of the ICH M11 template, turned into data/standards/m11_toc.yaml |
| SPIRIT 2025 | 34 items from the open-access paper, as data/standards/spirit2025.yaml |
| USDM schema | CDISC DDF-RA repository, pinned release |
| Procedure burden | Labelled assumptions in data/assumptions/procedure_costs.csv |

## 14. API

| Method | Path | Purpose |
|---|---|---|
| POST | /api/protocols | Upload PDF, JSON or docx; returns protocol id |
| POST | /api/protocols/{id}/runs | Start run; body `{mode: "full" or "rules_only"}` |
| GET | /api/runs/{id}/events | SSE progress |
| GET | /api/runs/{id} | Score, sub-scores, status |
| GET | /api/runs/{id}/issues | Issues with filters |
| POST | /api/issues/{id}/decision | Accept or reject, with note; written to audit log |
| GET | /api/runs/{id}/burden | Burden metrics and peer percentiles |
| GET | /api/runs/{id}/precedent | Precedent table |
| GET | /api/runs/{a}/diff/{b} | Resolved, new and unchanged issues; score change |
| POST | /api/drafts | Design brief to draft, precedent, self-check run |
| GET | /api/protocols/{id}/export | `?format=usdm`, `docx` or `report` |
| GET | /api/runs/{id}/trace | Step and LLM call log |
| GET | /api/benchmark | Latest PreflightBench results |
| GET | /api/protocols/{id}/pdf | Original PDF for the viewer |

## 15. Frontend pages

| Route | Content |
|---|---|
| / | Upload, mode toggle (full or confidential), recent runs, banner |
| /runs/[id] | Workspace: PDF with highlights left; issue panel right (filter by severity, category, source); score card on top; accept or reject per issue |
| /runs/[id]/burden | Burden metrics, peer percentile charts, hotspots, precedent table |
| /compare | Pick two runs; resolved, new, unchanged; score change |
| /draft | Brief form, precedent, generated M11 draft with self-check issues, exports |
| /evidence | PreflightBench results, ablation, human baseline, ROI calculator with sliders |
| /runs/[id]/trace | Audit trail and LLM call log |

## 16. Repository layout

```
protocol-preflight/
  backend/
    preflight/
      ingest/        pdf.py, sections.py, soa.py, entities.py, m11_map.py
      graph/         models.py
      checks/        registry.py, completeness.py, consistency.py, numbers.py,
                     design.py, visits.py, sample_size.py, eligibility.py, xref.py, registry_match.py
      reviewers/     committee.py, verifier.py, prompts/
      burden/        burden.py, peers.py, hotspots.py, precedent.py
      coauthor/      draft.py
      export/        usdm.py, m11_docx.py, report.py
      llm/           client.py, cache.py
      ctgov/         client.py
      eval/          inject.py, bench.py, metrics.py, ablation.py
      api/           main.py, routes/
      db.py, score.py, cli.py
    tests/
  frontend/          Next.js app
  data/
    standards/       m11_toc.yaml, spirit2025.yaml, usdm schema
    assumptions/     procedure_costs.csv
    corpus/          protocol PDFs + manifest.csv (NCT, source URL, license note)
    bench/           injected PDFs + answer keys (JSON)
    peers/           cached ClinicalTrials.gov responses
    llm_cache/       committed record/replay responses
  docs/              PRD.md, ARCHITECTURE.md, EVALUATION.md, BUILD_PLAN.md, DEMO_SCRIPT.md
  config/            score.yaml, checks.yaml
  docker-compose.yml, backend/Dockerfile, frontend/Dockerfile
  .github/workflows/ci.yml, Jenkinsfile
  LICENSE (MIT), README.md, .env.example
```
