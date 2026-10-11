// Small presentational pieces shared by the burden, trace, compare, evidence and draft screens.

import type { ReactNode } from "react";

import { cn } from "@/lib/utils";

export function Section({
  title,
  description,
  actions,
  children,
  className,
}: {
  title: string;
  description?: ReactNode;
  actions?: ReactNode;
  children: ReactNode;
  className?: string;
}) {
  return (
    <section className={cn("rounded-lg border bg-card", className)}>
      <header className="flex flex-wrap items-start justify-between gap-3 border-b px-4 py-3">
        <div className="min-w-0">
          <h2 className="text-sm font-semibold">{title}</h2>
          {description && <p className="mt-0.5 text-xs text-muted-foreground">{description}</p>}
        </div>
        {actions}
      </header>
      <div className="p-4">{children}</div>
    </section>
  );
}

export function Stat({ label, value, hint }: { label: string; value: ReactNode; hint?: ReactNode }) {
  return (
    <div className="min-w-0">
      <dt className="truncate text-xs text-muted-foreground">{label}</dt>
      <dd className="mt-0.5 text-lg leading-7 font-semibold tabular">{value}</dd>
      {hint && <dd className="text-xs text-muted-foreground">{hint}</dd>}
    </div>
  );
}

export function StatGrid({ children, className }: { children: ReactNode; className?: string }) {
  return <dl className={cn("grid grid-cols-2 gap-x-6 gap-y-4 sm:grid-cols-3 lg:grid-cols-6", className)}>{children}</dl>;
}

/**
 * Where a value sits among peers, 0–100. Higher percentile = heavier or stricter than peers,
 * so the bar turns amber above the 75th and red above the 90th percentile.
 */
export function PercentileMeter({ percentile, label }: { percentile: number; label?: string }) {
  const p = Math.max(0, Math.min(100, percentile));
  const tone = p >= 90 ? "bg-sev-critical" : p >= 75 ? "bg-sev-major" : "bg-primary";
  return (
    <div className="flex items-center gap-2" title={label ?? `${Math.round(p)}th percentile of peers`}>
      <span className="relative block h-2 flex-1 overflow-hidden rounded-full bg-track" aria-hidden>
        <span className={cn("absolute inset-y-0 left-0 rounded-full", tone)} style={{ width: `${p}%` }} />
        {[25, 50, 75].map((t) => (
          <span key={t} className="absolute inset-y-0 w-px bg-card" style={{ left: `${t}%` }} />
        ))}
      </span>
      <span className="w-12 shrink-0 text-right text-xs font-medium tabular">{Math.round(p)}th</span>
    </div>
  );
}

/** Histogram of peer values with this protocol's value marked. Pure SVG, scales to its container. */
export function Histogram({ values, marker, bins = 16 }: { values: number[]; marker: number; bins?: number }) {
  if (!values.length) return null;
  const min = Math.min(...values, marker);
  const max = Math.max(...values, marker);
  const span = max - min || 1;
  const counts = Array.from({ length: bins }, () => 0);
  for (const v of values) counts[Math.min(bins - 1, Math.floor(((v - min) / span) * bins))] += 1;
  const peak = Math.max(...counts);
  const w = 100 / bins;
  const markerX = ((marker - min) / span) * 100;
  return (
    <svg viewBox="0 0 100 32" preserveAspectRatio="none" className="h-10 w-full" role="img"
      aria-label={`Peer distribution from ${min} to ${max}; this protocol is ${marker}`}>
      {counts.map((c, i) => (
        <rect key={i} x={i * w + 0.4} width={w - 0.8} y={32 - (c / peak) * 28} height={(c / peak) * 28}
          className="fill-chart-2 opacity-60" />
      ))}
      <line x1={markerX} x2={markerX} y1={0} y2={32} className="stroke-sev-critical" strokeWidth={1.2}
        vectorEffect="non-scaling-stroke" />
    </svg>
  );
}

export function Table({ head, children, className }: { head: ReactNode[]; children: ReactNode; className?: string }) {
  return (
    <div className={cn("overflow-x-auto", className)}>
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b text-left text-xs text-muted-foreground">
            {head.map((h, i) => (
              <th key={i} scope="col" className="px-2 py-2 font-medium whitespace-nowrap first:pl-0">
                {h}
              </th>
            ))}
          </tr>
        </thead>
        <tbody className="divide-y">{children}</tbody>
      </table>
    </div>
  );
}

export const td = "px-2 py-2 align-top first:pl-0";

export function NctLink({ nctId }: { nctId: string }) {
  return (
    <a href={`https://clinicaltrials.gov/study/${nctId}`} target="_blank" rel="noreferrer"
      className="font-mono text-xs font-medium text-primary hover:underline">
      {nctId}
    </a>
  );
}
