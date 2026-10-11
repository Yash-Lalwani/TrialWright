import { BadgeCheck, CircleCheck, CircleDashed, CircleX } from "lucide-react";

import { COMPLETENESS_META, SEVERITY_META, SOURCE_META, STATUS_LABEL } from "@/lib/presentation";
import type { CompletenessStatus, IssueStatus, Severity, Source } from "@/lib/types";
import { cn } from "@/lib/utils";

const chip = "inline-flex shrink-0 items-center gap-1 rounded border px-1.5 py-0.5 text-xs font-medium leading-4 whitespace-nowrap";

export function SeverityBadge({ severity, className }: { severity: Severity; className?: string }) {
  const meta = SEVERITY_META[severity];
  const Icon = meta.icon;
  return (
    <span className={cn(chip, meta.text, meta.tint, meta.border, className)}>
      <Icon className="size-3.5" aria-hidden />
      {meta.label}
    </span>
  );
}

export function SourceBadge({ source, checkId }: { source: Source; checkId?: string }) {
  const meta = SOURCE_META[source];
  const Icon = meta.icon;
  return (
    <span className={cn(chip, "border-border bg-card text-muted-foreground")} title={meta.label}>
      <Icon className="size-3.5" aria-hidden />
      {source === "rule" ? `Rule${checkId ? ` ${checkId}` : ""}` : `AI · ${meta.short}`}
    </span>
  );
}

export function VerifiedBadge() {
  return (
    <span
      className={cn(chip, "border-status-present/30 bg-status-present-bg text-status-present")}
      title="Quoted evidence was found on the cited page"
    >
      <BadgeCheck className="size-3.5" aria-hidden />
      Verified
    </span>
  );
}

const STATUS_STYLE: Record<IssueStatus, string> = {
  open: "border-border bg-card text-muted-foreground",
  accepted: "border-status-present/30 bg-status-present-bg text-status-present",
  rejected: "border-border bg-muted text-muted-foreground line-through decoration-1",
};

export function IssueStatusBadge({ status }: { status: IssueStatus }) {
  return <span className={cn(chip, STATUS_STYLE[status])}>{STATUS_LABEL[status]}</span>;
}

const COMPLETENESS_ICON = { present: CircleCheck, thin: CircleDashed, missing: CircleX };

export function CompletenessBadge({ status }: { status: CompletenessStatus }) {
  const meta = COMPLETENESS_META[status];
  const Icon = COMPLETENESS_ICON[status];
  return (
    <span className={cn(chip, "border-transparent", meta.text, meta.tint)}>
      <Icon className="size-3.5" aria-hidden />
      {meta.label}
    </span>
  );
}
