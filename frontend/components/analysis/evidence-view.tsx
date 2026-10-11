"use client";

import { useState } from "react";

import { ErrorState } from "@/components/common/states";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";
import { AMENDMENT_LABEL, formatDateTime, formatPercent, formatUsd } from "@/lib/presentation";
import { useBenchmark } from "@/lib/queries";
import type { Benchmark } from "@/lib/types";
import { cn } from "@/lib/utils";

import { NctLink, Section, Stat, StatGrid, Table, td } from "./primitives";

const CONFIG_LABEL: Record<string, string> = {
  rules_only: "Rules only (confidential mode)",
  llm_only: "LLM only (no rules, no verifier)",
  full: "Full Pre-Flight (rules + verified AI)",
};
const METRIC_LABEL: Record<string, string> = {
  nInc: "Inclusion criteria count",
  nExc: "Exclusion criteria count",
  minAge: "Minimum age",
  maxAge: "Maximum age",
};

/** F3: PreflightBench results exactly as `preflight bench` wrote them (CONTRACTS 4.12), plus the ROI calculator (4.13). */
export function EvidenceView() {
  const bench = useBenchmark();
  if (bench.isPending) return <Skeleton className="h-96 w-full" aria-label="Loading benchmark" />;
  if (bench.isError) return <ErrorState title="Could not load benchmark results" error={bench.error} onRetry={() => void bench.refetch()} />;
  const b = bench.data;
  return (
    <>
      <Headline b={b} />
      <Ablation b={b} />
      <ByType b={b} />
      <Retrospective b={b} />
      <Roi recall={b.overall.recall} />
    </>
  );
}

function Headline({ b }: { b: Benchmark }) {
  return (
    <Section
      title="PreflightBench: injected-error test set"
      description={
        <>
          {b.test_set.injected_errors} errors injected into {b.test_set.protocols} real ClinicalTrials.gov protocols that were
          never used for tuning{b.config ? ` · configuration: ${CONFIG_LABEL[b.config] ?? b.config}` : ""} · model {b.model} ·
          generated {formatDateTime(b.generated_at)}.
        </>
      }
    >
      <StatGrid>
        <Stat label="Recall" value={formatPercent(b.overall.recall)} hint="injected errors found" />
        <Stat label="Precision" value={formatPercent(b.overall.precision)} hint="flags that were real" />
        <Stat label="F1" value={b.overall.f1.toFixed(2)} />
        <Stat label="False alarms" value={b.false_alarms_per_clean_protocol} hint="critical + major per clean protocol" />
        {b.hallucination && (
          <Stat
            label="Ungrounded AI findings shown"
            value={b.hallucination.shown_ungrounded}
            hint={`${b.hallucination.dropped_ungrounded} of ${b.hallucination.ai_findings} dropped by the verifier`}
          />
        )}
        {b.speed_cost && (
          <Stat label="Median time · cost" value={`${Math.round(b.speed_cost.median_seconds)} s`} hint={`${formatUsd(b.speed_cost.median_usd)} per protocol`} />
        )}
      </StatGrid>
      {b.human_baseline && (
        <p className="mt-4 text-sm">
          Human baseline on {b.human_baseline.protocol}: reviewers found{" "}
          {b.human_baseline.participants.map((p) => `${p.found}/${b.human_baseline!.total_errors} in ${p.minutes} min`).join(", ")};
          Pre-Flight found {b.human_baseline.preflight.found}/{b.human_baseline.total_errors} in {b.human_baseline.preflight.seconds} s.
        </p>
      )}
    </Section>
  );
}

function Ablation({ b }: { b: Benchmark }) {
  if (!b.ablation?.length) return null;
  return (
    <Section title="Ablation" description="The same injected errors, scored with parts of the system switched off.">
      <Table head={["Configuration", "Recall", "Precision", "F1"]}>
        {b.ablation.map((a) => (
          <tr key={a.config} className={cn(a.config === "full" && "font-medium")}>
            <td className={td}>{CONFIG_LABEL[a.config] ?? a.config}</td>
            <td className={`${td} tabular`}><Bar value={a.recall} /></td>
            <td className={`${td} tabular`}><Bar value={a.precision} /></td>
            <td className={`${td} tabular`}>{a.f1.toFixed(2)}</td>
          </tr>
        ))}
      </Table>
      <p className="mt-3 text-xs text-muted-foreground">
        An LLM alone flags far more than it should; rules alone miss what needs reading comprehension. Grounded AI on top of the
        rules gives the highest recall at rule-level precision.
      </p>
    </Section>
  );
}

function ByType({ b }: { b: Benchmark }) {
  return (
    <div className="grid gap-5 lg:grid-cols-3">
      <Section title="Recall by error type" className="lg:col-span-2">
        <Table head={["Type", "Error", "Found", "Recall"]}>
          {b.by_type.map((t) => (
            <tr key={t.type}>
              <td className={`${td} font-mono text-xs`}>{t.type}</td>
              <td className={td}>{t.name}</td>
              <td className={`${td} tabular`}>{t.found}/{t.n}</td>
              <td className={`${td} w-40`}><Bar value={t.recall} /></td>
            </tr>
          ))}
        </Table>
      </Section>
      <Section title="Recall by amendment category" description="Categories from the Tufts amendment studies.">
        <ul className="space-y-2">
          {b.by_category.map((c) => (
            <li key={c.amendment_category}>
              <div className="flex justify-between text-sm">
                <span>{AMENDMENT_LABEL[c.amendment_category] ?? c.amendment_category}</span>
                <span className="text-xs text-muted-foreground tabular">n = {c.n}</span>
              </div>
              <Bar value={c.recall} />
            </li>
          ))}
        </ul>
      </Section>
    </div>
  );
}

function Retrospective({ b }: { b: Benchmark }) {
  const r = b.retrospective;
  if (!r && !b.case_studies?.length) return null;
  return (
    <Section
      title="Do hotspots predict real amendments?"
      description="A retrospective check on ClinicalTrials.gov registry histories: was a trial flagged before its sponsor relaxed eligibility?"
    >
      {r && (
        <>
          <p className="text-sm">{r.population}</p>
          <Table head={["Metric", "Relaxed later", "Flagged before the edit", "Flag rate in other trials", "Odds ratio", "p (one-sided)"]} className="mt-3">
            {Object.entries(r.result).map(([k, v]) => (
              <tr key={k}>
                <td className={td}>{METRIC_LABEL[k] ?? k}</td>
                <td className={`${td} tabular`}>{v.relaxed_trials}</td>
                <td className={`${td} tabular`}>{v.flagged_before_edit}{v.relaxed_trials ? ` (${formatPercent(v.flagged_before_edit / v.relaxed_trials)})` : ""}</td>
                <td className={`${td} tabular`}>{v.other_trials ? formatPercent(v.other_flagged / v.other_trials) : "-"}</td>
                <td className={`${td} tabular`}>{v.odds_ratio?.toFixed(2) ?? "-"}</td>
                <td className={`${td} tabular`}>{v.fisher_one_sided_p?.toFixed(3) ?? "-"}</td>
              </tr>
            ))}
          </Table>
          <details className="mt-3 text-xs text-muted-foreground">
            <summary className="cursor-pointer font-medium">Method and caveats</summary>
            <p className="mt-2">{r.method}</p>
            <ul className="mt-2 list-disc space-y-1 pl-4">{r.caveats.map((c) => <li key={c}>{c}</li>)}</ul>
          </details>
        </>
      )}
      {!!b.case_studies?.length && (
        <div className="mt-5">
          <h3 className="text-xs font-medium text-muted-foreground">Case studies</h3>
          <ul className="mt-2 grid gap-2 md:grid-cols-2">
            {b.case_studies.map((c) => (
              <li key={c.nct_id + c.change} className="rounded-md border p-3 text-sm">
                <NctLink nctId={c.nct_id} />
                <p className="mt-1 font-medium">{c.change}</p>
                <p className="mt-0.5 text-xs text-muted-foreground">{c.summary}</p>
              </li>
            ))}
          </ul>
        </div>
      )}
    </Section>
  );
}

/** CONTRACTS 4.13: expected value of catching avoidable amendments before finalisation. */
function Roi({ recall }: { recall: number }) {
  const [phase, setPhase] = useState<"2" | "3">("3");
  const [pAmend, setPAmend] = useState(0.57);
  const [share, setShare] = useState(0.45);
  const [catchRate, setCatchRate] = useState(Math.round(recall * 100) / 100);
  const cost = phase === "2" ? 141000 : 535000;
  const avoidable = pAmend * share * cost;
  const avoided = avoidable * catchRate;
  const months = pAmend * share * 3 * catchRate;

  return (
    <Section title="What it could save" description="Expected value per protocol. Every input is adjustable; the defaults and sources are listed below.">
      <div className="grid gap-6 lg:grid-cols-[1fr_minmax(0,22rem)]">
        <div className="space-y-4">
          <div role="group" aria-label="Phase" className="inline-flex rounded-md border bg-muted p-0.5">
            {(["2", "3"] as const).map((p) => (
              <button key={p} type="button" aria-pressed={phase === p} onClick={() => setPhase(p)}
                className={cn("rounded px-3 py-1 text-xs font-medium", phase === p ? "bg-card shadow-sm" : "text-muted-foreground")}>
                Phase {p === "2" ? "II" : "III"}
              </button>
            ))}
          </div>
          <Slider id="p-amend" label="Protocols with a substantial amendment" value={pAmend} min={0.3} max={0.8} onChange={setPAmend} />
          <Slider id="share" label="Share of those amendments that were avoidable" value={share} min={0.33} max={0.45} onChange={setShare} />
          <Slider id="catch" label="Catch rate (benchmark recall by default)" value={catchRate} min={0.1} max={1} onChange={setCatchRate} />
          <p className="text-xs text-muted-foreground">
            Sources: 57% of protocols have at least one substantial amendment and 45% of those were judged avoidable (Getz et al.
            2016, DIA Therapeutic Innovation &amp; Regulatory Science; the lower bound 33% comes from the same Tufts CSDD work).
            Median direct cost per amendment: {formatUsd(141000)} Phase II, {formatUsd(535000)} Phase III (Getz et al. 2016).
            Trials with an amendment took about 3 months longer (Applied Clinical Trials).
          </p>
        </div>
        <dl className="grid content-start gap-4 rounded-lg border bg-muted/40 p-4">
          <Stat label="Expected avoidable amendment cost" value={formatUsd(avoidable)} />
          <Stat label="Expected cost avoided with Pre-Flight" value={formatUsd(avoided)} />
          <Stat label="Expected delay avoided" value={`${months.toFixed(1)} months`} />
          <p className="text-xs text-muted-foreground">
            {formatPercent(pAmend)} × {formatPercent(share)} × {formatUsd(cost)} × {formatPercent(catchRate)} catch rate
          </p>
        </dl>
      </div>
    </Section>
  );
}

function Slider({ id, label, value, min, max, onChange }: {
  id: string; label: string; value: number; min: number; max: number; onChange: (v: number) => void;
}) {
  return (
    <div className="space-y-1">
      <div className="flex justify-between gap-2">
        <Label htmlFor={id} className="text-sm font-normal">{label}</Label>
        <span className="text-sm font-medium tabular">{formatPercent(value)}</span>
      </div>
      <input id={id} type="range" min={min} max={max} step={0.01} value={value}
        onChange={(e) => onChange(Number(e.target.value))} className="w-full accent-primary" />
    </div>
  );
}

function Bar({ value }: { value: number }) {
  return (
    <span className="flex items-center gap-2">
      <span className="block h-1.5 flex-1 rounded-full bg-track" aria-hidden>
        <span className="block h-1.5 rounded-full bg-primary" style={{ width: `${Math.max(0, Math.min(1, value)) * 100}%` }} />
      </span>
      <span className="w-10 text-right text-xs tabular">{formatPercent(value)}</span>
    </span>
  );
}
