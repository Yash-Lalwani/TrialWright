import { CircleCheck, CircleMinus, CircleX, Loader2 } from "lucide-react";

import { RUN_STEP_LABEL } from "@/lib/presentation";
import { RUN_STEPS, type ProgressEvent, type RunStep } from "@/lib/types";
import { cn } from "@/lib/utils";

/**
 * Step list driven by SSE progress events (CONTRACTS.md §4.3). The first step without
 * an event is shown as running. Skipped steps (confidential mode) are labelled.
 */
export function RunProgress({
  events,
  failed,
  className,
}: {
  events: Partial<Record<RunStep, ProgressEvent>>;
  failed?: boolean;
  className?: string;
}) {
  const pct = Math.max(0, ...Object.values(events).map((e) => e?.pct ?? 0));
  const running = RUN_STEPS.find((s) => !events[s]);

  return (
    <div className={cn("space-y-3", className)}>
      <div
        role="progressbar"
        aria-label="Review progress"
        aria-valuemin={0}
        aria-valuemax={100}
        aria-valuenow={pct}
        className="h-1.5 overflow-hidden rounded-full bg-muted"
      >
        <div className="h-full rounded-full bg-primary transition-[width] duration-500 motion-reduce:transition-none" style={{ width: `${pct}%` }} />
      </div>
      <ol className="space-y-1.5" aria-live="polite">
        {RUN_STEPS.map((step) => {
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
                <span className={cn(isRunning && "font-medium")}>{RUN_STEP_LABEL[step]}</span>
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
