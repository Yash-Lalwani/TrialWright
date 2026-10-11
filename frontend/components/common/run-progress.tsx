import { CircleCheck, CircleMinus, CircleX, Loader2 } from "lucide-react";

import { RUN_STEP_LABEL } from "@/lib/presentation";
import { RUN_STEPS, type StepEvent } from "@/lib/types";
import { cn } from "@/lib/utils";

/**
 * Step list driven by SSE progress events (CONTRACTS.md §4.3). The first step without
 * an event is shown as running. Skipped steps (confidential mode) are labelled.
 */
export function RunProgress({
  events,
  failed,
  className,
  steps = RUN_STEPS,
  labels = RUN_STEP_LABEL,
  ariaLabel = "Review progress",
}: {
  events: Partial<Record<string, StepEvent>>;
  failed?: boolean;
  className?: string;
  /** Defaults to the review pipeline; the draft flow passes its own steps. */
  steps?: readonly string[];
  labels?: Record<string, string>;
  ariaLabel?: string;
}) {
  // Drafts send no pct, so fall back to the share of steps that have reported.
  const reported = Math.max(0, ...Object.values(events).map((e) => e?.pct ?? 0));
  const pct = reported || Math.round((steps.filter((s) => events[s]).length / steps.length) * 100);
  const running = steps.find((s) => !events[s]);

  return (
    <div className={cn("space-y-3", className)}>
      <div
        role="progressbar"
        aria-label={ariaLabel}
        aria-valuemin={0}
        aria-valuemax={100}
        aria-valuenow={pct}
        className="h-1.5 overflow-hidden rounded-full bg-muted"
      >
        <div className="h-full rounded-full bg-primary transition-[width] duration-500 motion-reduce:transition-none" style={{ width: `${pct}%` }} />
      </div>
      <ol className="space-y-1.5" aria-live="polite">
        {steps.map((step) => {
          const e = events[step];
          const isRunning = !failed && step === running;
          const isFailed = failed && step === running;
          const Icon = isFailed
            ? CircleX
            : e?.status === "skipped"
              ? CircleMinus
              : e
                ? CircleCheck
                : isRunning
                  ? Loader2
                  : null;
          return (
            <li key={step} className="flex items-start gap-2 text-sm">
              <span className="mt-0.5 flex size-4 shrink-0 items-center justify-center">
                {Icon ? (
                  <Icon
                    aria-hidden
                    className={cn(
                      "size-4",
                      isFailed && "text-sev-critical",
                      e?.status === "skipped" && "text-muted-foreground",
                      e && e.status !== "skipped" && "text-status-present",
                      isRunning && "animate-spin text-primary motion-reduce:animate-none",
                    )}
                  />
                ) : (
                  <span className="size-2 rounded-full border border-input" aria-hidden />
                )}
              </span>
              <span className={cn("min-w-0 flex-1", !e && !isRunning && "text-muted-foreground")}>
                <span className={cn(isRunning && "font-medium")}>{labels[step]}</span>
                {e && (
                  <span className={cn("ml-2 text-xs", e.status === "skipped" ? "text-muted-foreground italic" : "text-muted-foreground")}>
                    {e.message}
                  </span>
                )}
                <span className="sr-only">
                  {isFailed ? " failed" : e?.status === "skipped" ? " skipped" : e ? " done" : isRunning ? " in progress" : " pending"}
                </span>
              </span>
            </li>
          );
        })}
      </ol>
    </div>
  );
}
