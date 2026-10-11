# Protocol Pre-Flight: Team Contracts

Everyone reads this file. It freezes every interface between the three builders so each person can work alone and the pieces connect at the end.

These design documents are published in the repository for transparency (judges asked for PRDs and design docs). During the build they were kept local; the team task files in docs/team/ stay local.

Changing anything here: post the change in the team chat, A updates the master copy and re-shares it, and the matching code change goes in a PR. Nobody changes a shape silently.

## 1. Team and ownership

| Person | Area | Task file |
|---|---|---|
| A | Engine: ingest, Protocol Graph, rules, AI reviewers, score, core API, exports, DevOps | docs/team/PERSON_A_ENGINE.md |
| B | Data and evidence: ClinicalTrials.gov, standards, burden, peers, co-author, benchmark, README | docs/team/PERSON_B_DATA_EVIDENCE.md |
| C | Frontend: every page, then deck and video | docs/team/PERSON_C_FRONTEND.md |

Folder ownership (only the owner edits; others open a PR and tag the owner):

| Path | Owner |
|---|---|
| backend/preflight/ingest, graph, checks (except the two files below), reviewers, llm, export, api/main.py, api/routes/{protocols,runs,issues,exports,trace}.py, db.py, score.py, pipeline.py, cli.py | A |
| backend/preflight/checks/sample_size.py, checks/registry_match.py | B |
| backend/preflight/ctgov, burden, coauthor, eval, api/routes/{analysis,drafts,benchmark}.py | B |
| data/ (all), config/score.yaml, docs/RESULTS.md, docs/DEMO_SCRIPT.md, README.md | B |
| frontend/ (all) | C |
| docker-compose.yml, Dockerfiles, .github/, Jenkinsfile | A |
| docs/CONTRACTS.md (local only, not in git) | A keeps the master copy; changes agreed in chat |
| .gitignore | A |

## 2. Conventions

- Backend: http://localhost:8000, all routes under /api. Frontend: http://localhost:3000.
- Frontend env: `NEXT_PUBLIC_API_URL=http://localhost:8000`, `NEXT_PUBLIC_USE_MOCKS=true|false`.
- IDs are strings with prefixes: `prt_` protocol, `run_` run, `iss_` issue, `aud_` audit entry, `drf_` draft.
- Times are ISO 8601 UTC strings. Money is USD numbers. Durations are seconds.
- Pages are 1-indexed.
- Bounding boxes: `[x0, y0, x1, y1]` in PDF points with origin at the top-left of the page (PyMuPDF convention). The frontend multiplies by its render scale.
- Errors: HTTP 4xx/5xx with body `{"error": {"code": "not_found", "message": "Run run_x not found"}}`.
- Enums:
  - severity: `critical | major | minor | advisory`
  - category: `completeness | consistency | burden | amendment_risk | advisory`
  - source: `rule | ai:medical_writer | ai:clinical_scientist | ai:biostatistician | ai:clinical_ops`
  - status: `open | accepted | rejected`
  - run mode: `full | rules_only`
  - run status: `queued | running | complete | failed`
  - amendment_category: `eligibility | visit_schedule | safety | endpoints | statistics | design | intervention | completeness | clerical | registry`

## 3. Backend interfaces between A and B (Python)

All models are Pydantic v2. A owns graph/models.py and the Issue model; B imports them.

### 3.1 Core models (A, ready by H2)

```python
# backend/preflight/graph/models.py
class Span(BaseModel):
    page: int
    bbox: list[float] | None = None
    quote: str

class Section(BaseModel):
    id: str; m11_id: str | None; title: str; level: int
    page_start: int; page_end: int; text: str

class Endpoint(BaseModel):
    id: str; text: str; measure: str
    timepoints_weeks: list[float]; analysis_ids: list[str]; span: Span

class Objective(BaseModel):
    id: str; level: Literal["primary", "secondary", "exploratory"]
    text: str; endpoint_ids: list[str]; span: Span

class Criterion(BaseModel):
    id: str; kind: Literal["inclusion", "exclusion"]; text: str
    thresholds: list[dict]          # {"test": "ANC", "op": ">=", "value": 1.5, "unit": "10^9/L"}
    span: Span

class Visit(BaseModel):
    id: str; name: str; study_day: float | None
    window_minus: float | None; window_plus: float | None

class Procedure(BaseModel):
    id: str; name: str; normalized_name: str

class SoA(BaseModel):
    visits: list[Visit]; procedures: list[Procedure]
    cells: dict[str, dict[str, bool]]    # cells[visit_id][procedure_id]
    span: Span | None

class Arm(BaseModel):
    name: str; type: str; dose: str | None; route: str | None
    frequency: str | None; duration_weeks: float | None

class Stats(BaseModel):
    sample_size: int | None; alpha: float | None; sided: int | None
    power: float | None; effect_size: float | None; effect_type: str | None   # "mean_diff_sd" | "proportions" | "hazard_ratio"
    control_rate: float | None; dropout: float | None
    analyses: list[dict]               # {"id", "endpoint_id", "method", "span"}

class NumberFact(BaseModel):
    kind: Literal["age_min", "age_max", "dose", "duration_weeks", "sample_size", "ratio", "arms"]
    value: float | str; unit: str | None; span: Span

class Meta(BaseModel):
    title: str; nct_id: str | None; phase: str | None; condition: str | None
    sponsor: str | None; masking: str | None; allocation: str | None
    n_arms: int | None; ratio: str | None

class ProtocolGraph(BaseModel):
    protocol_id: str
    meta: Meta
    sections: list[Section]
    objectives: list[Objective]
    endpoints: list[Endpoint]
    criteria: list[Criterion]
    min_age: float | None; max_age: float | None
    arms: list[Arm]
    soa: SoA | None
    stats: Stats
    numbers: list[NumberFact]
    xrefs: list[dict]                  # {"text", "target", "span"}
    abbreviations: dict                # {"defined": {...}, "used": [...]}
```

```python
# backend/preflight/graph/issues.py
class Where(BaseModel):
    section: str | None; page: int | None; bbox: list[float] | None; quote: str | None

class Why(BaseModel):
    explanation: str; standard_ref: str | None; amendment_category: str

class Fix(BaseModel):
    suggestion: str; patch: dict | None = None

class Issue(BaseModel):
    id: str; check_id: str; source: str; category: str; severity: str
    title: str; where: Where; related: list[Where] = []
    why: Why; fix: Fix | None
    confidence: float; verified: bool; status: str = "open"
```

### 3.2 Check registration (A provides decorator by H2; B writes two checks)

```python
# backend/preflight/checks/registry.py
@dataclass
class CheckContext:
    registry_record: dict | None      # ClinicalTrials.gov study JSON, if nct_id known
    peers: "PeerSet | None"
    settings: dict

def check(id: str, category: str, amendment_category: str,
          standard_ref: str, severity: str): ...

# Every check:
def my_check(graph: ProtocolGraph, ctx: CheckContext) -> list[Issue]: ...
```

B implements `C7` in checks/sample_size.py and `C10` in checks/registry_match.py using this decorator. A's engine discovers all registered checks automatically.

### 3.3 LLM client (A, ready by H2)

```python
# backend/preflight/llm/client.py
async def complete_json(step: str, system: str, user: str,
                        schema: type[BaseModel], temperature: float = 0) -> BaseModel
async def complete_text(step: str, system: str, user: str, temperature: float = 0.2) -> str
```

Handles OpenRouter, the model setting, retries, JSON validation with one retry, record/replay cache, and logging to llm_calls. B uses it for co-author and the LLM-only baseline.

### 3.4 Pipeline hooks

A provides (by H11):

```python
# backend/preflight/pipeline.py
async def ingest_file(path: str, nct_id: str | None = None) -> ProtocolGraph
async def check_graph(graph: ProtocolGraph, mode: str = "full") -> CheckResult
# CheckResult: issues: list[Issue], score: Score, completeness: Completeness
async def run_file(path: str, mode: str = "full", nct_id: str | None = None) -> CheckResult  # used by bench
```

B provides (stubs returning example data by H2, real by H15):

```python
# backend/preflight/ctgov/client.py
async def get_study(nct_id: str) -> dict
async def search_peers(condition: str, phase: str | None, start_year_min: int = 2015, limit: int = 200) -> list[dict]
async def download_protocol(nct_id: str, dest_dir: str) -> str | None
async def get_versions(nct_id: str) -> list[dict]

# backend/preflight/burden/
def find_peers(graph: ProtocolGraph) -> PeerSet
def compute_burden(graph: ProtocolGraph, peers: PeerSet | None) -> BurdenReport
def hotspots(graph: ProtocolGraph, peers: PeerSet) -> list[Issue]       # category "amendment_risk"
def precedent(graph: ProtocolGraph, peers: PeerSet) -> PrecedentTable
def burden_score(report: BurdenReport) -> float                         # 0-100, used in Score

# backend/preflight/coauthor/draft.py
async def draft_from_brief(brief: Brief) -> Draft      # calls A's check_graph for self-check (E7)
```

A's pipeline calls `find_peers`, `compute_burden`, `hotspots` and `burden_score` during a run. The JSON shapes of BurdenReport, PeerSet, PrecedentTable, Brief and Draft are exactly the API responses in section 4.

### 3.5 Database tables (A)

protocols, runs, issues, decisions (audit), llm_calls, step_logs. B stores peer caches as files under data/peers/ and benchmark results under data/bench/results/.

## 4. REST API

Route owners: A for 4.1 to 4.7, B for 4.8 to 4.12. Both must return exactly these shapes. From H2, A's server runs with stub routes that return these examples, so C can test against a real server early.

### 4.1 Health
`GET /api/health` → `{"status": "ok", "llm_mode": "replay", "model": "deepseek/deepseek-v4-flash-0731"}`

### 4.2 Protocols
`POST /api/protocols` (multipart: `file`, optional `nct_id`) → 201
```json
{
  "protocol_id": "prt_8f2a",
  "filename": "NCT00000000_protocol.pdf",
  "title": "A Phase 3, Randomized, Open-Label Study of Drug X Versus Chemotherapy in Advanced NSCLC",
  "pages": 142,
  "nct_id": "NCT00000000",
  "phase": "PHASE3",
  "condition": "Non-small cell lung cancer",
  "uploaded_at": "2026-10-11T02:14:00Z"
}
```
`GET /api/protocols` → `{"items": [ <protocol>, ... ]}` each with `"latest_run": {"run_id": "run_31c9", "score": 62, "status": "complete"}` or `null`.
`GET /api/protocols/{protocol_id}/pdf` → `application/pdf`

### 4.3 Runs
`POST /api/protocols/{protocol_id}/runs` body `{"mode": "full", "version_label": "v1"}` → 202 `{"run_id": "run_31c9", "status": "queued"}`

`GET /api/runs/{run_id}/events` (Server-Sent Events):
```
event: progress
data: {"step": "ingest", "status": "done", "pct": 15, "message": "142 pages, 61 sections"}

event: complete
data: {"run_id": "run_31c9"}

event: error
data: {"message": "SoA table not found"}
```
Steps in order: `ingest, map_sections, extract_soa, extract_entities, rules, reviewers, verify, burden, peers, score`. In rules_only mode, `reviewers` and `verify` are sent with `"status": "skipped"`.

`GET /api/runs/{run_id}` →
```json
{
  "run_id": "run_31c9",
  "protocol_id": "prt_8f2a",
  "version_label": "v1",
  "mode": "full",
  "status": "complete",
  "started_at": "2026-10-11T02:14:05Z",
  "finished_at": "2026-10-11T02:15:39Z",
  "duration_s": 94.2,
  "llm_cost_usd": 0.12,
  "score": {
    "overall": 62,
    "completeness": 81,
    "consistency": 44,
    "burden": 58,
    "amendment_risk": 70,
    "weights": {"completeness": 0.25, "consistency": 0.35, "burden": 0.20, "amendment_risk": 0.20}
  },
  "counts": {"critical": 3, "major": 7, "minor": 11, "advisory": 4, "open": 25, "accepted": 0, "rejected": 0}
}
```
`GET /api/protocols/{protocol_id}/runs` → `{"items": [ <run summary>, ... ]}`

### 4.4 Issues
`GET /api/runs/{run_id}/issues?severity=&category=&source=&status=` →
```json
{
  "total": 25,
  "items": [
    {
      "id": "iss_01",
      "check_id": "C1",
      "source": "rule",
      "category": "consistency",
      "severity": "critical",
      "title": "Primary endpoint at Week 24 has no Week 24 tumor assessment in the Schedule of Activities",
      "where": {"section": "1.3 Schedule of Activities", "page": 14, "bbox": [72.0, 310.5, 540.0, 330.2], "quote": "Week 24 ... Tumor imaging (CT/MRI)"},
      "related": [{"section": "3.1 Primary Objective", "page": 21, "bbox": [72.0, 140.0, 540.0, 172.0], "quote": "Objective response rate at Week 24 per RECIST 1.1"}],
      "why": {
        "explanation": "The primary endpoint is measured at Week 24, but the Schedule of Activities has no tumor imaging at Week 24. Sites will not collect the primary endpoint as written.",
        "standard_ref": "ICH M11 1.3, 3; SPIRIT 2025 item 13",
        "amendment_category": "visit_schedule"
      },
      "fix": {
        "suggestion": "Add tumor imaging (CT/MRI) to the Week 24 visit, or change the endpoint timepoint to the nearest scheduled imaging visit (Week 25).",
        "patch": {"op": "set_soa_cell", "visit": "W24", "procedure": "Tumor imaging (CT/MRI)", "value": true}
      },
      "confidence": 0.95,
      "verified": true,
      "status": "open"
    }
  ]
}
```

`POST /api/issues/{issue_id}/decision` body `{"decision": "accepted", "note": "Added imaging at W24", "user": "reviewer"}` →
```json
{"issue_id": "iss_01", "status": "accepted", "audit_id": "aud_77", "score": { "overall": 68, "completeness": 81, "consistency": 59, "burden": 58, "amendment_risk": 70, "weights": {"completeness": 0.25, "consistency": 0.35, "burden": 0.20, "amendment_risk": 0.20} }}
```
Accepting removes the issue's points from the score. Rejecting keeps the score unchanged and records the note.

### 4.5 Completeness
`GET /api/runs/{run_id}/completeness` →
```json
{
  "summary": {"present": 41, "thin": 6, "missing": 3, "required": 50},
  "items": [
    {"framework": "M11", "item_id": "5.1", "title": "Inclusion Criteria", "status": "present", "pages": [23, 24], "note": null},
    {"framework": "M11", "item_id": "3", "title": "Trial Objectives and Associated Estimands", "status": "thin", "pages": [21], "note": "No estimand attributes (population, intercurrent events, summary measure)"},
    {"framework": "SPIRIT", "item_id": "23", "title": "Data monitoring", "status": "missing", "pages": [], "note": null}
  ]
}
```

### 4.6 Diff
`GET /api/runs/{from_run_id}/diff/{to_run_id}` →
```json
{
  "from_run": "run_31c9",
  "to_run": "run_52aa",
  "score_from": {"overall": 62, "completeness": 81, "consistency": 44, "burden": 58, "amendment_risk": 70},
  "score_to":   {"overall": 91, "completeness": 96, "consistency": 92, "burden": 74, "amendment_risk": 88},
  "resolved": [ <issue>, ... ],
  "new": [ <issue>, ... ],
  "unchanged": [ <issue>, ... ]
}
```

### 4.7 Exports and trace
`GET /api/runs/{run_id}/export?format=usdm|docx|report_pdf|report_csv` → file download with `Content-Disposition`.

`GET /api/runs/{run_id}/trace` →
```json
{
  "steps": [{"step": "extract_soa", "status": "done", "started_at": "2026-10-11T02:14:20Z", "duration_s": 18.4}],
  "llm_calls": [{"step": "extract_soa", "model": "deepseek/deepseek-v4-flash-0731", "tokens_in": 9120, "tokens_out": 1430, "latency_s": 6.2, "cost_usd": 0.0019, "cache_hit": false}],
  "verifier": {"ai_findings": 18, "dropped_ungrounded": 3, "shown": 15},
  "audit": [{"audit_id": "aud_77", "issue_id": "iss_01", "decision": "accepted", "user": "reviewer", "note": "Added imaging at W24", "at": "2026-10-11T02:20:00Z"}]
}
```

### 4.8 Burden (B)
`GET /api/runs/{run_id}/burden` →
```json
{
  "per_patient": {"visits": 18, "procedures_total": 214, "invasive": 6, "patient_hours": 61.5, "site_hours": 88.0, "cost_usd": 18400},
  "by_visit": [
    {"visit": "Screening", "study_day": -28, "patient_minutes": 240, "site_minutes": 310, "procedures": ["Informed consent", "CT/MRI", "Hematology", "Chemistry", "ECG"]},
    {"visit": "C1D1", "study_day": 1, "patient_minutes": 300, "site_minutes": 360, "procedures": ["Vitals", "PK sample", "Infusion"]}
  ],
  "orphan_procedures": [{"name": "Exploratory skin biopsy", "occurrences": 3, "patient_minutes": 135, "cost_usd": 2100}],
  "peer_percentiles": {"patient_hours": 82, "procedures_total": 77, "visits": 64, "n_peers_with_soa": 24},
  "assumptions": {"file": "data/assumptions/procedure_costs.csv", "version": "2026-10-11"}
}
```

### 4.9 Peers (B)
`GET /api/runs/{run_id}/peers` →
```json
{
  "query": {"condition": "Non-small cell lung cancer", "phase": "PHASE3", "start_year_min": 2015},
  "n": 143,
  "metrics": [
    {"metric": "n_inclusion_criteria", "label": "Inclusion criteria", "value": 14, "percentile": 71, "peer_median": 11, "peer_p25": 8, "peer_p75": 15, "distribution": [6, 8, 9, 11, 11, 12, 15, 19]},
    {"metric": "n_exclusion_criteria", "label": "Exclusion criteria", "value": 31, "percentile": 88, "peer_median": 19, "peer_p25": 14, "peer_p75": 25, "distribution": [10, 14, 17, 19, 21, 25, 30]}
  ],
  "hotspot_issue_ids": ["iss_19", "iss_20"],
  "trials": [{"nct_id": "NCT00000001", "title": "Study of Drug Y in NSCLC", "sponsor": "Sponsor Co", "phase": "PHASE3", "enrollment": 610, "start_date": "2019-03"}]
}
```
`distribution` holds the raw peer values (or a sample of up to 200) for drawing histograms.

### 4.10 Precedent (B)
`GET /api/runs/{run_id}/precedent` →
```json
{
  "this_protocol": {"primary_endpoint": "ORR per RECIST 1.1", "primary_timeframe": "Week 24", "key_eligibility": ["ECOG 0", "Age 18-75"], "enrollment": 420, "n_visits": 18},
  "rows": [
    {"nct_id": "NCT00000001", "title": "Study of Drug Y in NSCLC", "sponsor": "Sponsor Co", "phase": "PHASE3", "similarity": 0.82,
     "primary_endpoint": "PFS per RECIST 1.1", "primary_timeframe": "Up to 36 months",
     "key_eligibility": ["ECOG 0-1", "Age 18+"], "enrollment": 610, "n_visits": 14}
  ]
}
```

### 4.11 Drafts (B)
`POST /api/drafts` body (Brief) →
```json
{"condition": "Non-small cell lung cancer", "phase": "PHASE2", "intervention": "Drug X 350 mg IV Q3W", "comparator": "Docetaxel",
 "primary_question": "Does Drug X improve ORR vs docetaxel?", "population": "Adults with previously treated advanced NSCLC",
 "duration_weeks": 52, "alpha": 0.05, "power": 0.8, "expected_effect": {"type": "proportions", "control": 0.12, "treatment": 0.27}, "dropout": 0.1}
```
→ 202 `{"draft_id": "drf_11", "status": "queued"}`

`GET /api/drafts/{draft_id}/events` → SSE like runs, steps: `precedent, sample_size, draft_sections, build_graph, self_check, burden`.

`GET /api/drafts/{draft_id}` →
```json
{
  "draft_id": "drf_11",
  "status": "complete",
  "brief": { "...": "as submitted" },
  "precedent": { "...": "same shape as 4.10" },
  "sample_size": {"n_total": 210, "n_per_arm": 105, "method": "Two-proportion z-test, two-sided", "inputs": {"alpha": 0.05, "power": 0.8, "control": 0.12, "treatment": 0.27, "dropout": 0.1}},
  "sections": [
    {"m11_id": "3", "title": "Trial Objectives and Associated Estimands", "markdown": "### 3.1 Primary Objective\n...", "citations": ["NCT00000001", "NCT00000002"]}
  ],
  "burden": { "...": "same shape as 4.8" },
  "self_check": {"score": { "...": "same shape as score in 4.3" }, "issues": [ <issue>, ... ]}
}
```
`GET /api/drafts/{draft_id}/export?format=usdm|docx` → file download.

### 4.12 Benchmark (B)
`GET /api/benchmark` →
```json
{
  "generated_at": "2026-10-11T14:00:00Z",
  "model": "deepseek/deepseek-v4-flash-0731",
  "test_set": {"protocols": 7, "injected_errors": 84},
  "overall": {"recall": 0.88, "precision": 0.83, "f1": 0.85},
  "by_type": [{"type": "T01", "name": "Endpoint visit removed from SoA", "n": 6, "found": 6, "recall": 1.0}],
  "by_category": [{"amendment_category": "eligibility", "n": 14, "recall": 0.86}],
  "ablation": [
    {"config": "rules_only", "recall": 0.71, "precision": 0.94, "f1": 0.81},
    {"config": "llm_only", "recall": 0.52, "precision": 0.41, "f1": 0.46},
    {"config": "full", "recall": 0.88, "precision": 0.83, "f1": 0.85}
  ],
  "hallucination": {"ai_findings": 120, "dropped_ungrounded": 17, "shown_ungrounded": 0},
  "false_alarms_per_clean_protocol": 1.4,
  "human_baseline": null,
  "real_findings": {"sampled": 30, "precision": 0.77, "kappa": 0.71},
  "soa_extraction": {"protocols": 3, "cell_accuracy": 0.93},
  "speed_cost": {"median_seconds": 92, "median_usd": 0.11},
  "case_studies": [{"nct_id": "NCT00000003", "change": "ECOG 0 relaxed to ECOG 0-1 in version 6", "flagged_in_earlier_version": true, "summary": "Pre-Flight flagged ECOG 0 as stricter than 91% of peers."}]
}
```
All numbers above are placeholders. Real values come from `preflight bench`. Blocks that were not measured are `null`: the human-baseline study (N5) was dropped for time, so `human_baseline` is always `null` in this release.

### 4.13 ROI (computed in the frontend)
No endpoint. The evidence page computes, per phase:
```
expected_avoidable_cost = p_amend * share_avoidable * cost_per_amendment
expected_avoided_cost   = expected_avoidable_cost * catch_rate
expected_avoided_months = p_amend * share_avoidable * 3 * catch_rate
```
Defaults: p_amend 0.57; share_avoidable 0.45 (slider down to 0.33); cost_per_amendment 141000 (Phase II) or 535000 (Phase III); catch_rate = `overall.recall` from /api/benchmark. Show the sources under the sliders (see docs/EVALUATION.md section 7).

## 5. Mocks

- C copies every example above into frontend/mocks/*.json on day one and builds against them with `NEXT_PUBLIC_USE_MOCKS=true`.
- B puts one real demo protocol PDF in data/corpus/ by H2. A runs a quick script that produces a mock issues file with real page numbers and bboxes for that PDF (frontend/mocks/issues_real.json) by H4, so highlights can be tested on a real document early.
- Mock SSE: the frontend replays the step list with a 1-second delay per step.

## 6. Git workflow

### 6.1 .gitignore (A commits this as the very first commit, before anything else)

Rule: no Markdown files are pushed. That covers every planning doc, team file and generated .md. Secrets, environments, databases and downloaded PDFs are not pushed either.

```gitignore
# --- Markdown: never pushed ---
*.md
docs/
# README.md is also ignored for now. Judges need a README on GitHub,
# so uncomment the next line before submission (BUILD_PLAN.md section 6):
# !README.md

# --- Secrets ---
.env
.env.*
!.env.example

# --- Python ---
__pycache__/
*.py[cod]
.venv/
venv/
.pytest_cache/
.ruff_cache/
.mypy_cache/
*.egg-info/
dist/
build/

# --- Node / Next.js ---
node_modules/
frontend/.next/
frontend/out/
frontend/.vercel/
*.tsbuildinfo
next-env.d.ts
npm-debug.log*
yarn-error.log*
pnpm-debug.log*

# --- App runtime ---
*.db
*.sqlite
*.sqlite3
backend/uploads/
backend/exports/
logs/
*.log

# --- Data: PDFs are re-downloaded or regenerated, not committed ---
data/corpus/*.pdf
data/bench/*.pdf
data/peers/protocols/*.pdf
# Committed on purpose: data/corpus/manifest.csv, data/bench/*.json (answer keys),
# data/bench/results/, data/peers/*.json, data/llm_cache/, data/standards/, data/assumptions/

# --- OS / editors ---
.DS_Store
Thumbs.db
.idea/
.vscode/
```

Because PDFs are not committed, a clean clone gets them with `preflight fetch` (downloads every file in data/corpus/manifest.csv) and `preflight inject --all` (regenerates injected files from the committed answer keys and seeds). B makes sure both commands work before H18.

Check before every push: `git status` shows no .md file, no .env, no .pdf.

### 6.2 Branches

- One repo, branch `main`. Each person works on `a/...`, `b/...`, `c/...` branches and merges small PRs often (at least every 2 to 3 hours).
- Folder ownership prevents most conflicts. Shared files (pyproject.toml, docker-compose.yml) are edited only by A; ask in chat.
- Commit any new LLM cache files under data/llm_cache/ together with the code that created them.

## 7. Sync points

| Time | What |
|---|---|
| H0:45 | A pushes the repo skeleton. Everyone clones and runs it |
| H2 | Contract check: models, decorator, LLM client, stub server live; B has the sample PDF and standards YAML in; C has mocks running |
| H7 | Quick sync: blockers, any contract changes |
| H11 | M1 integration: frontend switches workspace pages to the real API (rules-only runs) |
| H15 | M2 integration: full runs, burden, peers, precedent live in UI |
| H18 | Feature freeze |
| H21 | Clean-clone test on a machine that has never run the project |
