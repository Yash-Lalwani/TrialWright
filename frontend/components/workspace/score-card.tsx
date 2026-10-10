import { Info } from "lucide-react";

import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { SEVERITY_META, SUBSCORE_LABEL } from "@/lib/presentation";
import { SEVERITIES, type IssueCounts, type Score } from "@/lib/types";

const SUBSCORES = ["completeness", "consistency", "burden", "amendment_risk"] as const;

/** F2: overall Pre-Flight score, four sub-scores, and the weights that combine them. */
export function ScoreCard({ score, counts }: { score: Score; counts: IssueCounts | null }) {
  const formula = SUBSCORES.map((k) => `${score.weights[k].toFixed(2)} × ${SUBSCORE_LABEL[k]}`).join(" + ");

  return (
    <section aria-label="Pre-Flight score" className="flex flex-wrap items-stretch gap-x-6 gap-y-3">
      <div className="flex items-center gap-3 pr-6 lg:border-r">
        <div className="flex items-baseline gap-1">
          <span className="text-3xl leading-none font-semibold tracking-tight tabular">{score.overall}</span>
          <span className="text-sm text-muted-foreground">/100</span>
        </div>
        <div className="flex flex-col">
          <span className="flex items-center gap-1 text-xs font-medium text-muted-foreground">
            Pre-Flight score
            <Tooltip>
              <TooltipTrigger asChild>
                <button type="button" aria-label="How the score is calculated" className="rounded-sm text-muted-foreground hover:text-foreground">
                  <Info className="size-3.5" aria-hidden />
                </button>
              </TooltipTrigger>
              <TooltipContent side="bottom" className="max-w-80 text-xs leading-relaxed">
                <p className="font-medium">Overall = {formula}</p>
                <p className="mt-1 opacity-80">
                  Weights come from config/score.yaml. Accepting a fix removes that issue&apos;s points.
                </p>
              </TooltipContent>
            </Tooltip>
          </span>
          {counts && (
            <span className="mt-1 flex items-center gap-2 text-xs">
              {SEVERITIES.map((s) => {
                const meta = SEVERITY_META[s];
                const Icon = meta.icon;
                return (
                  <span key={s} className={`inline-flex items-center gap-0.5 ${meta.text}`} title={`${counts[s]} ${meta.label}`}>
                    <Icon className="size-3.5" aria-hidden />
                    <span className="tabular">{counts[s]}</span>
                    <span className="sr-only">{meta.label}</span>
                  </span>
                );
              })}
            </span>
          )}
        </div>
      </div>

      <dl className="grid min-w-0 flex-1 basis-full grid-cols-2 gap-x-6 gap-y-2 sm:basis-0 sm:grid-cols-4">
        {SUBSCORES.map((k) => (
          <div key={k} className="min-w-0">
            <dt className="flex items-baseline justify-between gap-2 text-xs text-muted-foreground">
              <span>{SUBSCORE_LABEL[k]}</span>
              <span className="tabular">×{score.weights[k].toFixed(2)}</span>
            </dt>
            <dd className="mt-1 flex items-center gap-2">
              <span className="w-7 text-sm font-semibold tabular">{score[k]}</span>
              <span className="h-1.5 flex-1 overflow-hidden rounded-full bg-muted" aria-hidden>
                <span className="block h-full rounded-full bg-primary" style={{ width: `${score[k]}%` }} />
              </span>
            </dd>
          </div>
        ))}
      </dl>
    </section>
  );
}
