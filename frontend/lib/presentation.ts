// Display metadata for contract enums. Severity is always shown as icon + label +
// colour so it never relies on colour alone.

import {
  Bot,
  CircleAlert,
  Info,
  ListChecks,
  OctagonAlert,
  TriangleAlert,
  type LucideIcon,
} from "lucide-react";

import type {
  AmendmentCategory,
  Category,
  CompletenessStatus,
  DraftStep,
  IssueStatus,
  RunMode,
  RunStep,
  Severity,
  Source,
} from "./types";

export const SEVERITY_META: Record<
  Severity,
  { label: string; icon: LucideIcon; text: string; tint: string; border: string; rank: number }
> = {
  critical: {
    label: "Critical",
    icon: OctagonAlert,
    text: "text-sev-critical",
    tint: "bg-sev-critical-bg",
    border: "border-sev-critical-border",
    rank: 0,
  },
  major: {
    label: "Major",
    icon: TriangleAlert,
    text: "text-sev-major",
    tint: "bg-sev-major-bg",
    border: "border-sev-major-border",
    rank: 1,
  },
  minor: {
    label: "Minor",
    icon: CircleAlert,
    text: "text-sev-minor",
    tint: "bg-sev-minor-bg",
    border: "border-sev-minor-border",
    rank: 2,
  },
  advisory: {
    label: "Advisory",
    icon: Info,
    text: "text-sev-advisory",
    tint: "bg-sev-advisory-bg",
    border: "border-sev-advisory-border",
    rank: 3,
  },
};

/** Raw colour per severity for SVG/canvas overlays where classes don't apply. */
export const SEVERITY_COLOR: Record<Severity, string> = {
  critical: "var(--sev-critical)",
  major: "var(--sev-major)",
  minor: "var(--sev-minor)",
  advisory: "var(--sev-advisory)",
};

export const CATEGORY_LABEL: Record<Category, string> = {
  completeness: "Completeness",
  consistency: "Consistency",
  burden: "Burden",
  amendment_risk: "Amendment risk",
  advisory: "Advisory",
};

export const SOURCE_META: Record<Source, { label: string; short: string; icon: LucideIcon }> = {
  rule: { label: "Rule check", short: "Rule", icon: ListChecks },
  "ai:medical_writer": { label: "AI reviewer: Medical Writer", short: "Medical Writer", icon: Bot },
  "ai:clinical_scientist": { label: "AI reviewer: Clinical Scientist", short: "Clinical Scientist", icon: Bot },
  "ai:biostatistician": { label: "AI reviewer: Biostatistician", short: "Biostatistician", icon: Bot },
  "ai:clinical_ops": { label: "AI reviewer: Clinical Ops", short: "Clinical Ops", icon: Bot },
};

export const STATUS_LABEL: Record<IssueStatus, string> = {
  open: "Open",
  accepted: "Accepted",
  rejected: "Rejected",
};

export const AMENDMENT_LABEL: Record<AmendmentCategory, string> = {
  eligibility: "Eligibility",
  visit_schedule: "Visit schedule",
  safety: "Safety",
  endpoints: "Endpoints",
  statistics: "Statistics",
  design: "Design",
  intervention: "Intervention",
  completeness: "Completeness",
  clerical: "Clerical",
  registry: "Registry",
};

export const MODE_LABEL: Record<RunMode, string> = {
  full: "Full review",
  rules_only: "Confidential (rules only)",
};

export const RUN_STEP_LABEL: Record<RunStep, string> = {
  ingest: "Read PDF",
  map_sections: "Map sections to ICH M11",
  extract_soa: "Extract Schedule of Activities",
  extract_entities: "Extract objectives, endpoints and eligibility",
  rules: "Run rule checks",
  reviewers: "AI review committee",
  verify: "Verify AI findings against the text",
  burden: "Compute participant burden",
  peers: "Compare with peer trials",
  score: "Score",
};

export const DRAFT_STEP_LABEL: Record<DraftStep, string> = {
  precedent: "Find precedent trials",
  sample_size: "Calculate sample size",
  draft_sections: "Draft M11 sections",
  build_graph: "Build Protocol Graph",
  self_check: "Self-check",
  burden: "Compute burden",
};

export const COMPLETENESS_META: Record<CompletenessStatus, { label: string; text: string; tint: string }> = {
  present: { label: "Present", text: "text-status-present", tint: "bg-status-present-bg" },
  thin: { label: "Thin", text: "text-status-thin", tint: "bg-status-thin-bg" },
  missing: { label: "Missing", text: "text-status-missing", tint: "bg-status-missing-bg" },
};

export const SUBSCORE_LABEL = {
  completeness: "Completeness",
  consistency: "Consistency",
  burden: "Burden",
  amendment_risk: "Amendment risk",
} as const;

const dateTime = new Intl.DateTimeFormat("en-US", {
  month: "short",
  day: "numeric",
  hour: "2-digit",
  minute: "2-digit",
  timeZone: "UTC",
  timeZoneName: "short",
});

export const formatDateTime = (iso: string) => dateTime.format(new Date(iso));

export function formatDuration(seconds: number | null | undefined): string {
  if (seconds == null) return "-";
  if (seconds < 60) return `${seconds.toFixed(1)} s`;
  const m = Math.floor(seconds / 60);
  return `${m} min ${Math.round(seconds - m * 60)} s`;
}

export const formatPercent = (value: number) => `${Math.round(value * 100)}%`;

export const formatUsd = (value: number) =>
  new Intl.NumberFormat("en-US", { style: "currency", currency: "USD", maximumFractionDigits: value < 1 ? 2 : 0 }).format(value);

/** ClinicalTrials.gov phase codes to readable text: "PHASE3" -> "Phase 3", "PHASE1_PHASE2" -> "Phase 1/2". */
export function formatPhase(phase: string | null): string {
  if (!phase) return "Phase not stated";
  const numbers = phase.match(/\d/g);
  return numbers ? `Phase ${numbers.join("/")}` : phase;
}
