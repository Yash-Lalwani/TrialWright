// TypeScript mirror of docs/CONTRACTS.md section 2 (enums) and section 4 (REST API).
// Field names and nesting must match the contract exactly. If the contract changes,
// change it here first and let the compiler point at every affected screen.

// ---------- Enums (CONTRACTS.md §2) ----------

export const SEVERITIES = ["critical", "major", "minor", "advisory"] as const;
export type Severity = (typeof SEVERITIES)[number];

export const CATEGORIES = [
  "completeness",
  "consistency",
  "burden",
  "amendment_risk",
  "advisory",
] as const;
export type Category = (typeof CATEGORIES)[number];

export const SOURCES = [
  "rule",
  "ai:medical_writer",
  "ai:clinical_scientist",
  "ai:biostatistician",
  "ai:clinical_ops",
] as const;
export type Source = (typeof SOURCES)[number];

export const ISSUE_STATUSES = ["open", "accepted", "rejected"] as const;
export type IssueStatus = (typeof ISSUE_STATUSES)[number];

export const RUN_MODES = ["full", "rules_only"] as const;
export type RunMode = (typeof RUN_MODES)[number];

export type RunStatus = "queued" | "running" | "complete" | "failed";

export type AmendmentCategory =
  | "eligibility"
  | "visit_schedule"
  | "safety"
  | "endpoints"
  | "statistics"
  | "design"
  | "intervention"
  | "completeness"
  | "clerical"
  | "registry";

/** [x0, y0, x1, y1] in PDF points, origin top-left of the page (PyMuPDF convention). */
export type BBox = [number, number, number, number];

export interface ApiErrorBody {
  error: { code: string; message: string };
}

// ---------- 4.1 Health ----------

export interface Health {
  status: string;
  llm_mode: string;
  model: string;
}

// ---------- 4.2 Protocols ----------

// The backend returns null for title/pages when it cannot read them (e.g. a JSON upload).
export interface Protocol {
  protocol_id: string;
  filename: string;
  title: string | null;
  pages: number | null;
  nct_id: string | null;
  phase: string | null;
  condition: string | null;
  uploaded_at: string;
}

export interface LatestRun {
  run_id: string;
  /** null while a run is queued/running or after it failed. */
  score: number | null;
  status: RunStatus;
}

export interface ProtocolListItem extends Protocol {
  latest_run: LatestRun | null;
}

export interface ProtocolList {
  items: ProtocolListItem[];
}

// ---------- 4.3 Runs ----------

export interface CreateRunRequest {
  mode: RunMode;
  version_label: string;
}

export interface CreateRunResponse {
  run_id: string;
  status: RunStatus;
}

export const RUN_STEPS = [
  "ingest",
  "map_sections",
  "extract_soa",
  "extract_entities",
  "rules",
  "reviewers",
  "verify",
  "burden",
  "peers",
  "score",
] as const;
export type RunStep = (typeof RUN_STEPS)[number];

export type StepStatus = "running" | "done" | "skipped" | "failed";

export interface ProgressEvent {
  step: RunStep;
  status: StepStatus;
  pct: number;
  message: string;
}

export interface CompleteEvent {
  run_id: string;
}

export interface ErrorEvent {
  message: string;
}

export interface ScoreWeights {
  completeness: number;
  consistency: number;
  burden: number;
  amendment_risk: number;
}

export interface SubScores {
  overall: number;
  completeness: number;
  consistency: number;
  burden: number;
  amendment_risk: number;
}

export interface Score extends SubScores {
  weights: ScoreWeights;
}

export interface IssueCounts {
  critical: number;
  major: number;
  minor: number;
  advisory: number;
  open: number;
  accepted: number;
  rejected: number;
}

export interface Run {
  run_id: string;
  protocol_id: string;
  /** Optional when the run is started (A's RunIn), so null is possible. */
  version_label: string | null;
  mode: RunMode;
  status: RunStatus;
  started_at: string;
  finished_at: string | null;
  duration_s: number | null;
  llm_cost_usd: number | null;
  score: Score | null;
  counts: IssueCounts | null;
}

export interface RunList {
  items: Run[];
}

// ---------- 4.4 Issues ----------

export interface Where {
  section: string | null;
  page: number | null;
  bbox: BBox | null;
  quote: string | null;
}

export interface Why {
  explanation: string;
  standard_ref: string | null;
  amendment_category: AmendmentCategory;
}

export interface Fix {
  suggestion: string;
  patch: Record<string, unknown> | null;
}

export interface Issue {
  id: string;
  check_id: string;
  source: Source;
  category: Category;
  severity: Severity;
  title: string;
  where: Where;
  related: Where[];
  why: Why;
  fix: Fix | null;
  confidence: number;
  verified: boolean;
  status: IssueStatus;
}

export interface IssueList {
  total: number;
  items: Issue[];
}

export interface IssueFilters {
  severity?: Severity;
  category?: Category;
  source?: Source;
  status?: IssueStatus;
}

export interface DecisionRequest {
  decision: Exclude<IssueStatus, "open">;
  note: string;
  user: string;
}

export interface DecisionResponse {
  issue_id: string;
  status: IssueStatus;
  audit_id: string;
  score: Score;
}

// ---------- 4.5 Completeness ----------

export type CompletenessStatus = "present" | "thin" | "missing";

export interface CompletenessItem {
  framework: "M11" | "SPIRIT";
  item_id: string;
  title: string;
  status: CompletenessStatus;
  pages: number[];
  note: string | null;
}

export interface Completeness {
  summary: { present: number; thin: number; missing: number; required: number };
  items: CompletenessItem[];
}

// ---------- 4.6 Diff ----------

export interface RunDiff {
  from_run: string;
  to_run: string;
  score_from: SubScores;
  score_to: SubScores;
  resolved: Issue[];
  new: Issue[];
  unchanged: Issue[];
}

// ---------- 4.7 Exports and trace ----------

export type ExportFormat = "usdm" | "docx" | "report_pdf" | "report_csv";

export interface Trace {
  steps: { step: RunStep; status: StepStatus; started_at: string; duration_s: number }[];
  llm_calls: {
    step: string;
    model: string;
    tokens_in: number;
    tokens_out: number;
    latency_s: number;
    cost_usd: number;
    cache_hit: boolean;
  }[];
  verifier: { ai_findings: number; dropped_ungrounded: number; shown: number };
  audit: {
    audit_id: string;
    issue_id: string;
    decision: Exclude<IssueStatus, "open">;
    user: string;
    note: string;
    at: string;
  }[];
}

// ---------- 4.8 Burden ----------

export interface Burden {
  per_patient: {
    visits: number;
    procedures_total: number;
    invasive: number;
    patient_hours: number;
    site_hours: number;
    cost_usd: number;
  };
  by_visit: {
    visit: string;
    study_day: number;
    patient_minutes: number;
    site_minutes: number;
    procedures: string[];
  }[];
  orphan_procedures: {
    name: string;
    occurrences: number;
    patient_minutes: number;
    cost_usd: number;
  }[];
  peer_percentiles: {
    patient_hours: number;
    procedures_total: number;
    visits: number;
    n_peers_with_soa: number;
  };
  assumptions: { file: string; version: string };
}

// ---------- 4.9 Peers ----------

export interface PeerTrial {
  nct_id: string;
  title: string;
  sponsor: string;
  phase: string;
  enrollment: number;
  start_date: string;
}

export interface Peers {
  query: { condition: string; phase: string; start_year_min: number };
  n: number;
  metrics: {
    metric: string;
    label: string;
    value: number;
    percentile: number;
    peer_median: number;
    peer_p25: number;
    peer_p75: number;
    distribution: number[];
  }[];
  hotspot_issue_ids: string[];
  trials: PeerTrial[];
}

// ---------- 4.10 Precedent ----------

export interface PrecedentProtocolSummary {
  primary_endpoint: string;
  primary_timeframe: string;
  key_eligibility: string[];
  enrollment: number;
  n_visits: number;
}

export interface Precedent {
  this_protocol: PrecedentProtocolSummary;
  rows: (PrecedentProtocolSummary & {
    nct_id: string;
    title: string;
    sponsor: string;
    phase: string;
    similarity: number;
  })[];
}

// ---------- 4.11 Drafts ----------

export interface Brief {
  condition: string;
  phase: string;
  intervention: string;
  comparator: string;
  primary_question: string;
  population: string;
  duration_weeks: number;
  alpha: number;
  power: number;
  expected_effect: { type: string; control: number; treatment: number };
  dropout: number;
}

export interface CreateDraftResponse {
  draft_id: string;
  status: RunStatus;
}

export const DRAFT_STEPS = [
  "precedent",
  "sample_size",
  "draft_sections",
  "build_graph",
  "self_check",
  "burden",
] as const;
export type DraftStep = (typeof DRAFT_STEPS)[number];

export interface DraftProgressEvent {
  step: DraftStep;
  status: StepStatus;
  pct: number;
  message: string;
}

export interface Draft {
  draft_id: string;
  status: RunStatus;
  brief: Brief;
  precedent: Precedent;
  sample_size: {
    n_total: number;
    n_per_arm: number;
    method: string;
    inputs: { alpha: number; power: number; control: number; treatment: number; dropout: number };
  };
  sections: { m11_id: string; title: string; markdown: string; citations: string[] }[];
  burden: Burden;
  self_check: { score: Score; issues: Issue[] };
}

// ---------- 4.12 Benchmark ----------

export interface Benchmark {
  generated_at: string;
  model: string;
  test_set: { protocols: number; injected_errors: number };
  overall: { recall: number; precision: number; f1: number };
  by_type: { type: string; name: string; n: number; found: number; recall: number }[];
  by_category: { amendment_category: AmendmentCategory; n: number; recall: number }[];
  ablation: { config: string; recall: number; precision: number; f1: number }[];
  hallucination: { ai_findings: number; dropped_ungrounded: number; shown_ungrounded: number };
  false_alarms_per_clean_protocol: number;
  human_baseline: {
    protocol: string;
    participants: { id: string; found: number; minutes: number }[];
    preflight: { found: number; seconds: number };
    total_errors: number;
  };
  real_findings: { sampled: number; precision: number; kappa: number };
  soa_extraction: { protocols: number; cell_accuracy: number };
  speed_cost: { median_seconds: number; median_usd: number };
  case_studies: {
    nct_id: string;
    change: string;
    flagged_in_earlier_version: boolean;
    summary: string;
  }[];
}
