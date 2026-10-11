# Protocol Pre-Flight: demo script (3 minutes)

Record at 1440×900 or larger, browser zoom 100%, on the live demo
(https://frontend-production-a539.up.railway.app) or a local `docker compose up`. Open every page once before recording
so nothing loads cold. The demo protocol is **NCT04698187** (CMP-001 + nivolumab in advanced melanoma, Phase 2,
Regeneron). It is already reviewed on the live demo, together with an earlier draft of the same protocol that contains
planted errors.

| Time | Screen | Say (roughly) |
|---|---|---|
| 0:00-0:20 | Home page | "57% of trial protocols get a substantial amendment, almost half of them avoidable, at up to half a million dollars each. Pre-Flight catches those problems before the protocol is finalised. It assists authors; it doesn't approve protocols." |
| 0:20-0:40 | Upload `NCT04698187_protocol.pdf` with the NCT id, Full review, Start | "A real 134-page Regeneron melanoma protocol from ClinicalTrials.gov. Pre-Flight reads the PDF, maps it to ICH M11, extracts the Schedule of Activities, objectives, endpoints and eligibility, then runs rule checks and four AI reviewers." (Progress steps stream in.) |
| 0:40-1:20 | Review workspace | Point at the score and the four sub-scores. Click the major issue *"Endpoint 'Anti-Qb antibodies' has no analysis method"*: "Every finding says where, why, and how to fix it." Click the hotspot *"25 exclusion criteria: 85% of similar trials have fewer"*: the PDF jumps to page 39 and highlights the criterion. Click an AI finding and point at **Verified**: "An AI finding is only shown if its quote is actually on the cited page." Accept one issue with a note and watch the score update. |
| 1:20-1:45 | Burden & peers | "Participant burden: 14 visits, 44 hours, $16k per patient, heavier than 80% of 34 peer trials. Each metric is compared with 200 similar melanoma trials; the outliers are amendment-risk hotspots, with precedent from the closest trials." |
| 1:45-2:05 | Compare versions: earlier draft → final protocol | "Upload a revision and see what changed: 25 issues resolved, including a sample size that disagreed between sections, a nivolumab dose mismatch and overlapping visit windows. Score 49 → 72." |
| 2:05-2:25 | Draft | Show the brief and a generated draft (pre-generate one before recording): "From a short brief, Pre-Flight drafts M11 sections citing precedent trials, computes the sample size with a calculator rather than the model, and runs its own checks on the draft." |
| 2:25-2:50 | Evidence | "We measure ourselves. On 65 errors injected into 7 held-out protocols, the full system has 90% precision and beats both rules alone and an LLM alone, which gets only 10% precision. Zero ungrounded AI findings shown." Move the ROI sliders: "At our measured catch rate, about $59k expected savings per Phase III protocol." |
| 2:50-3:00 | Export menu, then the banner | "USDM JSON, M11 Word document, and an issue report. Open source, MIT, runs from a clean clone. Pre-Flight assists protocol authors; it doesn't approve protocols." |

## Before recording

1. Live demo: open `/`, the review of NCT04698187, its Burden & peers and Audit & trace pages, `/compare` with both
   versions selected, `/draft` with a finished draft, and `/evidence`.
2. Local instead: `docker compose up --build`, run `uv run preflight fetch --split dev` and `uv run preflight inject --set dev`
   in `backend/`, then upload `data/bench/NCT04698187_s1.pdf` as the earlier draft and
   `data/corpus/NCT04698187_protocol.pdf` as the final version.
3. Keep the banner visible in the opening and closing shots.
