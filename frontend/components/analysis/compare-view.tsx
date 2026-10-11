"use client";

import { ArrowRight, GitCompare, TrendingDown, TrendingUp } from "lucide-react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { useMemo } from "react";

import { QueryGate } from "@/components/common/query-gate";
import { EmptyState } from "@/components/common/states";
import { PageHeader } from "@/components/common/page-header";
import { Skeleton } from "@/components/ui/skeleton";
import { formatDateTime, protocolName, SEVERITY_META, SUBSCORE_LABEL } from "@/lib/presentation";
import { useDiff, useProtocolRuns, useProtocols } from "@/lib/queries";
import type { Issue, Run, SubScores } from "@/lib/types";
import { cn } from "@/lib/utils";

const selectClass =
  "h-8 w-full min-w-0 rounded-lg border bg-card px-2.5 text-sm focus-visible:ring-3 focus-visible:ring-ring/50 focus-visible:outline-none";

/** E5: pick two reviews of the same protocol and see what was fixed, what is new and what is still open. */
export function CompareView() {
  const router = useRouter();
  const params = useSearchParams();
  const protocols = useProtocols();

  const items = protocols.data?.items ?? [];
  // Only protocols that have been reviewed can be compared.
  const reviewed = items.filter((p) => p.latest_run && p.latest_run.status === "complete");
  const protocolId = params.get("protocol") ?? reviewed[0]?.protocol_id ?? "";
  const runs = useProtocolRuns(protocolId || undefined);

  const complete = useMemo(
    () => [...(runs.data?.items ?? [])].filter((r) => r.status === "complete").sort((a, b) => a.started_at.localeCompare(b.started_at)),
    [runs.data],
  );
  const toId = params.get("to") ?? complete.at(-1)?.run_id ?? null;
  const fromId = params.get("from") ?? complete.find((r) => r.run_id !== toId)?.run_id ?? null;

  const go = (next: { protocol?: string; from?: string | null; to?: string | null }) => {
    const q = new URLSearchParams();
    q.set("protocol", next.protocol ?? protocolId);
    const from = "from" in next ? next.from : fromId;
    const to = "to" in next ? next.to : toId;
    if (from) q.set("from", from);
    if (to) q.set("to", to);
    router.replace(`/compare?${q}`);
  };

  const diff = useDiff(fromId, toId);
  const label = (r: Run) => `${r.version_label ?? r.run_id} · ${formatDateTime(r.started_at)}`;

  return (
    <div className="mx-auto w-full max-w-6xl space-y-6 px-4 py-6 md:px-6">
      <PageHeader
        title="Compare versions"
        description="Choose two reviews of the same protocol to see what was fixed, what is new and what is still open."
      />

      {protocols.isPending ? (
        <Skeleton className="h-16 w-full" />
      ) : reviewed.length === 0 ? (
        <div className="rounded-lg border bg-card">
          <EmptyState icon={GitCompare} title="Nothing to compare yet">
            Review a protocol, upload a revised version and review it again. Both reviews then appear here.
          </EmptyState>
        </div>
      ) : (
        <div className="grid gap-3 rounded-lg border bg-card p-4 sm:grid-cols-3">
          <label className="text-xs font-medium">
            Protocol
            <select className={cn(selectClass, "mt-1")} value={protocolId} onChange={(e) => go({ protocol: e.target.value, from: null, to: null })}>
              {reviewed.map((p) => (
                <option key={p.protocol_id} value={p.protocol_id}>
                  {protocolName(p, p.protocol_id)}
                </option>
              ))}
            </select>
          </label>
          <label className="text-xs font-medium">
            Earlier review
            <select className={cn(selectClass, "mt-1")} value={fromId ?? ""} onChange={(e) => go({ from: e.target.value })} disabled={complete.length < 2}>
              {complete.map((r) => (
                <option key={r.run_id} value={r.run_id}>
                  {label(r)}
                </option>
              ))}
            </select>
          </label>
          <label className="text-xs font-medium">
            Later review
            <select className={cn(selectClass, "mt-1")} value={toId ?? ""} onChange={(e) => go({ to: e.target.value })} disabled={complete.length < 2}>
              {complete.map((r) => (
                <option key={r.run_id} value={r.run_id}>
                  {label(r)}
                </option>
              ))}
            </select>
          </label>
        </div>
      )}

      {runs.isSuccess && complete.length < 2 && reviewed.length > 0 && (
        <div className="rounded-lg border bg-card">
          <EmptyState icon={GitCompare} title="This protocol has only one review">
            Upload a revised version of the protocol and run a review on it to compare.
          </EmptyState>
        </div>
      )}

      {fromId && toId && fromId === toId && <p className="text-sm text-muted-foreground">Choose two different reviews.</p>}

      {fromId && toId && fromId !== toId && (
        <QueryGate query={diff} skeleton={<Skeleton className="h-72 w-full" />}>
          {(d) => (
            <>
              <ScoreChange from={d.score_from} to={d.score_to} />
              <div className="grid gap-4 lg:grid-cols-3">
                <IssueColumn id="resolved" title="Resolved" hint="In the earlier review, gone in the later one" issues={d.resolved} runId={d.from_run} tone="good" />
                <IssueColumn id="new" title="New" hint="Appeared in the later review" issues={d.new} runId={d.to_run} tone="bad" />
                <IssueColumn id="unchanged" title="Still open" hint="Present in both reviews" issues={d.unchanged} runId={d.to_run} tone="neutral" />
              </div>
            </>
          )}
        </QueryGate>
      )}
    </div>
  );
}

const ROWS = [
  ["overall", "Pre-Flight score"],
  ["completeness", SUBSCORE_LABEL.completeness],
  ["consistency", SUBSCORE_LABEL.consistency],
  ["burden", SUBSCORE_LABEL.burden],
  ["amendment_risk", SUBSCORE_LABEL.amendment_risk],
] as const;

function ScoreChange({ from, to }: { from: SubScores; to: SubScores }) {
  return (
    <section aria-labelledby="score-change" className="rounded-lg border bg-card">
      <h2 id="score-change" className="border-b px-4 py-3 text-sm font-semibold">
        Score change
      </h2>
      <dl className="grid grid-cols-2 gap-px bg-border sm:grid-cols-5" data-score-change>
        {ROWS.map(([key, label]) => {
          const delta = to[key] - from[key];
          const Icon = delta >= 0 ? TrendingUp : TrendingDown;
          return (
            <div key={key} className={cn("bg-card px-4 py-3", key === "overall" && "col-span-2 sm:col-span-1")} data-score-row={key}>
              <dt className="text-xs text-muted-foreground">{label}</dt>
              <dd className="mt-1 flex items-baseline gap-1.5 tabular">
                <span className="text-sm text-muted-foreground">{from[key]}</span>
                <ArrowRight className="size-3 self-center text-muted-foreground" aria-label="to" />
                <span className={cn("font-semibold", key === "overall" ? "text-2xl text-primary" : "text-lg")}>{to[key]}</span>
              </dd>
              <dd className={cn("mt-0.5 flex items-center gap-1 text-xs font-medium tabular", delta > 0 ? "text-status-present" : delta < 0 ? "text-sev-critical" : "text-muted-foreground")}>
                <Icon className="size-3.5" aria-hidden />
                {delta > 0 ? `+${delta}` : delta === 0 ? "No change" : delta}
              </dd>
            </div>
          );
        })}
      </dl>
    </section>
  );
}

function IssueColumn({
  id,
  title,
  hint,
  issues,
  runId,
  tone,
}: {
  id: string;
  title: string;
  hint: string;
  issues: Issue[];
  runId: string;
  tone: "good" | "bad" | "neutral";
}) {
  const sorted = [...issues].sort((a, b) => SEVERITY_META[a.severity].rank - SEVERITY_META[b.severity].rank);
  return (
    <section aria-labelledby={`col-${id}`} data-diff-column={id} className="flex min-h-0 flex-col rounded-lg border bg-card">
      <div className="border-b px-4 py-3">
        <h2 id={`col-${id}`} className="flex items-center gap-2 text-sm font-semibold">
          {title}
          <span
            className={cn(
              "rounded-full px-1.5 text-xs leading-5 tabular",
              tone === "good" && issues.length > 0 && "bg-status-present-bg text-status-present",
              tone === "bad" && issues.length > 0 && "bg-sev-critical-bg text-sev-critical",
              (tone === "neutral" || issues.length === 0) && "bg-muted text-muted-foreground",
            )}
          >
            {issues.length}
          </span>
        </h2>
        <p className="text-xs text-muted-foreground">{hint}</p>
      </div>
      {sorted.length === 0 ? (
        <p className="px-4 py-6 text-center text-sm text-muted-foreground">None</p>
      ) : (
        <ul className="max-h-[32rem] divide-y overflow-y-auto">
          {sorted.map((issue) => {
            const meta = SEVERITY_META[issue.severity];
            return (
              <li key={issue.id}>
                <Link
                  href={`/runs/${runId}?issue=${issue.id}`}
                  className="flex items-start gap-2 px-4 py-2.5 hover:bg-muted/60 focus-visible:ring-2 focus-visible:ring-ring/50 focus-visible:outline-none focus-visible:ring-inset"
                >
                  <meta.icon className={cn("mt-0.5 size-4 shrink-0", meta.text)} aria-label={meta.label} />
                  <span className="min-w-0 text-sm leading-snug">
                    <span className="line-clamp-3">{issue.title}</span>
                    <span className="mt-0.5 block text-xs text-muted-foreground">
                      {issue.where.page ? `p. ${issue.where.page}` : "No page"} · {issue.id}
                    </span>
                  </span>
                </Link>
              </li>
            );
          })}
        </ul>
      )}
    </section>
  );
}
