"use client";

import { ArrowRight, GitCompare } from "lucide-react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";

import { SeverityBadge } from "@/components/common/badges";
import { EmptyState, ErrorState } from "@/components/common/states";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";
import { formatDateTime, protocolName, SUBSCORE_LABEL } from "@/lib/presentation";
import { useDiff, useProtocolRuns, useProtocols } from "@/lib/queries";
import type { Issue, ProtocolListItem, Run, RunDiff } from "@/lib/types";
import { cn } from "@/lib/utils";

import { Section } from "./primitives";

const select =
  "h-9 w-full rounded-md border bg-card px-2 text-sm focus-visible:ring-2 focus-visible:ring-ring/50 focus-visible:outline-none";

/**
 * E5 version diff (CONTRACTS 4.6). Each side picks a protocol and one of its reviews: a revised PDF is a new
 * upload (ids come from the file content), so the two versions are usually two protocol entries.
 */
export function CompareView() {
  const router = useRouter();
  const params = useSearchParams();
  const toProtocol = params.get("protocol");
  const fromProtocol = params.get("fromProtocol") ?? toProtocol;
  const from = params.get("from");
  const to = params.get("to");
  const protocols = useProtocols();

  const set = (patch: Record<string, string | null>) => {
    const next = new URLSearchParams(params);
    for (const [k, v] of Object.entries(patch)) if (v) next.set(k, v); else next.delete(k);
    router.replace(`/compare?${next}`);
  };

  return (
    <div className="space-y-5">
      <Section title="Choose two reviews" description="Upload the revised version of a protocol, review it, then compare it with the review of the earlier version.">
        <div className="grid gap-6 md:grid-cols-2">
          <Side label="Earlier version" protocols={protocols.data?.items ?? []} protocolId={fromProtocol} runId={from}
            onProtocol={(v) => set({ fromProtocol: v, from: null })} onRun={(v) => set({ from: v })} />
          <Side label="Later version" protocols={protocols.data?.items ?? []} protocolId={toProtocol} runId={to}
            onProtocol={(v) => set({ protocol: v, to: null })} onRun={(v) => set({ to: v })} />
        </div>
      </Section>
      {from && to && from !== to ? <DiffResult from={from} to={to} /> : (
        <div className="rounded-lg border bg-card">
          <EmptyState icon={GitCompare} title="Pick two different reviews to compare" />
        </div>
      )}
    </div>
  );
}

function Side({ label, protocols, protocolId, runId, onProtocol, onRun }: {
  label: string; protocols: ProtocolListItem[]; protocolId: string | null; runId: string | null;
  onProtocol: (v: string) => void; onRun: (v: string) => void;
}) {
  const runs = useProtocolRuns(protocolId);
  const complete = (runs.data?.items ?? []).filter((r) => r.status === "complete");
  const id = label.toLowerCase().replace(/\s+/g, "-");
  return (
    <fieldset className="space-y-3">
      <legend className="text-sm font-medium">{label}</legend>
      <div className="space-y-1.5">
        <Label htmlFor={`${id}-protocol`}>Protocol</Label>
        <select id={`${id}-protocol`} className={select} value={protocolId ?? ""} onChange={(e) => onProtocol(e.target.value)}>
          <option value="">Select a protocol</option>
          {protocols.map((p) => (
            <option key={p.protocol_id} value={p.protocol_id}>
              {[p.nct_id, p.filename, protocolName(p, p.protocol_id).slice(0, 60)].filter(Boolean).join(" · ")}
            </option>
          ))}
        </select>
      </div>
      <RunSelect id={`${id}-run`} label="Review" runs={complete} value={runId} onChange={onRun} />
    </fieldset>
  );
}

function RunSelect({ id, label, runs, value, onChange }: {
  id: string; label: string; runs: Run[]; value: string | null; onChange: (v: string) => void;
}) {
  return (
    <div className="space-y-1.5">
      <Label htmlFor={id}>{label}</Label>
      <select id={id} className={select} value={value ?? ""} onChange={(e) => onChange(e.target.value)} disabled={!runs.length}>
        <option value="">{runs.length ? "Select a review" : "No completed reviews"}</option>
        {runs.map((r) => (
          <option key={r.run_id} value={r.run_id}>
            {[r.version_label, r.score ? `score ${r.score.overall}` : null, r.finished_at ? formatDateTime(r.finished_at) : null]
              .filter(Boolean).join(" · ") || r.run_id}
          </option>
        ))}
      </select>
    </div>
  );
}

function DiffResult({ from, to }: { from: string; to: string }) {
  const diff = useDiff(from, to);
  if (diff.isPending) return <Skeleton className="h-80 w-full" />;
  if (diff.isError) return <ErrorState error={diff.error} onRetry={() => void diff.refetch()} />;
  return <DiffBody diff={diff.data} />;
}

function DiffBody({ diff }: { diff: RunDiff }) {
  const keys = ["overall", "completeness", "consistency", "burden", "amendment_risk"] as const;
  return (
    <>
      <Section title="Score change">
        <dl className="grid grid-cols-2 gap-4 sm:grid-cols-5">
          {keys.map((k) => {
            const a = diff.score_from[k];
            const b = diff.score_to[k];
            const d = b - a;
            return (
              <div key={k}>
                <dt className="text-xs text-muted-foreground">{k === "overall" ? "Pre-Flight score" : SUBSCORE_LABEL[k]}</dt>
                <dd className="mt-0.5 flex items-baseline gap-1.5 tabular">
                  <span className="text-sm text-muted-foreground">{a}</span>
                  <ArrowRight className="size-3 self-center text-muted-foreground" aria-hidden />
                  <span className="text-lg font-semibold">{b}</span>
                  <span className={cn("text-xs font-medium", d > 0 ? "text-status-present" : d < 0 ? "text-sev-critical" : "text-muted-foreground")}>
                    {d > 0 ? `+${d}` : d}
                  </span>
                </dd>
              </div>
            );
          })}
        </dl>
      </Section>
      <div className="grid gap-5 lg:grid-cols-3">
        <IssueColumn title="Resolved" issues={diff.resolved} runId={diff.from_run} tone="text-status-present" />
        <IssueColumn title="New" issues={diff.new} runId={diff.to_run} tone="text-sev-critical" />
        <IssueColumn title="Unchanged" issues={diff.unchanged} runId={diff.to_run} tone="text-muted-foreground" />
      </div>
    </>
  );
}

function IssueColumn({ title, issues, runId, tone }: { title: string; issues: Issue[]; runId: string; tone: string }) {
  return (
    <Section title={`${title} (${issues.length})`} className="min-w-0">
      {issues.length ? (
        <ul className="-my-1 max-h-[32rem] divide-y overflow-y-auto">
          {issues.map((i) => (
            <li key={i.id} className="py-2">
              <div className="flex items-start justify-between gap-2">
                <Link href={`/runs/${runId}?issue=${i.id}`} className={cn("text-sm hover:underline", tone === "text-muted-foreground" ? "" : "font-medium")}>
                  {i.title}
                </Link>
                <SeverityBadge severity={i.severity} />
              </div>
              <p className="mt-0.5 text-xs text-muted-foreground">
                {i.check_id} · {i.where.section ?? "No section"}{i.where.page ? ` · p. ${i.where.page}` : ""}
              </p>
            </li>
          ))}
        </ul>
      ) : (
        <p className={cn("text-sm", tone)}>None</p>
      )}
    </Section>
  );
}
