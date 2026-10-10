"use client";

import { X } from "lucide-react";

import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { CATEGORY_LABEL, SEVERITY_META, SOURCE_META, STATUS_LABEL } from "@/lib/presentation";
import {
  CATEGORIES,
  ISSUE_STATUSES,
  SEVERITIES,
  SOURCES,
  type Category,
  type Issue,
  type IssueStatus,
  type Severity,
  type Source,
} from "@/lib/types";
import { cn } from "@/lib/utils";

/** Severity is multi-select (chips); the other filters mirror the API's single-value params. */
export interface IssueFilterState {
  severity: Severity[];
  category: Category | "all";
  source: Source | "all";
  status: IssueStatus | "all";
}

export const EMPTY_FILTERS: IssueFilterState = { severity: [], category: "all", source: "all", status: "all" };

export const isFiltered = (f: IssueFilterState) =>
  f.severity.length > 0 || f.category !== "all" || f.source !== "all" || f.status !== "all";

export function applyFilters(issues: Issue[], f: IssueFilterState, except?: keyof IssueFilterState): Issue[] {
  return issues.filter(
    (i) =>
      (except === "severity" || !f.severity.length || f.severity.includes(i.severity)) &&
      (except === "category" || f.category === "all" || i.category === f.category) &&
      (except === "source" || f.source === "all" || i.source === f.source) &&
      (except === "status" || f.status === "all" || i.status === f.status),
  );
}

/** Counts for one facet, given every other active filter (so numbers always add up). */
function facetCounts<K extends "severity" | "category" | "source" | "status">(issues: Issue[], f: IssueFilterState, key: K) {
  const counts = new Map<Issue[K], number>();
  for (const i of applyFilters(issues, f, key)) counts.set(i[key], (counts.get(i[key]) ?? 0) + 1);
  return counts;
}

export function IssueFilters({
  issues,
  value,
  onChange,
}: {
  issues: Issue[];
  value: IssueFilterState;
  onChange: (next: IssueFilterState) => void;
}) {
  const severityCounts = facetCounts(issues, value, "severity");
  const toggleSeverity = (s: Severity) =>
    onChange({
      ...value,
      severity: value.severity.includes(s) ? value.severity.filter((x) => x !== s) : [...value.severity, s],
    });

  return (
    <div className="space-y-2">
      <div role="group" aria-label="Filter by severity" className="flex flex-wrap gap-1.5">
        {SEVERITIES.map((s) => {
          const meta = SEVERITY_META[s];
          const Icon = meta.icon;
          const active = value.severity.includes(s);
          const count = severityCounts.get(s) ?? 0;
          return (
            <button
              key={s}
              type="button"
              aria-pressed={active}
              onClick={() => toggleSeverity(s)}
              className={cn(
                "inline-flex h-7 items-center gap-1 rounded-md border px-2 text-xs font-medium transition-colors focus-visible:ring-2 focus-visible:ring-ring/50 focus-visible:outline-none",
                active ? cn(meta.tint, meta.border, meta.text) : "border-border bg-card text-muted-foreground hover:bg-muted",
              )}
            >
              <Icon className={cn("size-3.5", !active && meta.text)} aria-hidden />
              {meta.label}
              <span className="tabular opacity-80">{count}</span>
            </button>
          );
        })}
      </div>

      <div className="grid grid-cols-3 gap-1.5">
        <FacetSelect
          label="Category"
          allLabel="All categories"
          value={value.category}
          options={CATEGORIES.map((c) => ({ value: c, label: CATEGORY_LABEL[c] }))}
          counts={facetCounts(issues, value, "category")}
          onChange={(category) => onChange({ ...value, category: category as IssueFilterState["category"] })}
        />
        <FacetSelect
          label="Source"
          allLabel="All sources"
          value={value.source}
          options={SOURCES.map((s) => ({ value: s, label: SOURCE_META[s].short }))}
          counts={facetCounts(issues, value, "source")}
          onChange={(source) => onChange({ ...value, source: source as IssueFilterState["source"] })}
        />
        <FacetSelect
          label="Status"
          allLabel="All statuses"
          value={value.status}
          options={ISSUE_STATUSES.map((s) => ({ value: s, label: STATUS_LABEL[s] }))}
          counts={facetCounts(issues, value, "status")}
          onChange={(status) => onChange({ ...value, status: status as IssueFilterState["status"] })}
        />
      </div>
    </div>
  );
}

function FacetSelect({
  label,
  allLabel,
  value,
  options,
  counts,
  onChange,
}: {
  label: string;
  allLabel: string;
  value: string;
  options: { value: string; label: string }[];
  counts: Map<string, number>;
  onChange: (value: string) => void;
}) {
  const total = [...counts.values()].reduce((a, b) => a + b, 0);
  return (
    <Select value={value} onValueChange={onChange}>
      <SelectTrigger size="sm" aria-label={`Filter by ${label.toLowerCase()}`} className={cn("w-full min-w-0 bg-card text-xs", value !== "all" && "border-primary/40 bg-accent text-accent-foreground")}>
        <SelectValue />
      </SelectTrigger>
      <SelectContent position="popper" align="start">
        <SelectItem value="all">
          {allLabel} <span className="ml-auto pl-3 text-xs text-muted-foreground tabular">{total}</span>
        </SelectItem>
        {options.map((o) => (
          <SelectItem key={o.value} value={o.value} disabled={!counts.get(o.value) && value !== o.value}>
            {o.label} <span className="ml-auto pl-3 text-xs text-muted-foreground tabular">{counts.get(o.value) ?? 0}</span>
          </SelectItem>
        ))}
      </SelectContent>
    </Select>
  );
}

export function ClearFilters({ onClear }: { onClear: () => void }) {
  return (
    <button
      type="button"
      onClick={onClear}
      className="inline-flex items-center gap-1 rounded-sm text-xs font-medium text-primary hover:underline"
    >
      <X className="size-3" aria-hidden />
      Clear filters
    </button>
  );
}
