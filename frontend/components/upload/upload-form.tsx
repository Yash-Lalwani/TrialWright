"use client";

import { useQueryClient } from "@tanstack/react-query";
import { ArrowRight, FileText, FileUp, Info, Loader2, Lock, ScanSearch, X } from "lucide-react";
import { useRouter } from "next/navigation";
import { useEffect, useId, useRef, useState } from "react";

import { RunProgress } from "@/components/common/run-progress";
import { errorMessage } from "@/components/common/states";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { createRun, subscribeRunEvents, uploadProtocol, USE_MOCKS } from "@/lib/api";
import { keys } from "@/lib/queries";
import type { ProgressEvent, RunMode, RunStep } from "@/lib/types";
import { cn } from "@/lib/utils";

const MAX_BYTES = 100 * 1024 * 1024;
const NCT_PATTERN = /^NCT\d{8}$/;

type Phase =
  | { kind: "idle" }
  | { kind: "uploading" }
  | { kind: "starting" }
  | { kind: "running"; runId: string }
  | { kind: "opening"; runId: string }
  | { kind: "error"; message: string; runId?: string };

function validateFile(file: File): string | null {
  const isPdf = file.type === "application/pdf" || file.name.toLowerCase().endsWith(".pdf");
  if (!isPdf) return `"${file.name}" is not a PDF. Upload the protocol as a .pdf file.`;
  if (file.size === 0) return `"${file.name}" is empty.`;
  if (file.size > MAX_BYTES) return `"${file.name}" is ${formatBytes(file.size)}. The limit is 100 MB.`;
  return null;
}

function formatBytes(bytes: number) {
  if (bytes < 1024 * 1024) return `${Math.max(1, Math.round(bytes / 1024))} KB`;
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
}

const MODES: { value: RunMode; title: string; body: string; icon: typeof Lock }[] = [
  {
    value: "full",
    title: "Full review",
    body: "Rule checks plus four AI reviewers. Every AI finding is verified against the quoted text.",
    icon: ScanSearch,
  },
  {
    value: "rules_only",
    title: "Confidential (rules only)",
    body: "The language model is disabled. Only rule checks, burden and peer comparison run.",
    icon: Lock,
  },
];

export function UploadForm() {
  const router = useRouter();
  const queryClient = useQueryClient();
  const ids = { file: useId(), nct: useId(), version: useId() };

  const [file, setFile] = useState<File | null>(null);
  const [fileError, setFileError] = useState<string | null>(null);
  const [dragging, setDragging] = useState(false);
  const [nct, setNct] = useState("");
  const [nctError, setNctError] = useState<string | null>(null);
  const [version, setVersion] = useState("v1");
  const [mode, setMode] = useState<RunMode>("full");
  const [phase, setPhase] = useState<Phase>({ kind: "idle" });
  const [events, setEvents] = useState<Partial<Record<RunStep, ProgressEvent>>>({});
  const unsubscribe = useRef<(() => void) | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => () => unsubscribe.current?.(), []);

  const busy = phase.kind === "uploading" || phase.kind === "starting" || phase.kind === "running" || phase.kind === "opening";

  const pick = (picked: File | undefined) => {
    if (!picked) return;
    const error = validateFile(picked);
    setFileError(error);
    setFile(error ? null : picked);
  };

  const checkNct = (value: string) => {
    const v = value.trim().toUpperCase();
    const error = v && !NCT_PATTERN.test(v) ? "Use the format NCT followed by 8 digits, for example NCT01234567." : null;
    setNctError(error);
    return { value: v, error };
  };

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (busy) return;
    const nctCheck = checkNct(nct);
    if (!file) setFileError("Choose a protocol PDF to review.");
    if (!file || nctCheck.error) return;

    setEvents({});
    try {
      setPhase({ kind: "uploading" });
      const protocol = await uploadProtocol(file, nctCheck.value || undefined);
      setPhase({ kind: "starting" });
      const { run_id } = await createRun(protocol.protocol_id, { mode, version_label: version.trim() || "v1" });
      void queryClient.invalidateQueries({ queryKey: keys.protocols });
      setPhase({ kind: "running", runId: run_id });
      unsubscribe.current = subscribeRunEvents(run_id, {
        onProgress: (event) => setEvents((prev) => ({ ...prev, [event.step]: event })),
        onComplete: (completedId) => {
          setPhase({ kind: "opening", runId: completedId });
          void queryClient.invalidateQueries({ queryKey: keys.protocols });
          router.push(`/runs/${completedId}`);
        },
        onError: (message) => setPhase({ kind: "error", message, runId: run_id }),
      });
    } catch (error) {
      setPhase({ kind: "error", message: errorMessage(error) });
    }
  };

  const reset = () => {
    unsubscribe.current?.();
    setPhase({ kind: "idle" });
    setEvents({});
  };

  const showProgress = phase.kind === "running" || phase.kind === "opening" || (phase.kind === "error" && phase.runId);

  const status =
    phase.kind === "uploading"
      ? "Uploading the protocol…"
      : phase.kind === "starting"
        ? "Starting the review…"
        : phase.kind === "running"
          ? "Reviewing. The workspace opens when the checks finish."
          : phase.kind === "opening"
            ? "Opening the review…"
            : null;

  return (
    <section aria-labelledby="upload-heading" className="rounded-lg border bg-card">
      <header className="border-b px-5 py-3.5">
        <h2 id="upload-heading" className="text-sm font-semibold">
          New review
        </h2>
        <p className="mt-0.5 text-[13px] text-muted-foreground">
          Upload a protocol PDF and choose how it is checked. Findings open next to the document, linked to the exact text.
        </p>
      </header>

      <form onSubmit={submit} noValidate>
        <div className="grid gap-x-6 gap-y-5 p-5 lg:grid-cols-[minmax(0,5fr)_minmax(0,7fr)]">
          {/* File */}
          <div className="flex flex-col gap-1.5">
            <div className="flex items-baseline justify-between gap-2">
              <Label htmlFor={ids.file}>Protocol PDF</Label>
              <span className="text-xs text-muted-foreground">One file, up to 100 MB</span>
            </div>
            <input
              ref={inputRef}
              id={ids.file}
              type="file"
              accept="application/pdf,.pdf"
              className="peer sr-only"
              disabled={busy}
              aria-invalid={!!fileError}
              aria-describedby={fileError ? `${ids.file}-error` : undefined}
              onChange={(e) => pick(e.target.files?.[0])}
            />
            {file ? (
              <div className="flex flex-1 items-center gap-3 rounded-md border bg-background px-3 py-3">
                <span className="flex size-9 shrink-0 items-center justify-center rounded-md bg-accent text-primary">
                  <FileText className="size-5" aria-hidden />
                </span>
                <div className="min-w-0 flex-1">
                  <p className="truncate text-sm font-medium">{file.name}</p>
                  <p className="text-xs text-muted-foreground tabular">{formatBytes(file.size)} · PDF</p>
                </div>
                <Button
                  type="button"
                  variant="ghost"
                  size="icon-sm"
                  aria-label="Remove file"
                  disabled={busy}
                  onClick={() => {
                    setFile(null);
                    if (inputRef.current) inputRef.current.value = "";
                  }}
                >
                  <X />
                </Button>
              </div>
            ) : (
              <label
                htmlFor={ids.file}
                onDragOver={(e) => {
                  e.preventDefault();
                  setDragging(true);
                }}
                onDragLeave={() => setDragging(false)}
                onDrop={(e) => {
                  e.preventDefault();
                  setDragging(false);
                  pick(e.dataTransfer.files[0]);
                }}
                className={cn(
                  "flex min-h-40 flex-1 cursor-pointer flex-col items-center justify-center gap-1.5 rounded-md border border-dashed px-6 py-6 text-center transition-colors duration-150 peer-focus-visible:border-ring peer-focus-visible:ring-3 peer-focus-visible:ring-ring/30",
                  dragging ? "border-primary bg-accent" : "border-input bg-muted/40 hover:border-primary/60 hover:bg-accent/50",
                  fileError && "border-sev-critical",
                )}
              >
                <FileUp className="mb-1 size-6 text-primary" aria-hidden />
                <span className="text-sm">
                  <span className="font-medium text-primary underline-offset-2 hover:underline">Choose a PDF</span> or drag it here
                </span>
              </label>
            )}
            {fileError && (
              <p id={`${ids.file}-error`} role="alert" className="text-xs text-sev-critical">
                {fileError}
              </p>
            )}
          </div>

          {/* Details and mode */}
          <div className="flex flex-col gap-5">
            <div className="grid grid-cols-[minmax(0,1fr)_7rem] gap-x-3 gap-y-1.5">
              <Label htmlFor={ids.nct}>
                NCT identifier <span className="font-normal text-muted-foreground">(optional)</span>
              </Label>
              <Label htmlFor={ids.version}>Version</Label>
              <Input
                id={ids.nct}
                value={nct}
                placeholder="NCT01234567"
                autoComplete="off"
                spellCheck={false}
                disabled={busy}
                className="font-mono uppercase placeholder:normal-case"
                aria-invalid={!!nctError}
                aria-describedby={`${ids.nct}-hint`}
                onChange={(e) => {
                  setNct(e.target.value);
                  if (nctError) checkNct(e.target.value);
                }}
                onBlur={(e) => checkNct(e.target.value)}
              />
              <Input id={ids.version} value={version} disabled={busy} onChange={(e) => setVersion(e.target.value)} />
              <p id={`${ids.nct}-hint`} className={cn("col-span-2 text-xs", nctError ? "text-sev-critical" : "text-muted-foreground")}>
                {nctError ?? "Adds a comparison with the ClinicalTrials.gov registry record."}
              </p>
            </div>

            <fieldset disabled={busy}>
              <legend className="mb-1.5 text-sm font-medium">Review mode</legend>
              <div className="grid gap-2 sm:grid-cols-2">
                {MODES.map((m) => {
                  const Icon = m.icon;
                  const checked = mode === m.value;
                  return (
                    <label
                      key={m.value}
                      className={cn(
                        "flex cursor-pointer gap-2.5 rounded-md border p-3 transition-colors duration-150 focus-within:ring-3 focus-within:ring-ring/30 has-disabled:cursor-not-allowed has-disabled:opacity-60",
                        checked ? "border-primary bg-accent/70" : "bg-card hover:border-primary/40 hover:bg-muted/50",
                      )}
                    >
                      <input
                        type="radio"
                        name="mode"
                        value={m.value}
                        checked={checked}
                        onChange={() => setMode(m.value)}
                        className="mt-0.5 size-4 shrink-0"
                      />
                      <span className="min-w-0">
                        <span className="flex items-center gap-1.5 text-sm font-medium">
                          <Icon className={cn("size-3.5", checked ? "text-primary" : "text-muted-foreground")} aria-hidden />
                          {m.title}
                        </span>
                        <span className="mt-0.5 block text-xs leading-relaxed text-muted-foreground">{m.body}</span>
                      </span>
                    </label>
                  );
                })}
              </div>
            </fieldset>
          </div>
        </div>

        <div className="flex flex-wrap items-center justify-between gap-3 border-t bg-muted/40 px-5 py-3">
          <p className="flex min-w-0 flex-1 items-start gap-1.5 text-xs text-muted-foreground" aria-live="polite">
            {status ? (
              <>
                <Loader2 className="mt-px size-3.5 shrink-0 animate-spin text-primary motion-reduce:animate-none" aria-hidden />
                <span>{status}</span>
              </>
            ) : USE_MOCKS ? (
              <>
                <Info className="mt-px size-3.5 shrink-0" aria-hidden />
                <span>Mock mode: your file stays in this browser, and the synthetic sample protocol is reviewed instead.</span>
              </>
            ) : (
              <span>The review opens automatically when the checks finish.</span>
            )}
          </p>
          <Button type="submit" size="lg" disabled={busy} className="min-w-36 px-4">
            {busy ? <Loader2 className="animate-spin motion-reduce:animate-none" aria-hidden /> : null}
            {busy ? "Reviewing…" : "Start review"}
            {!busy && <ArrowRight aria-hidden />}
          </Button>
        </div>
      </form>

      {(showProgress || phase.kind === "error") && (
        <div className="space-y-3 border-t px-5 py-4">
          {showProgress && <RunProgress events={events} failed={phase.kind === "error"} />}
          {phase.kind === "error" && (
            <div role="alert" className="flex flex-wrap items-center justify-between gap-2 rounded-md border border-sev-critical-border bg-sev-critical-bg px-3 py-2 text-sm">
              <span className="text-sev-critical">{phase.message}</span>
              <Button type="button" variant="outline" size="sm" onClick={reset}>
                Dismiss
              </Button>
            </div>
          )}
        </div>
      )}
    </section>
  );
}
