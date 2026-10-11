"use client";

import { FlaskConical } from "lucide-react";
import type { ReactNode } from "react";

import { PageHeader } from "@/components/common/page-header";
import { QueryGate } from "@/components/common/query-gate";
import { Skeleton } from "@/components/ui/skeleton";
import { USE_MOCKS } from "@/lib/api";
import { AMENDMENT_LABEL, formatPercent } from "@/lib/presentation";
import { useBenchmark } from "@/lib/queries";
import type { Benchmark } from "@/lib/types";
import { cn } from "@/lib/utils";

import { RoiCalculator } from "./roi-calculator";

const nf = new Intl.NumberFormat("en-US");
const dateFmt = new Intl.DateTimeFormat("en-US", { dateStyle: "medium", timeZone: "UTC" });

const ABLATION_LABEL: Record<string, string> = {
  rules_only: "Rules only",
  llm_only: "Language model only",
  full: "Full Pre-Flight",
};

export function EvidenceView() {
  const benchmark = useBenchmark();
  return (
    <div className="mx-auto w-full max-w-6xl space-y-6 px-4 py-6 md:px-6">
      <PageHeader
        title="Evidence"
        description="How well Pre-Flight finds planted errors, where it beats the alternatives, and what that could be worth."
      />
      <QueryGate query={benchmark} skeleton={<Skeleton className="h-96 w-full" />}>
        {(b) => <EvidenceBody b={b} />}
      </QueryGate>
    </div>
  );
}

function Section({ id, title, note, children }: { id: string; title: string; note?: ReactNode; children: ReactNode }) {
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

function Bar({ label, value, detail, strong }: { label: string; value: number; detail?: string; strong?: boolean }) {
  return (
    <div className="grid grid-cols-[minmax(0,10rem)_1fr_auto] items-center gap-3 text-xs sm:grid-cols-[14rem_1fr_auto]">
      <span className="truncate" title={label}>
        {label}
      </span>
      <span className="h-2 rounded-full bg-track" role="img" aria-label={`${label}: ${formatPercent(value)}`}>
        <span className={cn("block h-full rounded-full", strong ? "bg-primary" : "bg-brand-muted")} style={{ width: `${value * 100}%` }} />
      </span>
      <span className="w-24 text-right tabular">
        <b>{formatPercent(value)}</b>
        {detail && <span className="ml-1 text-muted-foreground">{detail}</span>}
      </span>
    </div>
  );
}

function Tile({ label, value, sub, big }: { label: string; value: string; sub?: string; big?: boolean }) {
  return (
    <div className="rounded-md border bg-muted/30 px-3 py-2.5">
      <p className="text-xs text-muted-foreground">{label}</p>
      <p className={cn("mt-0.5 font-semibold tabular", big ? "text-3xl leading-9 text-primary" : "text-xl leading-7")}>{value}</p>
      {sub && <p className="text-xs text-muted-foreground">{sub}</p>}
    </div>
  );
}

function EvidenceBody({ b }: { b: Benchmark }) {
  // Every section the benchmark has not measured is null; each one shows only when it has data.
  const h = b.hallucination;
  const withVerifier = h ? h.ai_findings - h.dropped_ungrounded : 0;
  const beforeRate = h && h.ai_findings ? h.dropped_ungrounded / h.ai_findings : 0;
  const afterRate = h && withVerifier ? h.shown_ungrounded / withVerifier : 0;
  const human = b.human_baseline;
  const cases = b.case_studies ?? [];
  const extras = [
    b.real_findings && { label: "Precision on real protocols", value: formatPercent(b.real_findings.precision), sub: `${b.real_findings.sampled} findings checked by hand` },
    b.real_findings && { label: "Agreement (kappa)", value: b.real_findings.kappa.toFixed(2), sub: "Between two labelers" },
    b.soa_extraction && { label: "Schedule extraction", value: formatPercent(b.soa_extraction.cell_accuracy), sub: `Cell accuracy, ${b.soa_extraction.protocols} protocols` },
    b.speed_cost && {
      label: "Speed and cost",
      value: `${b.speed_cost.median_seconds} s`,
      sub: `Median ${b.speed_cost.median_usd.toLocaleString("en-US", { style: "currency", currency: "USD", maximumFractionDigits: 4 })} per protocol`,
    },
  ].filter((t): t is { label: string; value: string; sub: string } => !!t);

  return (
    <>
      {USE_MOCKS ? (
        <div role="note" data-placeholder-notice className="flex items-start gap-3 rounded-lg border border-sev-minor-border bg-sev-minor-bg px-4 py-3">
          <FlaskConical className="mt-0.5 size-4 shrink-0 text-sev-minor" aria-hidden />
          <p className="text-sm text-sev-minor">
            <b>Placeholder numbers.</b> These figures come from the API contract example, not from an experiment. They show how the page
            will look. Connect the real backend to see results from <code>preflight bench</code>.
          </p>
        </div>
      ) : (
        <p className="text-xs text-muted-foreground">
          Results from <code>preflight bench</code>
          {b.set ? ` on the ${b.set} set` : ""}
          {b.config ? `, configuration ${b.config}` : ""}, generated {dateFmt.format(new Date(b.generated_at))}
          {b.model ? ` with ${b.model}` : " without a language model"}.
        </p>
      )}

      <Section
        id="overall-h"
        title="Overall accuracy on planted errors"
        note={`${b.test_set.protocols} protocols with ${nf.format(b.test_set.injected_errors)} injected errors. Injected errors do not cover every real protocol problem.`}
      >
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
          <Tile label="Recall" value={formatPercent(b.overall.recall)} sub="Planted errors found" big />
          <Tile label="Precision" value={formatPercent(b.overall.precision)} sub="Findings that were real" big />
          <Tile label="F1" value={b.overall.f1.toFixed(2)} sub="Balance of the two" big />
          {b.false_alarms_per_clean_protocol != null && (
            <Tile label="False alarms" value={b.false_alarms_per_clean_protocol.toFixed(1)} sub="Per clean protocol" />
          )}
        </div>
      </Section>

      <div className="grid gap-6 lg:grid-cols-2">
        <Section id="type-h" title="Recall by error type" note="Share of planted errors of each type that were found.">
          <div className="space-y-2.5" data-by-type>
            {b.by_type.map((t) =>
              t.measurable === false ? (
                <p key={t.type} className="grid grid-cols-[minmax(0,10rem)_1fr] gap-3 text-xs text-muted-foreground sm:grid-cols-[14rem_1fr]">
                  <span className="truncate" title={`${t.type} ${t.name}`}>
                    {t.type} {t.name}
                  </span>
                  <span>Not detectable in this configuration</span>
                </p>
              ) : (
                <Bar key={t.type} label={`${t.type} ${t.name}`} value={t.recall} detail={`${t.found}/${t.n}`} strong />
              ),
            )}
          </div>
        </Section>
        <Section id="cat-h" title="Recall by amendment area" note="Which kinds of amendment the found errors would have caused.">
          <div className="space-y-2.5" data-by-category>
            {b.by_category.map((c) => (
              <Bar key={c.amendment_category} label={AMENDMENT_LABEL[c.amendment_category] ?? c.amendment_category} value={c.recall} detail={`n=${c.n}`} strong />
            ))}
          </div>
        </Section>
      </div>

      {b.ablation.length > 0 && (
      <Section id="ablation-h" title="What each part adds" note="The same test set, run with parts switched off. Rules are precise; the model adds coverage; the verifier keeps it honest.">
        <div className="overflow-x-auto">
          <table className="w-full min-w-[32rem] text-sm" data-ablation>
            <thead className="text-left text-xs text-muted-foreground">
              <tr>
                <th className="py-1.5 pr-3 font-medium">Configuration</th>
                {(["recall", "precision", "f1"] as const).map((k) => (
                  <th key={k} className="px-3 py-1.5 text-xs font-medium capitalize">
                    {k === "f1" ? "F1" : k}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y">
              {b.ablation.map((row) => (
                <tr key={row.config} className={cn(row.config === "full" && "bg-accent/60 font-medium")}>
                  <td className="py-2 pr-3">{ABLATION_LABEL[row.config] ?? row.config}</td>
                  {(["recall", "precision", "f1"] as const).map((k) => (
                    <td key={k} className="px-3 py-2">
                      <span className="flex items-center gap-2">
                        <span className="h-1.5 w-20 rounded-full bg-track" aria-hidden>
                          <span className={cn("block h-full rounded-full", row.config === "full" ? "bg-primary" : "bg-brand-muted")} style={{ width: `${row[k] * 100}%` }} />
                        </span>
                        <span className="tabular">{k === "f1" ? row[k].toFixed(2) : formatPercent(row[k])}</span>
                      </span>
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Section>
      )}

      {(h || human) && (
      <div className="grid gap-6 lg:grid-cols-2">
        {h && (
        <Section id="halluc-h" title="Hallucination control" note="Every AI finding must quote text that exists in the protocol. Ones that do not are dropped.">
          <dl className="grid grid-cols-3 gap-3 text-center">
            <Tile label="AI findings" value={nf.format(h.ai_findings)} />
            <Tile label="Dropped as ungrounded" value={nf.format(h.dropped_ungrounded)} />
            <Tile label="Shown ungrounded" value={nf.format(h.shown_ungrounded)} />
          </dl>
          <div className="mt-4 space-y-2.5">
            <Bar label="Ungrounded without the verifier" value={beforeRate} />
            <Bar label="Ungrounded after the verifier" value={afterRate} strong />
          </div>
        </Section>
        )}

        {human && (
        <Section id="human-h" title="Against human reviewers" note={`${human.protocol}. ${human.total_errors} planted errors.`}>
          <div className="space-y-2.5" data-human-baseline>
            {human.participants.map((p) => (
              <Bar key={p.id} label={`Reviewer ${p.id}`} value={p.found / human.total_errors} detail={`${p.found}/${human.total_errors} in ${p.minutes} min`} />
            ))}
            <Bar label="Pre-Flight" value={human.preflight.found / human.total_errors} detail={`${human.preflight.found}/${human.total_errors} in ${human.preflight.seconds} s`} strong />
          </div>
        </Section>
        )}
      </div>
      )}

      {extras.length > 0 && (
      <Section id="real-h" title="Beyond the benchmark">
        <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
          {extras.map((t) => (
            <Tile key={t.label} {...t} />
          ))}
        </div>
      </Section>
      )}

      {cases.length > 0 && (
        <Section id="case-h" title="Retrospective case studies" note="Real changes made to registered trials, and whether an earlier version would have been flagged.">
          <ul className="divide-y rounded-md border" data-case-studies>
            {cases.map((c) => (
              <li key={c.nct_id + c.change} className="px-3 py-2.5 text-sm">
                <p>
                  <a
                    href={`https://clinicaltrials.gov/study/${encodeURIComponent(c.nct_id)}`}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="font-mono text-primary underline-offset-2 hover:underline"
                  >
                    {c.nct_id}
                  </a>
                  <span className="ml-2 font-medium">{c.change}</span>
                </p>
                <p className="mt-0.5 text-muted-foreground">
                  {c.flagged_in_earlier_version ? "Flagged in the earlier version. " : "Not flagged in the earlier version. "}
                  {c.summary}
                </p>
              </li>
            ))}
          </ul>
          {b.retrospective && (
            <details className="mt-3 text-xs" data-retrospective>
              <summary className="cursor-pointer font-semibold">How this was checked</summary>
              <p className="mt-1.5 leading-relaxed text-muted-foreground">{b.retrospective.population}</p>
              <p className="mt-1.5 leading-relaxed text-muted-foreground">{b.retrospective.method}</p>
              {Array.isArray(b.retrospective.caveats) && (
                <ul className="mt-1.5 list-disc space-y-0.5 pl-4 text-muted-foreground">
                  {b.retrospective.caveats.map((c, i) => (
                    <li key={i}>{String(c)}</li>
                  ))}
                </ul>
              )}
            </details>
          )}
        </Section>
      )}

      <Section id="roi-h" title="What could this be worth?" note="Move the sliders to test your own assumptions. Nothing here is sent anywhere.">
        <RoiCalculator recall={b.overall.recall} recallIsMeasured={!USE_MOCKS} />
      </Section>
    </>
  );
}
