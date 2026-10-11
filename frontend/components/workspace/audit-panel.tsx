"use client";

import { Bot, Check, ShieldCheck, X } from "lucide-react";

import { ErrorState } from "@/components/common/states";
import { Skeleton } from "@/components/ui/skeleton";
import { formatDateTime, formatDuration, formatUsd, RUN_STEP_LABEL } from "@/lib/presentation";
import { useTrace } from "@/lib/queries";

/** Audit tab (4.7 trace): human decisions, the verifier's work, pipeline steps and every model call. */
export function AuditPanel({ runId, onSelectIssue }: { runId: string; onSelectIssue: (id: string) => void }) {
  const trace = useTrace(runId);

  if (trace.isPending) {
    return (
      <div className="space-y-2 p-3" aria-busy="true" aria-label="Loading audit trail">
        {Array.from({ length: 5 }, (_, i) => (
          <Skeleton key={i} className="h-10 w-full" />
        ))}
      </div>
    );
  }
  if (trace.isError) return <ErrorState className="m-3" error={trace.error} onRetry={() => void trace.refetch()} />;

  const { audit, verifier, steps, llm_calls: calls } = trace.data;
  const totalCost = calls.reduce((sum, c) => sum + c.cost_usd, 0);
  const hits = calls.filter((c) => c.cache_hit).length;

  return (
    <div className="divide-y text-sm">
      <Section title="Decisions" count={audit.length}>
        {audit.length === 0 ? (
          <p className="px-3 pb-3 text-muted-foreground">No decisions yet. Accept or reject an issue and it is recorded here.</p>
        ) : (
          <ol className="divide-y border-t" data-audit-list>
            {[...audit].reverse().map((a) => (
              <li key={a.audit_id} className="px-3 py-2">
                <div className="flex items-center gap-2">
                  {a.decision === "accepted" ? (
                    <Check className="size-4 text-status-present" aria-label="Accepted" />
                  ) : (
                    <X className="size-4 text-muted-foreground" aria-label="Rejected" />
                  )}
                  <button
                    type="button"
                    onClick={() => onSelectIssue(a.issue_id)}
                    className="rounded-sm font-mono text-xs font-medium text-primary underline-offset-2 hover:underline focus-visible:ring-2 focus-visible:ring-ring/50 focus-visible:outline-none"
                  >
                    {a.issue_id}
                  </button>
                  <span className="text-xs text-muted-foreground">
                    {a.decision} by {a.user}
                  </span>
                  <time dateTime={a.at} className="ml-auto text-xs text-muted-foreground tabular">
                    {formatDateTime(a.at)}
                  </time>
                </div>
                {a.note && <p className="mt-1 pl-6 leading-snug">{a.note}</p>}
              </li>
            ))}
          </ol>
        )}
      </Section>

      <Section title="Grounding check" count={null}>
        <div className="flex items-start gap-2 px-3 pb-3">
          <ShieldCheck className="mt-0.5 size-4 shrink-0 text-status-present" aria-hidden />
          <p className="leading-relaxed">
            AI reviewers proposed <b className="tabular">{verifier.ai_findings}</b> findings. The verifier dropped{" "}
            <b className="tabular">{verifier.dropped_ungrounded}</b> whose quotes were not found in the protocol, leaving{" "}
            <b className="tabular">{verifier.shown}</b> shown.
          </p>
        </div>
      </Section>

      <Section title="Pipeline" count={steps.length}>
        <ul className="border-t">
          {steps.map((s) => (
            <li key={s.step} className="flex items-center gap-2 px-3 py-1.5 text-xs">
              <span className="flex-1">{RUN_STEP_LABEL[s.step]}</span>
              <span className="text-muted-foreground capitalize">{s.status}</span>
              <span className="w-14 text-right tabular text-muted-foreground">{formatDuration(s.duration_s)}</span>
            </li>
          ))}
        </ul>
      </Section>

      <Section title="Model calls" count={calls.length}>
        {calls.length === 0 ? (
          <p className="px-3 pb-3 text-muted-foreground">No model calls. This review used rules only.</p>
        ) : (
          <>
            <p className="flex items-center gap-1.5 px-3 pb-2 text-xs text-muted-foreground">
              <Bot className="size-3.5" aria-hidden />
              Total {formatUsd(totalCost)} · {hits} cached
            </p>
            <div className="overflow-x-auto border-t">
              <table className="w-full text-xs">
                <thead className="text-left text-muted-foreground">
                  <tr>
                    <th className="px-3 py-1.5 font-medium">Step</th>
                    <th className="px-2 py-1.5 font-medium">Model</th>
                    <th className="px-2 py-1.5 text-right font-medium">Tokens in/out</th>
                    <th className="px-2 py-1.5 text-right font-medium">Latency</th>
                    <th className="px-3 py-1.5 text-right font-medium">Cost</th>
                  </tr>
                </thead>
                <tbody className="divide-y">
                  {calls.map((c, i) => (
                    <tr key={i}>
                      <td className="px-3 py-1.5">
                        {c.step}
                        {c.cache_hit && <span className="ml-1 text-muted-foreground">(cached)</span>}
                      </td>
                      <td className="max-w-32 truncate px-2 py-1.5 font-mono" title={c.model}>
                        {c.model}
                      </td>
                      <td className="px-2 py-1.5 text-right tabular">
                        {c.tokens_in.toLocaleString("en-US")} / {c.tokens_out.toLocaleString("en-US")}
                      </td>
                      <td className="px-2 py-1.5 text-right tabular">{c.latency_s.toFixed(1)} s</td>
                      <td className="px-3 py-1.5 text-right tabular">${c.cost_usd.toFixed(4)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </>
        )}
      </Section>
    </div>
  );
}

function Section({ title, count, children }: { title: string; count: number | null; children: React.ReactNode }) {
  return (
    <section>
      <h3 className="flex items-center gap-2 px-3 py-2 text-xs font-semibold">
        {title}
        {count != null && <span className="rounded-full bg-muted px-1.5 text-[11px] leading-4 tabular text-muted-foreground">{count}</span>}
      </h3>
      {children}
    </section>
  );
}
