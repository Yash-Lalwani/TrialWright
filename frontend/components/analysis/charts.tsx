import { cn } from "@/lib/utils";

/** "82" -> "82nd". */
export function ordinal(n: number): string {
  const rem100 = n % 100;
  if (rem100 >= 11 && rem100 <= 13) return `${n}th`;
  return `${n}${({ 1: "st", 2: "nd", 3: "rd" } as Record<number, string>)[n % 10] ?? "th"}`;
}

/**
 * Where a protocol sits among its peers, 0 to 100. Heavier than most peers is worth a look,
 * so the marker is tinted by position; the number and words carry the meaning, not the color.
 */
export function PercentileBar({ label, percentile, peers }: { label: string; percentile: number; peers: number }) {
  const high = percentile >= 75;
  return (
    <div data-percentile={label}>
      <div className="flex items-baseline justify-between gap-3 text-sm">
        <span className="font-medium">{label}</span>
        <span className={cn("text-xs tabular", high ? "font-semibold text-sev-major" : "text-muted-foreground")}>
          {ordinal(percentile)} percentile
        </span>
      </div>
      <div
        role="img"
        aria-label={`${label}: higher than ${percentile}% of ${peers} peer protocols`}
        className="relative mt-1.5 h-2.5 rounded-full bg-track"
      >
        {[25, 50, 75].map((t) => (
          <span key={t} aria-hidden className="absolute inset-y-0 w-px bg-card" style={{ left: `${t}%` }} />
        ))}
        <span
          aria-hidden
          className={cn("absolute inset-y-0 left-0 rounded-full", high ? "bg-sev-major" : "bg-primary")}
          style={{ width: `${Math.max(2, Math.min(100, percentile))}%` }}
        />
      </div>
      <p className="mt-1 text-xs text-muted-foreground">Higher than {percentile}% of {peers} peer protocols</p>
    </div>
  );
}

/**
 * Histogram of the peer distribution with this protocol marked.
 * Bin count follows the data size; the x axis spans both the peers and this protocol's value.
 */
export function Histogram({
  values,
  value,
  median,
  p25,
  p75,
  unit,
  label,
}: {
  values: number[];
  value: number;
  median: number;
  p25: number;
  p75: number;
  unit?: string;
  label: string;
}) {
  const W = 320;
  const H = 96;
  const pad = { l: 4, r: 4, t: 14, b: 18 };
  const lo = Math.min(...values, value);
  const hi = Math.max(...values, value);
  const span = hi - lo || 1;
  const binCount = Math.max(5, Math.min(10, Math.round(Math.sqrt(values.length) * 1.4)));
  const bins = Array.from({ length: binCount }, () => 0);
  for (const v of values) bins[Math.min(binCount - 1, Math.floor(((v - lo) / span) * binCount))] += 1;
  const maxBin = Math.max(...bins, 1);
  const x = (v: number) => pad.l + ((v - lo) / span) * (W - pad.l - pad.r);
  const barW = (W - pad.l - pad.r) / binCount;
  const plotH = H - pad.t - pad.b;
  const fmt = (n: number) => (Number.isInteger(n) ? String(n) : n.toFixed(1));

  return (
    <svg
      viewBox={`0 0 ${W} ${H}`}
      role="img"
      aria-label={`${label}: this protocol ${fmt(value)}${unit ?? ""}; peer median ${fmt(median)}${unit ?? ""}, middle half ${fmt(p25)} to ${fmt(p75)}`}
      className="h-auto w-full"
    >
      <rect x={x(p25)} y={pad.t} width={Math.max(1, x(p75) - x(p25))} height={plotH} className="fill-accent" />
      {bins.map((n, i) => {
        const h = (n / maxBin) * plotH;
        return (
          <rect
            key={i}
            x={pad.l + i * barW + 1}
            y={pad.t + plotH - h}
            width={Math.max(1, barW - 2)}
            height={h}
            rx={1.5}
            className="fill-brand-muted"
          />
        );
      })}
      <line x1={x(median)} x2={x(median)} y1={pad.t} y2={pad.t + plotH} className="stroke-muted-foreground" strokeDasharray="3 3" />
      <line x1={x(value)} x2={x(value)} y1={pad.t - 6} y2={pad.t + plotH} className="stroke-primary" strokeWidth={2.5} />
      <circle cx={x(value)} cy={pad.t - 6} r={3.5} className="fill-primary" />
      <line x1={pad.l} x2={W - pad.r} y1={pad.t + plotH} y2={pad.t + plotH} className="stroke-border" />
      <text x={pad.l} y={H - 4} className="fill-muted-foreground text-[10px]">
        {fmt(lo)}
      </text>
      <text x={W - pad.r} y={H - 4} textAnchor="end" className="fill-muted-foreground text-[10px]">
        {fmt(hi)}
      </text>
    </svg>
  );
}
