"use client";

import { ArrowUpRight, ChevronDown, FileSearch, MapPin, Wrench } from "lucide-react";
import { useEffect, useRef } from "react";

import { IssueStatusBadge, SeverityBadge, SourceBadge, VerifiedBadge } from "@/components/common/badges";
import { AMENDMENT_LABEL, CATEGORY_LABEL, SEVERITY_COLOR, SEVERITY_META, SOURCE_META } from "@/lib/presentation";
import { SEVERITIES, type Issue, type Severity, type Where } from "@/lib/types";
import { cn } from "@/lib/utils";

/**
 * Accordion list grouped by severity: one row per issue, the selected row expands into the full detail.
 * Arrow keys (or j/k) move the selection; Enter/Space toggles via the row button.
 */
export function IssueList({
  issues,
  selectedId,
  onSelect,
  onLocate,
}: {
  issues: Issue[];
  selectedId: string | null;
  onSelect: (id: string | null) => void;
  onLocate: (where: Where, issueId: string) => void;
}) {
  const listRef = useRef<HTMLDivElement>(null);

  // Keep the selected row in view when selection comes from the PDF or the URL.
  useEffect(() => {
    if (!selectedId) return;
    listRef.current
      ?.querySelector<HTMLElement>(`[data-issue="${selectedId}"]`)
      ?.scrollIntoView({ block: "nearest", behavior: "auto" });
  }, [selectedId]);

  const move = (delta: 1 | -1) => {
    const index = issues.findIndex((i) => i.id === selectedId);
    const next = issues[Math.min(Math.max(index + delta, 0), issues.length - 1)];
    if (!next) return;
    onSelect(next.id);
    listRef.current?.querySelector<HTMLButtonElement>(`[data-issue="${next.id}"] > button`)?.focus();
  };

  // Issues arrive sorted by severity; group them so severity reads as structure.
  const groups = SEVERITIES.map((severity) => ({ severity, items: issues.filter((i) => i.severity === severity) })).filter(
    (g) => g.items.length > 0,
  );

  return (
    <div
      ref={listRef}
      onKeyDown={(e) => {
        if (e.target instanceof HTMLElement && e.target.closest("[data-detail]")) return;
        if (e.key === "ArrowDown" || e.key === "j") {
          e.preventDefault();
          move(1);
        } else if (e.key === "ArrowUp" || e.key === "k") {
          e.preventDefault();
          move(-1);
        }
      }}
    >
      {groups.map(({ severity, items }) => {
        const meta = SEVERITY_META[severity];
        const GroupIcon = meta.icon;
        return (
          <section key={severity} aria-labelledby={`group-${severity}`}>
            <h3
              id={`group-${severity}`}
              className={cn("sticky top-0 z-[2] flex items-center gap-1.5 border-y px-3 py-1.5 text-xs font-semibold", meta.tint, meta.border)}
            >
              <GroupIcon className={cn("size-3.5", meta.text)} aria-hidden />
              <span className={meta.text}>{meta.label}</span>
              <span className={cn("ml-auto rounded-full bg-card px-1.5 text-[11px] leading-4 font-semibold tabular", meta.text)}>{items.length}</span>
            </h3>
            <ul aria-label={`${meta.label} issues`} className="divide-y [&>li.relative]:border-transparent [&>li.relative+li]:border-transparent">
              {items.map((issue) => {
                const selected = issue.id === selectedId;
                const Icon = meta.icon;
                return (
                  <li
                    key={issue.id}
                    data-issue={issue.id}
                    className={cn(
                      "scroll-mt-8",
                      // The selected issue lifts off the list as a card.
                      selected && "relative z-[1] my-1.5 rounded-md bg-card shadow-[0_4px_14px_-4px_rgb(16_24_40/0.18)] ring-1 ring-primary/30 mx-1.5",
                    )}
                  >
                    <button
                      type="button"
                      aria-expanded={selected}
                      aria-controls={`detail-${issue.id}`}
                      onClick={() => onSelect(selected ? null : issue.id)}
                      className={cn(
                        "flex w-full items-start gap-2.5 px-3 py-2.5 text-left transition-colors duration-150 focus-visible:ring-2 focus-visible:ring-ring/60 focus-visible:outline-none focus-visible:ring-inset",
                        selected ? "rounded-t-md bg-accent" : "hover:bg-muted/70",
                      )}
                    >
                      <Icon className={cn("mt-0.5 size-4 shrink-0", meta.text)} aria-label={meta.label} />
                      <span className="min-w-0 flex-1">
                        <span
                          className={cn(
                            "line-clamp-2 text-sm leading-snug",
                            selected ? "font-semibold" : "font-medium",
                            issue.status === "rejected" && "text-muted-foreground",
                          )}
                        >
                          {issue.title}
                        </span>
                        <span className="mt-1 flex flex-wrap items-center gap-x-2 gap-y-0.5 text-xs text-muted-foreground">
                          <span className="font-mono">{issue.id}</span>
                          <span aria-hidden>·</span>
                          <span>{issue.where.page ? `p. ${issue.where.page}` : "No page"}</span>
                          <span aria-hidden>·</span>
                          <span>{issue.source === "rule" ? `Rule ${issue.check_id}` : SOURCE_META[issue.source].short}</span>
                          {issue.status !== "open" && (
                            <>
                              <span aria-hidden>·</span>
                              <IssueStatusBadge status={issue.status} />
                            </>
                          )}
                        </span>
                      </span>
                      <ChevronDown
                        className={cn(
                          "mt-0.5 size-4 shrink-0 text-muted-foreground transition-transform duration-150 motion-reduce:transition-none",
                          selected && "rotate-180 text-foreground",
                        )}
                        aria-hidden
                      />
                    </button>
                    {selected && <IssueDetail issue={issue} onLocate={onLocate} />}
                  </li>
                );
              })}
            </ul>
          </section>
        );
      })}
    </div>
  );
}

function IssueDetail({ issue, onLocate }: { issue: Issue; onLocate: (where: Where, issueId: string) => void }) {
  return (
    <div id={`detail-${issue.id}`} data-detail className="space-y-4 px-3 pt-1 pb-4 pl-[38px] text-sm">
      <div className="flex flex-wrap items-center gap-1.5">
        <SeverityBadge severity={issue.severity} />
        <span className="inline-flex items-center rounded border px-1.5 py-0.5 text-xs leading-4 font-medium text-muted-foreground">
          {CATEGORY_LABEL[issue.category]}
        </span>
        <SourceBadge source={issue.source} checkId={issue.check_id} />
        {issue.verified && <VerifiedBadge />}
        <IssueStatusBadge status={issue.status} />
      </div>

      <Confidence value={issue.confidence} />

      <DetailSection icon={MapPin} title="Where">
        <EvidenceRef where={issue.where} variant="where" severity={issue.severity} onLocate={() => onLocate(issue.where, issue.id)} />
        {issue.related.length > 0 && (
          <div className="mt-3 space-y-2">
            <p className="text-xs font-medium text-muted-foreground">Related evidence</p>
            {issue.related.map((r, i) => (
              <EvidenceRef key={i} where={r} variant="related" severity={issue.severity} onLocate={() => onLocate(r, issue.id)} />
            ))}
          </div>
        )}
      </DetailSection>

      <DetailSection icon={FileSearch} title="Why it matters">
        <p className="leading-relaxed">{issue.why.explanation}</p>
        <dl className="mt-2 grid grid-cols-[auto_1fr] gap-x-3 gap-y-1 text-xs">
          <dt className="text-muted-foreground">Standard</dt>
          <dd>{issue.why.standard_ref ?? "None cited"}</dd>
          <dt className="text-muted-foreground">Amendment risk area</dt>
          <dd>{AMENDMENT_LABEL[issue.why.amendment_category] ?? issue.why.amendment_category}</dd>
        </dl>
      </DetailSection>

      <DetailSection icon={Wrench} title="Suggested fix">
        {issue.fix ? (
          <>
            <p className="leading-relaxed">{issue.fix.suggestion}</p>
            {issue.fix.patch && (
              <details className="mt-2 text-xs">
                <summary className="cursor-pointer text-muted-foreground hover:text-foreground">Structured change</summary>
                <pre className="mt-1 overflow-x-auto rounded-md bg-muted p-2 font-mono text-xs leading-relaxed">
                  {JSON.stringify(issue.fix.patch, null, 2)}
                </pre>
              </details>
            )}
          </>
        ) : (
          <p className="text-muted-foreground">No fix suggested. Review the evidence and decide.</p>
        )}
      </DetailSection>
    </div>
  );
}

function DetailSection({ icon: Icon, title, children }: { icon: typeof MapPin; title: string; children: React.ReactNode }) {
  return (
    <section>
      <h4 className="mb-1.5 flex items-center gap-1.5 text-xs font-semibold text-foreground">
        <Icon className="size-3.5 text-muted-foreground" aria-hidden />
        {title}
      </h4>
      {children}
    </section>
  );
}

/** Swatch that mirrors the PDF highlight style, so the panel and the document read as one key. */
export function EvidenceSwatch({ variant, severity }: { variant: "where" | "related"; severity: Severity }) {
  return (
    <span
      aria-hidden
      style={{ "--sev": SEVERITY_COLOR[severity] } as React.CSSProperties}
      className={cn(
        "inline-block size-3 shrink-0 rounded-[2px]",
        variant === "where" ? "border-[1.5px] border-(--sev) bg-hl-where" : "border-[1.5px] border-dashed border-hl-related-border bg-hl-related",
      )}
    />
  );
}

function EvidenceRef({
  where,
  variant,
  severity,
  onLocate,
}: {
  where: Where;
  variant: "where" | "related";
  severity: Severity;
  onLocate: () => void;
}) {
  return (
    <div className="rounded-md border bg-card">
      <div className="flex items-center justify-between gap-2 border-b px-2.5 py-1.5 text-xs">
        <span className="flex min-w-0 items-center gap-1.5">
          <EvidenceSwatch variant={variant} severity={severity} />
          <span className="truncate font-medium">{where.section ?? "Section not identified"}</span>
        </span>
        {where.page ? (
          <button
            type="button"
            onClick={onLocate}
            className="inline-flex shrink-0 items-center gap-0.5 rounded-sm font-medium text-primary underline-offset-2 hover:underline focus-visible:ring-2 focus-visible:ring-ring/50 focus-visible:outline-none"
          >
            Page {where.page}
            <ArrowUpRight className="size-3" aria-hidden />
          </button>
        ) : (
          <span className="text-muted-foreground">No page</span>
        )}
      </div>
      {where.quote && (
        <blockquote className="px-2.5 py-2 text-[13px] leading-relaxed text-foreground before:content-['\201C'] after:content-['\201D']">
          {where.quote}
        </blockquote>
      )}
    </div>
  );
}

function Confidence({ value }: { value: number }) {
  const pct = Math.round(value * 100);
  return (
    <div className="flex items-center gap-2 text-xs">
      <span className="text-muted-foreground">Confidence</span>
      <span className="h-1.5 w-24 overflow-hidden rounded-full bg-muted" aria-hidden>
        <span className="block h-full rounded-full bg-primary" style={{ width: `${pct}%` }} />
      </span>
      <span className="font-medium tabular">{pct}%</span>
    </div>
  );
}
