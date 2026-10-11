"use client";

import { ErrorState } from "@/components/common/states";
import { Skeleton } from "@/components/ui/skeleton";
import { formatDateTime, formatDuration, formatUsd, RUN_STEP_LABEL } from "@/lib/presentation";
import { useTrace } from "@/lib/queries";
import type { Run, RunStep } from "@/lib/types";
import { cn } from "@/lib/utils";

import { Section, Stat, StatGrid, Table, td } from "./primitives";

/** Audit & trace (CONTRACTS 4.7): pipeline steps, every LLM call, the verifier and the decision log. */
export function TraceView({ run }: { run: Run }) {
  const trace = useTrace(run.run_id);
  if (trace.isPending) return <Skeleton className="h-96 w-full" aria-label="Loading trace" />;
  if (trace.isError) return <ErrorState error={trace.error} onRetry={() => void trace.refetch()} />;
  const { steps, llm_calls: calls, verifier, audit } = trace.data;
  const tokens = calls.reduce((n, c) => n + c.tokens_in + c.tokens_out, 0);
  const cost = calls.reduce((n, c) => n + c.cost_usd, 0);
  const hits = calls.filter((c) => c.cache_hit).length;

  return (
    <>
      <Section title="Run summary">
        <StatGrid>
          <Stat label="Duration" value={formatDuration(run.duration_s)} />
          <Stat label="LLM calls" value={calls.length} hint={calls.length ? `${hits} from the replay cache` : undefined} />
          <Stat label="Tokens" value={tokens.toLocaleString("en-US")} />
          <Stat label="LLM cost" value={formatUsd(cost)} />
          <Stat label="AI findings" value={verifier.ai_findings} />
          <Stat label="Dropped as ungrounded" value={verifier.dropped_ungrounded} hint={`${verifier.shown} shown`} />
        </StatGrid>
        <p className="mt-4 text-xs text-muted-foreground">
          Every AI finding must quote text that is found on the page it cites. Findings whose quote is not on the page, or that
          reuse one quote for several claims, are dropped before you see them.
        </p>
      </Section>

      <Section title="Pipeline steps">
        <Table head={["Step", "Status", "Started", "Duration"]}>
          {steps.map((s, i) => (
            <tr key={`${s.step}-${i}`}>
              <td className={td}>{RUN_STEP_LABEL[s.step as RunStep] ?? s.step}</td>
              <td className={td}>
                <span className={cn("text-xs font-medium", s.status === "done" ? "text-status-present" : "text-muted-foreground")}>
                  {s.status}
                </span>
              </td>
              <td className={`${td} tabular text-xs`}>{formatDateTime(s.started_at)}</td>
              <td className={`${td} tabular`}>{formatDuration(s.duration_s)}</td>
            </tr>
          ))}
        </Table>
      </Section>

      <Section title="LLM calls" description="One row per model call. Replayed calls are served from the committed cache at no cost.">
        {calls.length ? (
          <Table head={["Step", "Model", "Tokens in", "Tokens out", "Latency", "Cost", "Source"]}>
            {calls.map((c, i) => (
              <tr key={i}>
                <td className={`${td} font-mono text-xs`}>{c.step}</td>
                <td className={`${td} text-xs`}>{c.model}</td>
                <td className={`${td} tabular`}>{c.tokens_in.toLocaleString("en-US")}</td>
                <td className={`${td} tabular`}>{c.tokens_out.toLocaleString("en-US")}</td>
                <td className={`${td} tabular`}>{c.latency_s.toFixed(1)} s</td>
                <td className={`${td} tabular`}>{formatUsd(c.cost_usd)}</td>
                <td className={`${td} text-xs`}>{c.cache_hit ? "cache" : "live"}</td>
              </tr>
            ))}
          </Table>
        ) : (
          <p className="text-sm text-muted-foreground">No language model was called (confidential rules-only review).</p>
        )}
      </Section>

      <Section title="Decision audit trail" description="Every accept or reject on an issue, with who and why.">
        {audit.length ? (
          <Table head={["When", "Issue", "Decision", "User", "Note"]}>
            {audit.map((a) => (
              <tr key={a.audit_id}>
                <td className={`${td} tabular text-xs whitespace-nowrap`}>{formatDateTime(a.at)}</td>
                <td className={`${td} font-mono text-xs`}>{a.issue_id}</td>
                <td className={`${td} capitalize`}>{a.decision}</td>
                <td className={td}>{a.user ?? "-"}</td>
                <td className={td}>{a.note ?? ""}</td>
              </tr>
            ))}
          </Table>
        ) : (
          <p className="text-sm text-muted-foreground">No decisions recorded yet. Accept or reject issues in the review.</p>
        )}
      </Section>
    </>
  );
}
