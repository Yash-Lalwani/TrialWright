"use client";

import { Users } from "lucide-react";
import Link from "next/link";

import { SeverityBadge } from "@/components/common/badges";
import { EmptyState, ErrorState } from "@/components/common/states";
import { Skeleton } from "@/components/ui/skeleton";
import { formatPhase, formatUsd } from "@/lib/presentation";
import { useBurden, useIssues, usePeers, usePrecedent } from "@/lib/queries";
import type { Burden, Peers, Precedent, Run } from "@/lib/types";

import { Histogram, NctLink, PercentileMeter, Section, Stat, StatGrid, Table, td } from "./primitives";

/** D1 burden, D2 peer benchmarking, D3 hotspots and E6 precedent for one run (CONTRACTS 4.8–4.10). */
export function BurdenView({ run }: { run: Run }) {
  const burden = useBurden(run.run_id);
  const peers = usePeers(run.run_id);
  const precedent = usePrecedent(run.run_id);
  return (
    <>
      <Loaded query={burden} label="burden">{(b) => <BurdenSection burden={b} />}</Loaded>
      <Loaded query={peers} label="peer comparison">{(p) => <PeersSection peers={p} runId={run.run_id} />}</Loaded>
      <Loaded query={precedent} label="precedent">{(p) => <PrecedentSection precedent={p} />}</Loaded>
    </>
  );
}

function Loaded<T>({
  query,
  label,
  children,
}: {
  query: { isPending: boolean; isError: boolean; error: unknown; data?: T; refetch: () => unknown };
  label: string;
  children: (data: T) => React.ReactNode;
}) {
  if (query.isPending) return <Skeleton className="h-48 w-full" aria-label={`Loading ${label}`} />;
  if (query.isError) return <ErrorState title={`Could not load ${label}`} error={query.error} onRetry={() => void query.refetch()} />;
  return <>{children(query.data as T)}</>;
}

function BurdenSection({ burden }: { burden: Burden }) {
  const pp = burden.per_patient;
  const maxMinutes = Math.max(...burden.by_visit.map((v) => v.patient_minutes), 1);
  return (
    <Section
      title="Participant burden"
      description={
        <>
          Per participant, from the Schedule of Activities. Time and cost per procedure are labelled assumptions from{" "}
          <code>{burden.assumptions.file}</code> (version {burden.assumptions.version}).
        </>
      }
    >
      <StatGrid>
        <Stat label="Visits" value={pp.visits} />
        <Stat label="Procedures" value={pp.procedures_total} />
        <Stat label="Invasive procedures" value={pp.invasive} />
        <Stat label="Patient hours" value={pp.patient_hours.toFixed(1)} />
        <Stat label="Site hours" value={pp.site_hours.toFixed(1)} />
        <Stat label="Cost per patient" value={formatUsd(pp.cost_usd)} />
      </StatGrid>

      <div className="mt-6 grid gap-6 lg:grid-cols-2">
        <div>
          <h3 className="text-xs font-medium text-muted-foreground">Compared with similar trials</h3>
          {burden.peer_percentiles ? (
            <div className="mt-2 space-y-2.5">
              {(["patient_hours", "procedures_total", "visits"] as const).map((k) => (
                <div key={k}>
                  <div className="text-xs">{{ patient_hours: "Patient hours", procedures_total: "Procedures", visits: "Visits" }[k]}</div>
                  <PercentileMeter percentile={burden.peer_percentiles![k]} />
                </div>
              ))}
              <p className="text-xs text-muted-foreground">
                {burden.peer_percentiles.scope === "library"
                  ? `Percentile among all ${burden.peer_percentiles.n_peers_with_soa} trials in our library whose Schedule of Activities was parsed (all conditions: too few similar trials had one).`
                  : `Percentile among ${burden.peer_percentiles.n_peers_with_soa} peer protocols whose Schedule of Activities was parsed.`}{" "}
                Higher means heavier than peers.
              </p>
            </div>
          ) : (
            <p className="mt-2 text-sm text-muted-foreground">
              No peer protocols with a parsed Schedule of Activities were found for this condition, so the burden sub-score
              is neutral (50).
            </p>
          )}
        </div>

        <div>
          <h3 className="text-xs font-medium text-muted-foreground">Patient time per visit</h3>
          <ol className="mt-2 max-h-72 space-y-1 overflow-y-auto pr-1">
            {burden.by_visit.map((v, i) => (
              <li key={`${v.visit}-${i}`} className="grid grid-cols-[minmax(0,9rem)_1fr_3.5rem] items-center gap-2 text-xs"
                title={v.procedures.join(", ")}>
                <span className="truncate">{v.visit}</span>
                <span className="block h-2 rounded-full bg-track">
                  <span className="block h-2 rounded-full bg-primary" style={{ width: `${(v.patient_minutes / maxMinutes) * 100}%` }} />
                </span>
                <span className="text-right tabular">{Math.round(v.patient_minutes)} min</span>
              </li>
            ))}
          </ol>
        </div>
      </div>

      {burden.orphan_procedures.length > 0 && (
        <div className="mt-6">
          <h3 className="text-xs font-medium text-muted-foreground">Procedures that serve no objective</h3>
          <Table head={["Procedure", "Occurrences", "Patient minutes", "Cost"]} className="mt-1">
            {burden.orphan_procedures.map((o) => (
              <tr key={o.name}>
                <td className={td}>{o.name}</td>
                <td className={`${td} tabular`}>{o.occurrences}</td>
                <td className={`${td} tabular`}>{Math.round(o.patient_minutes)}</td>
                <td className={`${td} tabular`}>{formatUsd(o.cost_usd)}</td>
              </tr>
            ))}
          </Table>
        </div>
      )}
    </Section>
  );
}

function PeersSection({ peers, runId }: { peers: Peers; runId: string }) {
  const issues = useIssues(runId);
  const hotspots = (issues.data?.items ?? []).filter((i) => peers.hotspot_issue_ids.includes(i.id));
  if (!peers.n) {
    return (
      <Section title="Peer benchmarking">
        <EmptyState icon={Users} title="No comparable trials found on ClinicalTrials.gov" />
      </Section>
    );
  }
  return (
    <Section
      title="Peer benchmarking"
      description={`${peers.n} ClinicalTrials.gov trials: ${peers.query.condition}, ${formatPhase(peers.query.phase)}, started ${peers.query.start_year_min} or later.`}
    >
      <div className="grid gap-x-8 gap-y-5 md:grid-cols-2">
        {peers.metrics.map((m) => (
          <div key={m.metric}>
            <div className="flex items-baseline justify-between gap-2 text-sm">
              <span className="font-medium">{m.label}</span>
              <span className="text-xs text-muted-foreground tabular">
                this protocol <span className="font-semibold text-foreground">{m.value}</span> · peer median {m.peer_median}
              </span>
            </div>
            <Histogram values={m.distribution} marker={m.value} />
            <PercentileMeter percentile={m.percentile} />
          </div>
        ))}
      </div>

      <div className="mt-6">
        <h3 className="text-xs font-medium text-muted-foreground">Amendment-risk hotspots</h3>
        {hotspots.length ? (
          <ul className="mt-2 space-y-2">
            {hotspots.map((h) => (
              <li key={h.id} className="rounded-md border p-3">
                <div className="flex items-start justify-between gap-2">
                  <span className="text-sm font-medium">{h.title}</span>
                  <SeverityBadge severity={h.severity} />
                </div>
                <p className="mt-1 text-xs text-muted-foreground">{h.why.explanation}</p>
                <Link href={`/runs/${runId}?issue=${h.id}`} className="mt-1 inline-block text-xs font-medium text-primary hover:underline">
                  Show in the protocol
                </Link>
              </li>
            ))}
          </ul>
        ) : (
          <p className="mt-1 text-sm text-muted-foreground">No eligibility or schedule choices stand out against these peers.</p>
        )}
      </div>

      {peers.trials.length > 0 && (
        <details className="mt-6">
          <summary className="cursor-pointer text-xs font-medium text-muted-foreground">Peer trials ({peers.trials.length})</summary>
          <Table head={["NCT", "Title", "Sponsor", "Phase", "Enrollment", "Start"]} className="mt-2 max-h-80 overflow-y-auto">
            {peers.trials.map((t) => (
              <tr key={t.nct_id}>
                <td className={td}><NctLink nctId={t.nct_id} /></td>
                <td className={`${td} max-w-md`}>{t.title}</td>
                <td className={td}>{t.sponsor}</td>
                <td className={`${td} whitespace-nowrap`}>{formatPhase(t.phase)}</td>
                <td className={`${td} tabular`}>{t.enrollment}</td>
                <td className={`${td} tabular`}>{t.start_date}</td>
              </tr>
            ))}
          </Table>
        </details>
      )}
    </Section>
  );
}

export function PrecedentSection({ precedent }: { precedent: Precedent }) {
  const me = precedent.this_protocol;
  return (
    <Section title="Precedent" description="What the most similar trials chose for the same design decisions.">
      <Table head={["Trial", "Similarity", "Primary endpoint", "Timeframe", "Key eligibility", "Enrollment", "Visits"]}>
        <tr className="bg-accent/40">
          <td className={`${td} font-medium`}>This protocol</td>
          <td className={td}>-</td>
          <td className={td}>{me.primary_endpoint}</td>
          <td className={td}>{me.primary_timeframe}</td>
          <td className={td}>{me.key_eligibility.join("; ")}</td>
          <td className={`${td} tabular`}>{me.enrollment ?? "-"}</td>
          <td className={`${td} tabular`}>{me.n_visits ?? "-"}</td>
        </tr>
        {precedent.rows.map((r) => (
          <tr key={r.nct_id}>
            <td className={td}>
              <NctLink nctId={r.nct_id} />
              <div className="line-clamp-2 max-w-56 text-xs text-muted-foreground" title={r.title}>{r.title}</div>
            </td>
            <td className={`${td} tabular`}>{Math.round(r.similarity * 100)}%</td>
            <td className={td}>{r.primary_endpoint}</td>
            <td className={td}>{r.primary_timeframe}</td>
            <td className={td}>{r.key_eligibility.join("; ")}</td>
            <td className={`${td} tabular`}>{r.enrollment ?? "-"}</td>
            <td className={`${td} tabular`}>{r.n_visits ?? "-"}</td>
          </tr>
        ))}
      </Table>
    </Section>
  );
}
