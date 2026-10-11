"use client";

import { useQueryClient } from "@tanstack/react-query";
import { Download, RotateCcw } from "lucide-react";
import { useRouter, useSearchParams } from "next/navigation";
import { useCallback, useEffect, useState } from "react";

import { PrecedentTable } from "@/components/analysis/burden-view";
import { PageHeader } from "@/components/common/page-header";
import { RunProgress } from "@/components/common/run-progress";
import { ErrorState } from "@/components/common/states";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { createDraft, draftExportUrl, subscribeDraftEvents, USE_MOCKS } from "@/lib/api";
import { Markdown, nctUrl } from "@/lib/markdown";
import { DRAFT_STEP_LABEL, formatPhase, formatUsd, SEVERITY_META } from "@/lib/presentation";
import { useDraft } from "@/lib/queries";
import { DRAFT_STEPS, type Brief, type Draft, type DraftProgressEvent } from "@/lib/types";
import { cn } from "@/lib/utils";

import { ScoreCard } from "@/components/workspace/score-card";
import { BriefForm } from "./brief-form";

type Phase =
  | { kind: "brief" }
  | { kind: "starting" }
  | { kind: "running"; draftId: string; events: Partial<Record<string, DraftProgressEvent>> }
  | { kind: "error"; message: string };

/** Brief, then progress, then the drafted protocol. The draft id lives in the URL so a reload keeps the result. */
export function DraftView() {
  const router = useRouter();
  const params = useSearchParams();
  const queryClient = useQueryClient();
  const urlDraft = params.get("draft");
  const [phase, setPhase] = useState<Phase>({ kind: "brief" });

  const start = useCallback(
    async (brief: Brief) => {
      setPhase({ kind: "starting" });
      try {
        const created = await createDraft(brief);
        setPhase({ kind: "running", draftId: created.draft_id, events: {} });
      } catch (error) {
        setPhase({ kind: "error", message: error instanceof Error ? error.message : "Could not start the draft." });
      }
    },
    [],
  );

  const draftId = phase.kind === "running" ? phase.draftId : null;
  useEffect(() => {
    if (!draftId) return;
    return subscribeDraftEvents(draftId, {
      onProgress: (e) => setPhase((p) => (p.kind === "running" ? { ...p, events: { ...p.events, [e.step]: e } } : p)),
      onComplete: (id) => {
        void queryClient.invalidateQueries({ queryKey: ["draft", id] });
        setPhase({ kind: "brief" });
        router.replace(`/draft?draft=${encodeURIComponent(id)}`);
      },
      onError: (message) => setPhase({ kind: "error", message }),
    });
  }, [draftId, queryClient, router]);

  const reset = () => {
    setPhase({ kind: "brief" });
    router.replace("/draft");
  };

  const showResult = urlDraft && phase.kind === "brief";

  return (
    <div className="mx-auto w-full max-w-6xl space-y-6 px-4 py-6 md:px-6">
      <PageHeader
        title="Draft a protocol"
        description="Turn a design brief into an ICH M11 draft with precedent from similar trials, a sample-size calculation and a self-check."
        actions={
          showResult ? (
            <Button variant="outline" size="sm" onClick={reset}>
              <RotateCcw aria-hidden /> New brief
            </Button>
          ) : undefined
        }
      />

      {(phase.kind === "brief" || phase.kind === "starting") && !urlDraft && <BriefForm pending={phase.kind === "starting"} onSubmit={start} />}

      {phase.kind === "running" && (
        <div className="max-w-xl rounded-lg border bg-card p-4">
          <h2 className="mb-3 text-sm font-semibold">Drafting your protocol</h2>
          <RunProgress events={phase.events} steps={DRAFT_STEPS} labels={DRAFT_STEP_LABEL} ariaLabel="Draft progress" />
        </div>
      )}

      {phase.kind === "error" && (
        <div className="space-y-3">
          <ErrorState title="The draft could not be created" error={new Error(phase.message)} />
          <Button variant="outline" size="sm" onClick={reset}>
            Back to the brief
          </Button>
        </div>
      )}

      {showResult && <DraftResult draftId={urlDraft} />}
    </div>
  );
}

function DraftResult({ draftId }: { draftId: string }) {
  const draft = useDraft(draftId);
  if (draft.isPending) return <Skeleton className="h-96 w-full" />;
  if (draft.isError) return <ErrorState title="Could not load the draft" error={draft.error} onRetry={() => void draft.refetch()} />;
  return <DraftBody draft={draft.data} />;
}

function Panel({ id, title, note, children, actions }: { id: string; title: string; note?: string; children: React.ReactNode; actions?: React.ReactNode }) {
  return (
    <section aria-labelledby={id} className="rounded-lg border bg-card">
      <div className="flex flex-wrap items-start justify-between gap-2 border-b px-4 py-3">
        <div>
          <h2 id={id} className="text-sm font-semibold">
            {title}
          </h2>
          {note && <p className="mt-0.5 text-xs text-muted-foreground">{note}</p>}
        </div>
        {actions}
      </div>
      <div className="p-4">{children}</div>
    </section>
  );
}

function DraftBody({ draft }: { draft: Draft }) {
  const { brief, sample_size: ss } = draft;
  const usdm = draftExportUrl(draft.draft_id, "usdm");
  const docx = draftExportUrl(draft.draft_id, "docx");

  return (
    <div className="space-y-6" data-draft-result>
      {USE_MOCKS && (
        <p role="note" className="rounded-md border border-sev-minor-border bg-sev-minor-bg px-3 py-2 text-sm text-sev-minor">
          Mock draft. This content is a fixed example of the API response. It does not reflect the brief you entered.
        </p>
      )}

      <div className="flex flex-wrap items-center justify-between gap-3 rounded-lg border bg-card px-4 py-3">
        <div className="min-w-0">
          <p className="text-xs text-muted-foreground">
            {formatPhase(brief.phase)} · {brief.condition}
          </p>
          <p className="truncate text-base font-semibold">
            {brief.intervention} vs {brief.comparator}
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <ExportLink url={usdm} label="Protocol Graph (USDM)" />
          <ExportLink url={docx} label="Word (.docx)" />
        </div>
      </div>

      <Panel id="ss-heading" title="Sample size" note={ss.method}>
        <dl className="grid grid-cols-2 gap-3 sm:grid-cols-4 lg:grid-cols-6">
          <Stat label="Total participants" value={ss.n_total} big />
          <Stat label="Per arm" value={ss.n_per_arm} big />
          <Stat label="Significance level" value={ss.inputs.alpha} />
          <Stat label="Power" value={ss.inputs.power} />
          <Stat label="Control rate" value={ss.inputs.control} />
          <Stat label="Treatment rate" value={ss.inputs.treatment} />
          <Stat label="Dropout allowed" value={ss.inputs.dropout} />
        </dl>
      </Panel>

      <Panel id="prec-heading" title="Precedent" note="Trials this draft was shaped by. Every section below cites the ones it drew on.">
        <PrecedentTable precedent={draft.precedent} />
      </Panel>

      <Panel id="sections-heading" title={`ICH M11 draft (${draft.sections.length} sections)`}>
        <div className="divide-y">
          {draft.sections.map((s) => (
            <article key={s.m11_id} className="py-4 first:pt-0 last:pb-0" data-m11-section={s.m11_id}>
              <h3 className="text-sm font-semibold">
                <span className="mr-2 font-mono text-muted-foreground">{s.m11_id}</span>
                {s.title}
              </h3>
              <div className="mt-2 max-w-3xl">
                <Markdown source={s.markdown} />
              </div>
              {s.citations.length > 0 && (
                <p className="mt-3 flex flex-wrap items-center gap-x-2 gap-y-1 text-xs text-muted-foreground">
                  Drawn from
                  {s.citations.map((id) => (
                    <a
                      key={id}
                      href={nctUrl(id)}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="rounded-sm font-mono text-primary underline-offset-2 hover:underline focus-visible:ring-2 focus-visible:ring-ring/50 focus-visible:outline-none"
                    >
                      {id}
                    </a>
                  ))}
                </p>
              )}
            </article>
          ))}
        </div>
      </Panel>

      <Panel id="self-heading" title="Self-check" note="The draft was run through the same checks as an uploaded protocol.">
        <ScoreCard score={draft.self_check.score} />
        {draft.self_check.issues.length === 0 ? (
          <p className="mt-4 text-sm text-muted-foreground">No issues found.</p>
        ) : (
          <ul className="mt-4 divide-y rounded-md border" data-self-check-issues>
            {draft.self_check.issues.map((i) => {
              const meta = SEVERITY_META[i.severity];
              return (
                <li key={i.id} className="flex items-start gap-2.5 px-3 py-2.5 text-sm">
                  <meta.icon className={cn("mt-0.5 size-4 shrink-0", meta.text)} aria-label={meta.label} />
                  <div className="min-w-0">
                    <p className="font-medium">{i.title}</p>
                    <p className="mt-0.5 text-muted-foreground">{i.why.explanation}</p>
                    {i.fix && <p className="mt-1">{i.fix.suggestion}</p>}
                  </div>
                </li>
              );
            })}
          </ul>
        )}
      </Panel>

      <Panel id="draft-burden" title="Participant burden of this design" note="Estimated from the draft's Schedule of Activities.">
        <dl className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-6">
          <Stat label="Visits" value={draft.burden.per_patient.visits} />
          <Stat label="Procedures" value={draft.burden.per_patient.procedures_total} />
          <Stat label="Invasive" value={draft.burden.per_patient.invasive} />
          <Stat label="Patient time" value={`${draft.burden.per_patient.patient_hours} h`} />
          <Stat label="Site time" value={`${draft.burden.per_patient.site_hours} h`} />
          <Stat label="Cost per patient" value={formatUsd(draft.burden.per_patient.cost_usd)} />
        </dl>
      </Panel>
    </div>
  );
}

function Stat({ label, value, big }: { label: string; value: number | string; big?: boolean }) {
  return (
    <div className="rounded-md border bg-muted/30 px-3 py-2.5">
      <dt className="text-xs text-muted-foreground">{label}</dt>
      <dd className={cn("mt-0.5 font-semibold tabular", big ? "text-2xl leading-8 text-primary" : "text-lg leading-7")}>{value}</dd>
    </div>
  );
}

function ExportLink({ url, label }: { url: string | null; label: string }) {
  if (!url) {
    return (
      <Button variant="outline" size="sm" disabled title="Exports are produced by the backend and are off on mock data">
        <Download aria-hidden /> {label}
      </Button>
    );
  }
  return (
    <Button asChild variant="outline" size="sm">
      <a href={url} download>
        <Download aria-hidden /> {label}
      </a>
    </Button>
  );
}

