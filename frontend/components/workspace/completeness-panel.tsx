"use client";

import { ListChecks } from "lucide-react";
import { useState } from "react";

import { CompletenessBadge } from "@/components/common/badges";
import { EmptyState, ErrorState } from "@/components/common/states";
import { Skeleton } from "@/components/ui/skeleton";
import { useCompleteness } from "@/lib/queries";
import type { CompletenessItem, CompletenessStatus } from "@/lib/types";
import { cn } from "@/lib/utils";

const FRAMEWORKS = ["all", "M11", "SPIRIT"] as const;
type Framework = (typeof FRAMEWORKS)[number];
const FRAMEWORK_LABEL: Record<Framework, string> = { all: "All", M11: "ICH M11", SPIRIT: "SPIRIT 2025" };
const STATUS_ORDER: CompletenessStatus[] = ["missing", "thin", "present"];

/** B1–B3: M11 and SPIRIT checklist (CONTRACTS.md §4.5). Page numbers jump the PDF. */
export function CompletenessPanel({ runId, onGoToPage }: { runId: string; onGoToPage: (page: number) => void }) {
  const { data, isPending, isError, error, refetch } = useCompleteness(runId);
  const [framework, setFramework] = useState<Framework>("all");
  const [status, setStatus] = useState<CompletenessStatus | "all">("all");

  if (isPending) {
    return (
      <div className="space-y-2 p-3" aria-busy="true" aria-label="Loading completeness">
        {Array.from({ length: 6 }, (_, i) => (
          <Skeleton key={i} className="h-9 w-full" />
        ))}
      </div>
    );
  }
  if (isError) return <ErrorState className="m-3" error={error} onRetry={() => void refetch()} />;

  const { summary } = data;
  const items = data.items
    .filter((i) => (framework === "all" || i.framework === framework) && (status === "all" || i.status === status))
    .sort((a, b) => STATUS_ORDER.indexOf(a.status) - STATUS_ORDER.indexOf(b.status));

  return (
    <div className="flex flex-col">
      <div className="sticky top-0 z-10 space-y-3 border-b bg-card p-3">
        <div className="flex items-baseline justify-between text-xs text-muted-foreground">
          <span>
            <span className="text-sm font-semibold text-foreground tabular">{summary.present}</span> of{" "}
            <span className="tabular">{summary.required}</span> required items present
          </span>
        </div>
        <div className="flex h-2 overflow-hidden rounded-full bg-muted" aria-hidden>
          {(["present", "thin", "missing"] as const).map((s) => (
            <span
              key={s}
              className={cn(s === "present" ? "bg-status-present" : s === "thin" ? "bg-status-thin" : "bg-status-missing")}
              style={{ width: `${summary.required ? (summary[s] / summary.required) * 100 : 0}%` }}
            />
          ))}
        </div>
        <div role="group" aria-label="Filter by status" className="flex flex-wrap gap-1.5">
          {(["all", ...STATUS_ORDER] as const).map((s) => (
            <button
              key={s}
              type="button"
              aria-pressed={status === s}
              onClick={() => setStatus(s)}
              className={cn(
                "inline-flex h-7 items-center gap-1.5 rounded-md border px-2 text-xs font-medium focus-visible:ring-2 focus-visible:ring-ring/50 focus-visible:outline-none",
                status === s ? "border-primary/40 bg-accent text-accent-foreground" : "bg-card text-muted-foreground hover:bg-muted",
              )}
            >
              {s === "all" ? "All" : <CompletenessBadge status={s} />}
              <span className="tabular">{s === "all" ? summary.required : summary[s]}</span>
            </button>
          ))}
        </div>
        <div role="group" aria-label="Framework" className="inline-flex rounded-md border bg-muted p-0.5">
          {FRAMEWORKS.map((f) => (
            <button
              key={f}
              type="button"
              aria-pressed={framework === f}
              onClick={() => setFramework(f)}
              className={cn(
                "rounded px-2.5 py-1 text-xs font-medium focus-visible:ring-2 focus-visible:ring-ring/50 focus-visible:outline-none",
                framework === f ? "bg-card text-foreground shadow-sm" : "text-muted-foreground hover:text-foreground",
              )}
            >
              {FRAMEWORK_LABEL[f]}
            </button>
          ))}
        </div>
      </div>

      {items.length === 0 ? (
        <EmptyState icon={ListChecks} title="No items match these filters" />
      ) : (
        <ul className="divide-y">
          {items.map((item) => (
            <ChecklistRow key={`${item.framework}-${item.item_id}`} item={item} onGoToPage={onGoToPage} />
          ))}
        </ul>
      )}
    </div>
  );
}

function ChecklistRow({ item, onGoToPage }: { item: CompletenessItem; onGoToPage: (page: number) => void }) {
  return (
    <li className="flex items-start gap-3 px-3 py-2.5">
      <span className="w-14 shrink-0 pt-0.5 font-mono text-xs text-muted-foreground">
        {item.framework === "M11" ? "M11" : "SPIRIT"} {item.item_id}
      </span>
      <div className="min-w-0 flex-1">
        <div className="flex items-start justify-between gap-2">
          <span className="text-sm font-medium">{item.title}</span>
          <CompletenessBadge status={item.status} />
        </div>
        {item.note && <p className="mt-0.5 text-xs leading-relaxed text-muted-foreground">{item.note}</p>}
        <div className="mt-1 flex flex-wrap items-center gap-1 text-xs">
          {item.pages.length ? (
            item.pages.map((p) => (
              <button
                key={p}
                type="button"
                onClick={() => onGoToPage(p)}
                aria-label={`Go to page ${p}`}
                className="rounded border bg-card px-1.5 py-0.5 font-medium text-primary tabular hover:bg-accent focus-visible:ring-2 focus-visible:ring-ring/50 focus-visible:outline-none"
              >
                p. {p}
              </button>
            ))
          ) : (
            <span className="text-muted-foreground">Not found in the document</span>
          )}
        </div>
      </div>
    </li>
  );
}
