import { Info } from "lucide-react";

import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { SUBSCORE_LABEL } from "@/lib/presentation";
import type { Score } from "@/lib/types";
import { cn } from "@/lib/utils";

const SUBSCORES = ["completeness", "consistency", "burden", "amendment_risk"] as const;

/**
 * F2: overall Pre-Flight score and the four weighted sub-scores, drawn as meters on
 * the same 0–100 scale (quarter ticks) so they compare at a glance.
 */
export function ScoreCard({ score }: { score: Score }) {
  const formula = SUBSCORES.map((k) => `${score.weights[k].toFixed(2)} × ${SUBSCORE_LABEL[k]}`).join(" + ");

  return (
    <section aria-label="Pre-Flight score" className="flex flex-wrap items-stretch gap-x-5 gap-y-3">
      <div className="w-36 shrink-0">
        <div className="flex items-center gap-1 text-xs font-medium text-muted-foreground">
          Pre-Flight score
          <Tooltip>
            <TooltipTrigger asChild>
              <button
                type="button"
                aria-label="How the score is calculated"
                className="-m-1 rounded-sm p-1 text-muted-foreground transition-colors hover:text-foreground focus-visible:ring-2 focus-visible:ring-ring/50 focus-visible:outline-none"
              >
                <Info className="size-3.5" aria-hidden />
              </button>
            </TooltipTrigger>
            <TooltipContent side="bottom" className="max-w-80 text-xs leading-relaxed">
              <p className="font-medium">Overall = {formula}</p>
              <p className="mt-1 opacity-80">Weights come from config/score.yaml. Accepting a fix removes that issue&apos;s points.</p>
            </TooltipContent>
          </Tooltip>
        </div>
        <div className="mt-0.5 flex items-baseline gap-1">
          <span className="text-2xl leading-8 font-semibold tracking-tight tabular">{score.overall}</span>
          <span className="text-xs text-muted-foreground">/ 100</span>
        </div>
        <Meter value={score.overall} strong />
      </div>

      <div className="hidden w-px self-stretch bg-border sm:block" aria-hidden />

      <dl className="grid min-w-0 flex-1 basis-full grid-cols-2 gap-x-4 gap-y-3 sm:basis-0 sm:grid-cols-4 2xl:gap-x-5">
        {SUBSCORES.map((k) => (
          <div key={k} className="min-w-0 sm:w-28 2xl:w-36">
            <dt className="truncate text-xs text-muted-foreground">{SUBSCORE_LABEL[k]}</dt>
            <dd>
              <span className="flex items-baseline justify-between gap-2">
                <span className="text-base leading-7 font-semibold tabular">{score[k]}</span>
                <span className="text-xs text-muted-foreground tabular" title={`Weight in the overall score: ${score.weights[k]}`}>
                  ×{score.weights[k].toFixed(2)}
                </span>
              </span>
              <Meter value={score[k]} />
            </dd>
          </div>
        ))}
      </dl>
    </section>
  );
}

/** Horizontal meter on a fixed 0–100 scale with ticks at 25/50/75. Decorative: the number is shown beside it. */
function Meter({ value, strong }: { value: number; strong?: boolean }) {
  return (
    <span className={cn("relative mt-1 block overflow-hidden rounded-full bg-track", strong ? "h-2" : "h-1.5")} aria-hidden>
      <span className="absolute inset-y-0 left-0 rounded-full bg-primary" style={{ width: `${Math.max(0, Math.min(100, value))}%` }} />
      {[25, 50, 75].map((t) => (
        <span key={t} className="absolute inset-y-0 w-px bg-card" style={{ left: `${t}%` }} />
      ))}
    </span>
  );
}
