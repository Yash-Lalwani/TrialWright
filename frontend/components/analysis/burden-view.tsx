"use client";

import { Clock, Hospital, Layers, Syringe, Users, Wallet } from "lucide-react";
import Link from "next/link";

import { QueryGate } from "@/components/common/query-gate";
import { Skeleton } from "@/components/ui/skeleton";
import { formatPhase, formatUsd, protocolName, SEVERITY_META } from "@/lib/presentation";
import { useBurden, useIssues, usePeers, usePrecedent, useProtocols, useRun } from "@/lib/queries";
import type { Burden, Issue, Peers, Precedent } from "@/lib/types";
import { cn } from "@/lib/utils";

import { Histogram, PercentileBar } from "./charts";
import { RunPageHeader } from "./run-subnav";

const nf = new Intl.NumberFormat("en-US");
const NOT_STATED = <span className="font-normal text-muted-foreground">Not stated</span>;
const num = (n: number | null | undefined) => (n == null ? "-" : nf.format(n));

export function BurdenView({ runId }: { runId: string }) {
  const run = useRun(runId);
  const protocols = useProtocols();
  const protocol = protocols.data?.items.find((p) => p.protocol_id === run.data?.protocol_id);
  const burden = useBurden(runId);
  const peers = usePeers(runId);
  const precedent = usePrecedent(runId);
  const issues = useIssues(runId);

  return (
    <div className="mx-auto w-full max-w-6xl space-y-6 px-4 py-6 md:px-6">
      <RunPageHeader
        runId={runId}
        protocolName={protocolName(protocol, runId)}
        current="burden"
        title="Participant burden and peer comparison"
        description="What this protocol asks of a participant, and how that compares with similar trials. Estimates use stated cost and time assumptions; they are not measurements."
      />

      <QueryGate query={burden} skeleton={<Skeleton className="h-64 w-full" />}>
        {(b) => <BurdenSection burden={b} />}
      </QueryGate>

      <QueryGate query={peers} skeleton={<Skeleton className="h-64 w-full" />}>
        {(p) => <PeersSection peers={p} issues={issues.data?.items ?? []} runId={runId} />}
      </QueryGate>

      <QueryGate query={precedent} skeleton={<Skeleton className="h-48 w-full" />}>
        {(p) => <PrecedentSection precedent={p} />}
      </QueryGate>
    </div>
  );
}

function Card({ title, note, children, id }: { title: string; note?: React.ReactNode; children: React.ReactNode; id: string }) {
  return (
    <section aria-labelledby={id} className="rounded-lg border bg-card">
      <div className="border-b px-4 py-3">
        <h2 id={id} className="text-sm font-semibold">
          {title}
        </h2>
        {note && <p className="mt-0.5 text-xs text-muted-foreground">{note}</p>}
      </div>
      <div className="p-4">{children}</div>
    </section>
  );
}

// ---------------------------------------------------------------------------

/** The backend answers with zeros when no schedule could be read (or drafted). */
export const hasNoSchedule = (b: Burden) => b.by_visit.length === 0 && b.per_patient.visits === 0;

function BurdenSection({ burden }: { burden: Burden }) {
  if (hasNoSchedule(burden)) {
    return (
      <Card id="burden-heading" title="Burden per participant">
        <p className="text-sm text-muted-foreground" data-no-schedule>
          No Schedule of Activities could be read from this protocol, so burden is not estimated.
        </p>
      </Card>
    );
  }
  const p = burden.per_patient;
  const tiles = [
    { icon: Hospital, label: "Visits", value: nf.format(p.visits) },
    { icon: Layers, label: "Procedures", value: nf.format(p.procedures_total) },
    { icon: Syringe, label: "Invasive", value: nf.format(p.invasive) },
    { icon: Users, label: "Patient time", value: `${p.patient_hours} h` },
    { icon: Clock, label: "Site time", value: `${p.site_hours} h` },
    { icon: Wallet, label: "Cost per patient", value: formatUsd(p.cost_usd) },
  ];
  const visits = [...burden.by_visit].sort((a, b) => (a.study_day ?? Infinity) - (b.study_day ?? Infinity) || 0);
  const maxMinutes = Math.max(...visits.map((v) => Math.max(v.patient_minutes, v.site_minutes)), 1);

  return (
    <Card
      id="burden-heading"
      title="Burden per participant"
      note={`Cost and time assumptions: ${burden.assumptions.file}, version ${burden.assumptions.version}.`}
    >
      <dl className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-6">
        {tiles.map(({ icon: Icon, label, value }) => (
          <div key={label} className="rounded-md border bg-muted/30 px-3 py-2.5">
            <dt className="flex items-center gap-1.5 text-xs text-muted-foreground">
              <Icon className="size-3.5" aria-hidden />
              {label}
            </dt>
            <dd className="mt-0.5 text-xl leading-7 font-semibold tabular">{value}</dd>
          </div>
        ))}
      </dl>

      {burden.coverage && burden.coverage.unmatched.length > 0 && (
        <p className="mt-3 text-xs text-muted-foreground" data-coverage>
          {burden.coverage.matched} of {burden.coverage.procedures} procedures were priced from the cost table. Not priced:{" "}
          {burden.coverage.unmatched.slice(0, 6).join(", ")}
          {burden.coverage.unmatched.length > 6 ? ` and ${burden.coverage.unmatched.length - 6} more` : ""}. Totals understate those.
        </p>
      )}

      <div className="mt-6 grid gap-6 lg:grid-cols-[minmax(0,3fr)_minmax(0,2fr)]">
        <div>
          <div className="flex flex-wrap items-center justify-between gap-2">
            <h3 className="text-xs font-semibold">Time per visit</h3>
            <span className="flex items-center gap-3 text-xs text-muted-foreground">
              <span className="flex items-center gap-1.5">
                <span aria-hidden className="size-2.5 rounded-sm bg-primary" />
                Patient
              </span>
              <span className="flex items-center gap-1.5">
                <span aria-hidden className="size-2.5 rounded-sm bg-brand-muted" />
                Site
              </span>
            </span>
          </div>
          <ol className="mt-2 space-y-1.5" data-visit-chart>
            {visits.map((v) => (
              <li key={`${v.visit}-${v.study_day}`} className="grid grid-cols-[7.5rem_1fr_3.5rem] items-center gap-2 text-xs" title={v.procedures.join(", ")}>
                <span className="min-w-0">
                  <span className="block truncate font-medium">{v.visit}</span>
                  <span className="block text-[11px] text-muted-foreground tabular">{v.study_day != null ? `Day ${v.study_day}` : "Day not stated"}</span>
                </span>
                <span className="space-y-0.5">
                  <span className="block h-2 rounded-full bg-primary" style={{ width: `${(v.patient_minutes / maxMinutes) * 100}%` }} />
                  <span className="block h-1.5 rounded-full bg-brand-muted" style={{ width: `${(v.site_minutes / maxMinutes) * 100}%` }} />
                </span>
                <span className="text-right tabular">{v.patient_minutes} min</span>
              </li>
            ))}
          </ol>
          <p className="mt-2 text-xs text-muted-foreground">Hover a visit to list its procedures.</p>
        </div>

        <div>
          <h3 className="text-xs font-semibold">Procedures with no stated purpose</h3>
          {burden.orphan_procedures.length === 0 ? (
            <p className="mt-2 text-sm text-muted-foreground">Every scheduled procedure is linked to an objective or endpoint.</p>
          ) : (
            <>
              <p className="mt-0.5 text-xs text-muted-foreground">Scheduled, but not tied to any objective or endpoint. Candidates to remove.</p>
              <ul className="mt-2 divide-y rounded-md border" data-orphans>
                {burden.orphan_procedures.map((o) => (
                  <li key={o.name} className="px-3 py-2 text-sm">
                    <p className="font-medium">{o.name}</p>
                    <p className="text-xs text-muted-foreground tabular">
                      {o.occurrences} times · {o.patient_minutes} patient min · {formatUsd(o.cost_usd)}
                    </p>
                  </li>
                ))}
              </ul>
            </>
          )}

          {burden.peer_percentiles ? (
            <>
            <h3 className="mt-5 text-xs font-semibold">Against {burden.peer_percentiles.n_peers_with_soa} peers with a schedule</h3>
            <div className="mt-2 space-y-3.5">
              <PercentileBar label="Patient hours" percentile={burden.peer_percentiles.patient_hours} peers={burden.peer_percentiles.n_peers_with_soa} />
              <PercentileBar label="Procedures" percentile={burden.peer_percentiles.procedures_total} peers={burden.peer_percentiles.n_peers_with_soa} />
              <PercentileBar label="Visits" percentile={burden.peer_percentiles.visits} peers={burden.peer_percentiles.n_peers_with_soa} />
            </div>
            </>
          ) : (
            <p className="mt-5 text-sm text-muted-foreground">Too few peer trials have a published schedule to rank this protocol.</p>
          )}
        </div>
      </div>
    </Card>
  );
}

// ---------------------------------------------------------------------------

function PeersSection({ peers, issues, runId }: { peers: Peers; issues: Issue[]; runId: string }) {
  const hotspots = peers.hotspot_issue_ids.map((id) => issues.find((i) => i.id === id)).filter((i): i is Issue => !!i);
  return (
    <Card
      id="peers-heading"
      title={`Peer comparison: ${peers.n} trials`}
      note={`${peers.query.condition ?? "Condition not identified"}, ${formatPhase(peers.query.phase)}, started ${peers.query.start_year_min} or later. Each chart shows peers; the blue line is this protocol, the dashed line the peer median, the shaded band the middle half.`}
    >
      <div className="grid gap-x-6 gap-y-5 sm:grid-cols-2 lg:grid-cols-3" data-peer-metrics>
        {peers.metrics.map((m) => (
          <figure key={m.metric} data-metric={m.metric}>
            <figcaption className="flex items-baseline justify-between gap-2 text-sm">
              <span className="font-medium">{m.label}</span>
              <span className="text-xs text-muted-foreground tabular">
                <b className="text-sm text-foreground">{m.value}</b> vs median {m.peer_median}
              </span>
            </figcaption>
            <Histogram values={m.distribution} value={m.value} median={m.peer_median} p25={m.peer_p25} p75={m.peer_p75} label={m.label} />
            <p className={cn("text-xs tabular", m.percentile >= 75 ? "font-medium text-sev-major" : "text-muted-foreground")}>
              {m.percentile}th percentile
            </p>
          </figure>
        ))}
      </div>

      {hotspots.length > 0 && (
        <div className="mt-6">
          <h3 className="text-xs font-semibold">Amendment hotspots</h3>
          <p className="mt-0.5 text-xs text-muted-foreground">Places where this protocol is unusually strict compared with its peers, so more likely to be amended.</p>
          <ul className="mt-2 divide-y rounded-md border" data-hotspots>
            {hotspots.map((issue) => {
              const meta = SEVERITY_META[issue.severity];
              return (
                <li key={issue.id}>
                  <Link
                    href={`/runs/${runId}?issue=${issue.id}`}
                    className="flex items-center gap-2.5 px-3 py-2 text-sm hover:bg-muted/60 focus-visible:ring-2 focus-visible:ring-ring/50 focus-visible:outline-none focus-visible:ring-inset"
                  >
                    <meta.icon className={cn("size-4 shrink-0", meta.text)} aria-label={meta.label} />
                    <span className="min-w-0 flex-1">{issue.title}</span>
                    <span className="shrink-0 text-xs font-medium text-primary">Open in review →</span>
                  </Link>
                </li>
              );
            })}
          </ul>
        </div>
      )}

      <details className="mt-6 text-sm">
        <summary className="cursor-pointer text-xs font-semibold">Peer trials ({peers.trials.length} shown)</summary>
        <div className="mt-2 overflow-x-auto rounded-md border">
          <table className="w-full text-xs">
            <thead className="bg-muted/50 text-left text-muted-foreground">
              <tr>
                <th className="px-3 py-1.5 font-medium">Trial</th>
                <th className="px-3 py-1.5 font-medium">Sponsor</th>
                <th className="px-3 py-1.5 text-right font-medium">Enrollment</th>
                <th className="px-3 py-1.5 font-medium">Start</th>
              </tr>
            </thead>
            <tbody className="divide-y">
              {peers.trials.map((t) => (
                <tr key={t.nct_id}>
                  <td className="px-3 py-1.5">
                    <NctLink id={t.nct_id} />
                    <span className="ml-2">{t.title}</span>
                  </td>
                  <td className="px-3 py-1.5">{t.sponsor}</td>
                  <td className="px-3 py-1.5 text-right tabular">{num(t.enrollment)}</td>
                  <td className="px-3 py-1.5 tabular">{t.start_date ?? "-"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </details>
    </Card>
  );
}

export function NctLink({ id }: { id: string }) {
  return (
    <a
      href={`https://clinicaltrials.gov/study/${encodeURIComponent(id)}`}
      target="_blank"
      rel="noopener noreferrer"
      className="rounded-sm font-mono text-primary underline-offset-2 hover:underline focus-visible:ring-2 focus-visible:ring-ring/50 focus-visible:outline-none"
    >
      {id}
    </a>
  );
}

// ---------------------------------------------------------------------------

/** 4.10: this protocol on the first row, similar trials beneath it, with differences marked. */
export function PrecedentTable({ precedent }: { precedent: Precedent }) {
  const me = precedent.this_protocol;
  // A draft has not stated these yet; marking every row "differs" against a blank would be noise.
  const diff = (a: string, b: string) => !!b.trim() && a.trim().toLowerCase() !== b.trim().toLowerCase();
  const Mark = ({ different }: { different: boolean }) =>
    different ? <span className="ml-1 rounded-sm bg-sev-minor-bg px-1 text-[10px] font-semibold text-sev-minor uppercase">differs</span> : null;

  return (
    <div className="overflow-x-auto rounded-md border">
      <table className="w-full min-w-[56rem] text-xs" data-precedent>
        <thead className="bg-muted/50 text-left text-muted-foreground">
          <tr>
            <th className="px-3 py-2 font-medium">Trial</th>
            <th className="px-3 py-2 font-medium">Primary endpoint</th>
            <th className="px-3 py-2 font-medium">Timeframe</th>
            <th className="px-3 py-2 font-medium">Key eligibility</th>
            <th className="px-3 py-2 text-right font-medium">Enrollment</th>
            <th className="px-3 py-2 text-right font-medium">Visits</th>
            <th className="px-3 py-2 text-right font-medium">Similarity</th>
          </tr>
        </thead>
        <tbody className="divide-y align-top">
          <tr className="bg-accent/60" data-this-protocol>
            <td className="px-3 py-2 font-semibold">This protocol</td>
            <td className="px-3 py-2 font-medium">{me.primary_endpoint || NOT_STATED}</td>
            <td className="px-3 py-2 font-medium">{me.primary_timeframe || NOT_STATED}</td>
            <td className="px-3 py-2 font-medium">{me.key_eligibility.join("; ") || NOT_STATED}</td>
            <td className="px-3 py-2 text-right font-medium tabular">{me.enrollment ? num(me.enrollment) : "-"}</td>
            <td className="px-3 py-2 text-right font-medium tabular">{me.n_visits ?? "-"}</td>
            <td className="px-3 py-2 text-right text-muted-foreground">-</td>
          </tr>
          {precedent.rows.map((r) => (
            <tr key={r.nct_id}>
              <td className="px-3 py-2">
                <NctLink id={r.nct_id} />
                <span className="mt-0.5 block text-muted-foreground">
                  {r.sponsor} · {formatPhase(r.phase)}
                </span>
              </td>
              <td className="px-3 py-2">
                {r.primary_endpoint}
                <Mark different={diff(r.primary_endpoint, me.primary_endpoint)} />
              </td>
              <td className="px-3 py-2">
                {r.primary_timeframe || "-"}
                <Mark different={diff(r.primary_timeframe, me.primary_timeframe)} />
              </td>
              <td className="px-3 py-2">
                {r.key_eligibility.join("; ")}
                <Mark different={diff(r.key_eligibility.join(";"), me.key_eligibility.join(";"))} />
              </td>
              <td className="px-3 py-2 text-right tabular">{num(r.enrollment)}</td>
              <td className="px-3 py-2 text-right tabular">{r.n_visits ?? "-"}</td>
              <td className="px-3 py-2 text-right tabular">{Math.round(r.similarity * 100)}%</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function PrecedentSection({ precedent }: { precedent: Precedent }) {
  return (
    <Card
      id="precedent-heading"
      title="Precedent: the most similar trials"
      note="Where this protocol departs from its closest neighbours is marked. A difference is a question to answer, not necessarily a mistake."
    >
      <PrecedentTable precedent={precedent} />
    </Card>
  );
}
