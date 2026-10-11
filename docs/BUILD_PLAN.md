# Protocol Pre-Flight: Build Plan

One build, in phases, about 22 hours, team of 2 to 4. Feature IDs from docs/PRD.md.

## 1. Rules for the build

1. Contracts first. The Issue schema, Protocol Graph models and API shapes are frozen in hour 1, so frontend and backend work in parallel against mock JSON.
2. Benchmark before checks. The injector and `preflight bench` exist before the first rule, and every check is scored as it lands.
3. Always demoable. Every phase ends with something that runs end to end.
4. Feature freeze at H18. After that, only fixes, numbers and packaging.
5. Record the LLM cache for demo and benchmark protocols as soon as each pipeline step stabilizes.

## 2. Roles

| Role | Owns |
|---|---|
| R1 Backend core | Ingest, Protocol Graph, rules engine, score, API |
| R2 Data and evaluation | Corpus, peers, injector, benchmark, burden, human baseline, case studies, ROI |
| R3 Frontend | All pages, PDF highlights, charts, accept/reject, diff, evidence page |
| R4 AI and co-author | LLM client and cache, reviewers, verifier, co-author, exports, then deck and video |

Final team of 3:

| Person | Takes | Task file |
|---|---|---|
| A Engine | R1, plus R4's LLM client, reviewers, verifier and exports | docs/team/PERSON_A_ENGINE.md |
| B Data and evidence | R2, plus R4's co-author, plus README | docs/team/PERSON_B_DATA_EVIDENCE.md |
| C Frontend | R3, plus deck and video | docs/team/PERSON_C_FRONTEND.md |

Interfaces between the three are frozen in docs/CONTRACTS.md. The per-person files are the source of truth for who does what and when; the table in section 3 shows the same work by role.

## 3. Phases and timeline

| Hours | Phase | R1 Backend | R2 Data and eval | R3 Frontend | R4 AI and co-author |
|---|---|---|---|---|---|
| 0-2 | P0 Foundations | Repo, MIT license, uv, FastAPI skeleton, Pydantic models (Graph, Issue), SQLite | Fetch corpus (10 protocols, dev/test split), manifest, peers cache; m11_toc.yaml, spirit2025.yaml | Next.js, Tailwind, shadcn; layout; mock JSON fixtures from the frozen schema | OpenRouter client; test structured output on DeepSeek V4 Flash; record/replay cache |
| 2-7 | P1 Ingest and harness | A1 sections and spans, A2 M11 mapping, A4 regex entities | Injector (T01-T18) with answer keys; `preflight bench` and metrics; procedure_costs.csv | Upload page; workspace with react-pdf and highlight overlay on mock issues; issue panel | A3 SoA extraction; LLM entity extraction (objectives, endpoints, eligibility) |
| 7-11 | P2 Rules engine | B1-B3, C1-C10, merge, score | Run bench after each check; start human baseline sessions using an injected test file | Wire to real API; SSE progress; score card; filters | C7 calculator (statsmodels); C10 registry match |
| H11 | Milestone M1 | Rules-only run end to end in the UI with first real benchmark numbers |
| 11-15 | P3 AI and P4 Burden | Accept/reject and audit log API; diff API (E5) | D1 burden, D2 peers, D3 hotspots, E6 precedent | Burden and peers page; accept/reject; audit trail view | Review committee, Verifier, guardrails, fix text (E1, C11) |
| H15 | Milestone M2 | Full hybrid run end to end; numbers for N1 to N4 |
| 15-18 | P6 Co-author and exports | Export endpoints; confidential mode (F5) | Ablation runs (N3); real-findings adjudication (N6); case studies (N7) | Compare page; draft page; evidence page with ROI sliders | E3 draft, E7 self-check, E4 USDM JSON and M11 .docx |
| H18 | Feature freeze |
| 18-21 | P7 Evidence and P8 Packaging | Docker, compose, CI, Jenkinsfile, deploy | Final bench run, RESULTS.md, record final LLM cache | Polish, empty and error states, banner everywhere | Deck (10-12 slides), demo video (3 min), README |
| 21-22 | Ship | Clean-clone test on a fresh machine following only the README; submit | | | |

If ahead of schedule at any milestone, take stretch items in order: D5, F7, F6, D4.

## 4. Definition of done per phase

- P0: `docker compose up` shows the frontend talking to a backend stub; corpus downloaded; structured-output test result known.
- P1: `preflight check file.pdf` prints sections with M11 mapping and extracted entities with page numbers; `preflight inject` and `preflight bench` run.
- P2: All rule checks in the registry; bench prints per-type recall; UI shows real issues with working highlights.
- P3/P4: AI findings appear with "verified" status; hallucination count logged; burden and peer charts render from real data.
- P6: A brief produces a draft with precedent citations and self-check issues; USDM export validates against the schema; v1 vs v2 diff works.
- P7: RESULTS.md has N1 to N10 filled from real runs.
- P8: Everything in the packaging checklist below.

## 5. Risks and fallbacks

| Risk | Fallback |
|---|---|
| SoA tables parse badly | Choose demo protocols with clean tables; LLM normalization; report SoA accuracy honestly |
| DeepSeek V4 Flash weak at structured output | JSON prompt plus validation and retry; swap model via `PREFLIGHT_MODEL` |
| OpenRouter rate limits or timeouts | Concurrency limit, retries with backoff, record/replay cache |
| ClinicalTrials.gov throttling | Fetch and cache all peers and documents in P0 |
| Too few trials with registry changes | N7 becomes 2 case studies; D4 dropped |
| Running out of time | Cut in order: D4, F6, F7, D5 (stretch), then E3 drafting quality (keep a basic draft) |

Never cut: the benchmark, the Verifier, clean-clone setup, the banner.

## 6. Packaging checklist

- [ ] Public GitHub repo, MIT license
- [ ] `git status` clean of .md, .env and .pdf files on every push (CONTRACTS.md section 6.1)
- [ ] At submission only: uncomment `!README.md` in .gitignore and push the README. Judges need it; all other .md files stay local
- [ ] README: what it is, 30-second quickstart (`docker compose up`), demo GIF, how to reproduce benchmark, architecture diagram, data sources and citations, limitations, "assists, does not approve"
- [ ] `.env.example`; runs in replay mode without any key
- [ ] docs/ kept local and shared with the team through the Claude project (not pushed)
- [ ] CI green (lint, tests, benchmark gate); Jenkinsfile present
- [ ] Deployed demo URL
- [ ] Demo video, 3 minutes, public link
- [ ] Slide deck, 10-12 slides, public link
- [ ] Devpost submission with team page link (needed for the JEDI interest form)

## 7. Deck outline (10-12 slides)

1. Title and one-line pitch
2. The problem: 57% amended, 45% avoidable, $141k to $535k each, about 3 months delay
3. Who it's for and today's workflow
4. What Pre-Flight does (one diagram)
5. Live example: an issue with highlight, why and fix
6. Burden and peers: heavier than X% of similar trials
7. Co-author: brief to checked M11 draft and USDM JSON
8. The numbers: recall, precision, ablation, hallucination rate
9. Human baseline and retrospective case study
10. ROI: dollars and months, with assumptions shown
11. Architecture, readiness, privacy (confidential mode, clean clone, CI)
12. What's next

## 8. Demo video outline (3 minutes)

| Time | Beat |
|---|---|
| 0:00-0:20 | Problem in three numbers |
| 0:20-0:50 | Upload a real oncology protocol with injected errors; progress; score appears |
| 0:50-1:30 | Click through 3 issues: missing endpoint visit, sample size mismatch, eligibility contradiction; each with highlight, why, fix; accept two |
| 1:30-1:55 | Burden and peers: hotspot with peer trials listed |
| 1:55-2:20 | Upload v2: diff, score jumps |
| 2:20-2:40 | Co-author: brief to checked draft, USDM export |
| 2:40-3:00 | Evidence page: recall, human baseline, ROI; close on "assists, does not approve" |
