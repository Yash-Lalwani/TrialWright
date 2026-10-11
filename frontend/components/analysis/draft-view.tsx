"use client";

import { CircleCheck, Download, Loader2 } from "lucide-react";
import Link from "next/link";
import { useEffect, useState, type FormEvent } from "react";

import { SeverityBadge } from "@/components/common/badges";
import { ErrorState, errorMessage } from "@/components/common/states";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { ScoreCard } from "@/components/workspace/score-card";
import { createDraft, draftExportUrl, subscribeDraftEvents, USE_MOCKS } from "@/lib/api";
import { DRAFT_STEP_LABEL, SEVERITY_META } from "@/lib/presentation";
import { useDraft } from "@/lib/queries";
import { DRAFT_STEPS, type Brief, type Draft, type DraftProgressEvent, type DraftStep } from "@/lib/types";
import { cn } from "@/lib/utils";

import { PrecedentSection } from "./burden-view";
import { NctLink, Section, Stat, StatGrid } from "./primitives";

const EXAMPLE: Brief = {
  condition: "Melanoma",
  phase: "PHASE2",
  intervention: "Drug X 350 mg IV Q3W plus nivolumab",
  comparator: "Nivolumab alone",
  primary_question: "Does adding Drug X improve objective response rate versus nivolumab alone?",
  population: "Adults with unresectable or metastatic melanoma progressing on anti-PD-1 therapy",
  duration_weeks: 52,
  alpha: 0.05,
  power: 0.8,
  expected_effect: { type: "proportions", control: 0.12, treatment: 0.3 },
  dropout: 0.1,
};

/** E3/E6/E7 co-author: design brief -> precedent, sample size, M11 draft and its self-check (CONTRACTS 4.11). */
export function DraftView() {
  const [brief, setBrief] = useState<Brief>(EXAMPLE);
  const [draftId, setDraftId] = useState<string | null>(null);
  const [events, setEvents] = useState<Partial<Record<DraftStep, DraftProgressEvent>>>({});
  const [done, setDone] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const draft = useDraft(done ? draftId : null);

  useEffect(() => {
    if (!draftId || done) return;
    return subscribeDraftEvents(draftId, {
      onProgress: (e) => setEvents((prev) => ({ ...prev, [e.step]: e })),
      onComplete: () => setDone(true),
      onError: setError,
    });
  }, [draftId, done]);

  async function submit(e: FormEvent) {
    e.preventDefault();
    setSubmitting(true);
    setError(null);
    setEvents({});
    setDone(false);
    try {
      setDraftId((await createDraft(brief)).draft_id);
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setSubmitting(false);
    }
  }

  const busy = submitting || (!!draftId && !done && !error);
  return (
    <div className="space-y-5">
      <BriefForm brief={brief} onChange={setBrief} onSubmit={submit} busy={busy} />
      {draftId && !done && <DraftProgress events={events} failed={!!error} />}
      {error && <ErrorState title="The draft could not be generated" error={new Error(error)} />}
      {draft.isError && <ErrorState error={draft.error} onRetry={() => void draft.refetch()} />}
      {draft.data && <DraftResult draft={draft.data} />}
    </div>
  );
}

function BriefForm({ brief, onChange, onSubmit, busy }: {
  brief: Brief; onChange: (b: Brief) => void; onSubmit: (e: FormEvent) => void; busy: boolean;
}) {
  const text = (k: "condition" | "intervention" | "comparator" | "primary_question" | "population") => ({
    id: k, value: brief[k], required: true, onChange: (e: React.ChangeEvent<HTMLInputElement>) => onChange({ ...brief, [k]: e.target.value }),
  });
  const num = (value: number, set: (v: number) => void, step = "0.01") => ({
    type: "number", step, value, required: true, onChange: (e: React.ChangeEvent<HTMLInputElement>) => set(Number(e.target.value)),
  });
  return (
    <Section title="Design brief" description="A short brief is enough. The sample size comes from a statistical calculator, never from the model.">
      <form onSubmit={onSubmit} className="space-y-4">
        <div className="grid gap-4 md:grid-cols-2">
          <Field label="Condition"><Input {...text("condition")} /></Field>
          <Field label="Phase">
            <select id="phase" value={brief.phase} onChange={(e) => onChange({ ...brief, phase: e.target.value })}
              className="h-9 w-full rounded-md border bg-card px-2 text-sm">
              {["PHASE1", "PHASE2", "PHASE3"].map((p) => <option key={p} value={p}>{p.replace("PHASE", "Phase ")}</option>)}
            </select>
          </Field>
          <Field label="Intervention"><Input {...text("intervention")} /></Field>
          <Field label="Comparator"><Input {...text("comparator")} /></Field>
          <Field label="Primary question" className="md:col-span-2"><Input {...text("primary_question")} /></Field>
          <Field label="Population" className="md:col-span-2"><Input {...text("population")} /></Field>
        </div>
        <div className="grid grid-cols-2 gap-4 md:grid-cols-6">
          <Field label="Duration (weeks)"><Input id="duration" {...num(brief.duration_weeks, (v) => onChange({ ...brief, duration_weeks: v }), "1")} /></Field>
          <Field label="Alpha"><Input id="alpha" {...num(brief.alpha, (v) => onChange({ ...brief, alpha: v }))} /></Field>
          <Field label="Power"><Input id="power" {...num(brief.power, (v) => onChange({ ...brief, power: v }))} /></Field>
          <Field label="Control response rate"><Input id="control" {...num(brief.expected_effect.control, (v) => onChange({ ...brief, expected_effect: { ...brief.expected_effect, control: v } }))} /></Field>
          <Field label="Treatment response rate"><Input id="treatment" {...num(brief.expected_effect.treatment, (v) => onChange({ ...brief, expected_effect: { ...brief.expected_effect, treatment: v } }))} /></Field>
          <Field label="Dropout"><Input id="dropout" {...num(brief.dropout, (v) => onChange({ ...brief, dropout: v }))} /></Field>
        </div>
        <div className="flex items-center justify-between gap-3">
          <p className="text-xs text-muted-foreground">Takes about a minute: precedent search, calculator, section drafting and a full self-check.</p>
          <Button type="submit" disabled={busy}>
            {busy && <Loader2 className="animate-spin" aria-hidden />} Generate draft
          </Button>
        </div>
      </form>
    </Section>
  );
}

function Field({ label, children, className }: { label: string; children: React.ReactElement<{ id?: string }>; className?: string }) {
  return (
    <div className={cn("space-y-1.5", className)}>
      <Label htmlFor={children.props.id}>{label}</Label>
      {children}
    </div>
  );
}

function DraftProgress({ events, failed }: { events: Partial<Record<DraftStep, DraftProgressEvent>>; failed: boolean }) {
  const running = DRAFT_STEPS.find((s) => !events[s]);
  return (
    <Section title="Drafting">
      <ol className="space-y-1.5" aria-live="polite">
        {DRAFT_STEPS.map((step) => {
          const e = events[step];
          return (
            <li key={step} className="flex items-center gap-2 text-sm">
              {e ? <CircleCheck className="size-4 text-status-present" aria-hidden />
                : step === running && !failed ? <Loader2 className="size-4 animate-spin text-primary" aria-hidden />
                : <span className="size-4 rounded-full border" aria-hidden />}
              <span className={cn(!e && "text-muted-foreground")}>{DRAFT_STEP_LABEL[step]}</span>
              {e?.message && <span className="text-xs text-muted-foreground">· {e.message}</span>}
            </li>
          );
        })}
      </ol>
    </Section>
  );
}

function DraftResult({ draft }: { draft: Draft }) {
  const s = draft.sample_size;
  const issues = [...draft.self_check.issues]
    .filter((i) => i.severity !== "advisory")
    .sort((a, b) => SEVERITY_META[a.severity].rank - SEVERITY_META[b.severity].rank)
    .slice(0, 15);
  return (
    <>
      <Section
        title="Draft"
        actions={USE_MOCKS ? undefined : (
          <div className="flex gap-2">
            {(["docx", "usdm"] as const).map((f) => (
              <Button key={f} asChild variant="outline" size="sm">
                <a href={draftExportUrl(draft.draft_id, f) ?? "#"}><Download aria-hidden /> {f === "docx" ? "M11 .docx" : "USDM JSON"}</a>
              </Button>
            ))}
          </div>
        )}
      >
        <StatGrid className="lg:grid-cols-4">
          <Stat label="Total sample size" value={s.n_total} hint={`${s.n_per_arm} per arm`} />
          <Stat label="Method" value={<span className="text-sm">{s.method}</span>} />
          <Stat label="Inputs" value={<span className="text-sm">α {s.inputs.alpha} · power {s.inputs.power} · dropout {s.inputs.dropout}</span>} />
          <Stat label="Effect" value={<span className="text-sm">{s.inputs.control} → {s.inputs.treatment}</span>} />
        </StatGrid>
        <div className="mt-6 space-y-6">
          {draft.sections.map((sec) => (
            <article key={sec.m11_id}>
              <h3 className="text-sm font-semibold"><span className="font-mono text-muted-foreground">{sec.m11_id}</span> {sec.title}</h3>
              <div className="mt-1 text-sm leading-relaxed whitespace-pre-wrap">{sec.markdown.replace(/^#+\s*/gm, "")}</div>
              {sec.citations.length > 0 && (
                <p className="mt-1 flex flex-wrap gap-x-2 text-xs text-muted-foreground">
                  Precedent: {sec.citations.map((c) => <NctLink key={c} nctId={c} />)}
                </p>
              )}
            </article>
          ))}
        </div>
      </Section>

      <Section title="Self-check" description="The draft was run through the same checks as an uploaded protocol.">
        <ScoreCard score={draft.self_check.score} />
        <ul className="mt-4 divide-y">
          {issues.map((i) => (
            <li key={i.id} className="flex items-start justify-between gap-2 py-2 text-sm">
              <span>{i.title}<span className="block text-xs text-muted-foreground">{i.fix?.suggestion ?? i.why.explanation}</span></span>
              <SeverityBadge severity={i.severity} />
            </li>
          ))}
        </ul>
        {draft.self_check.issues.length > issues.length && (
          <p className="mt-2 text-xs text-muted-foreground">
            Showing the {issues.length} most severe of {draft.self_check.issues.length} findings.{" "}
            <Link href="/evidence" className="text-primary hover:underline">How checks are measured</Link>
          </p>
        )}
      </Section>

      <PrecedentSection precedent={draft.precedent} />
    </>
  );
}
