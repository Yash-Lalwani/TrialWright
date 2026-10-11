"use client";

import { ArrowRight, Loader2 } from "lucide-react";
import { useId, useState } from "react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import type { Brief } from "@/lib/types";

export const EXAMPLE_BRIEF: Brief = {
  condition: "Non-small cell lung cancer",
  phase: "PHASE2",
  intervention: "Drug X 350 mg IV Q3W",
  comparator: "Docetaxel",
  primary_question: "Does Drug X improve ORR vs docetaxel?",
  population: "Adults with previously treated advanced NSCLC",
  duration_weeks: 52,
  alpha: 0.05,
  power: 0.8,
  expected_effect: { type: "proportions", control: 0.12, treatment: 0.27 },
  dropout: 0.1,
};

const PHASES = [
  ["PHASE1", "Phase 1"],
  ["PHASE1_PHASE2", "Phase 1/2"],
  ["PHASE2", "Phase 2"],
  ["PHASE2_PHASE3", "Phase 2/3"],
  ["PHASE3", "Phase 3"],
] as const;

type Form = Record<"condition" | "phase" | "intervention" | "comparator" | "primary_question" | "population", string> &
  Record<"duration_weeks" | "alpha" | "power" | "control" | "treatment" | "dropout", string>;

const toForm = (b: Brief): Form => ({
  condition: b.condition,
  phase: b.phase,
  intervention: b.intervention,
  comparator: b.comparator,
  primary_question: b.primary_question,
  population: b.population,
  duration_weeks: String(b.duration_weeks),
  alpha: String(b.alpha),
  power: String(b.power),
  control: String(b.expected_effect.control),
  treatment: String(b.expected_effect.treatment),
  dropout: String(b.dropout),
});

type Errors = Partial<Record<keyof Form, string>>;

function validate(f: Form): Errors {
  const e: Errors = {};
  for (const k of ["condition", "intervention", "comparator", "primary_question", "population"] as const) {
    if (!f[k].trim()) e[k] = "Required";
  }
  const num = (k: keyof Form, lo: number, hi: number, msg: string) => {
    const v = Number(f[k]);
    if (f[k].trim() === "" || !Number.isFinite(v) || v < lo || v > hi) e[k] = msg;
  };
  num("duration_weeks", 1, 520, "Enter 1 to 520 weeks");
  num("alpha", 0.001, 0.2, "Enter 0.001 to 0.2");
  num("power", 0.5, 0.99, "Enter 0.5 to 0.99");
  num("control", 0.001, 0.999, "Enter a rate between 0 and 1");
  num("treatment", 0.001, 0.999, "Enter a rate between 0 and 1");
  num("dropout", 0, 0.9, "Enter 0 to 0.9");
  if (!e.control && !e.treatment && Number(f.control) === Number(f.treatment)) {
    e.treatment = "Must differ from the control rate";
  }
  return e;
}

/** The 4.11 Brief as a form. Every field maps one-to-one onto the request body. */
export function BriefForm({ pending, onSubmit }: { pending: boolean; onSubmit: (brief: Brief) => void }) {
  const [form, setForm] = useState<Form>(() => toForm(EXAMPLE_BRIEF));
  const [errors, setErrors] = useState<Errors>({});
  const uid = useId();

  const set = (k: keyof Form) => (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) => {
    setForm((f) => ({ ...f, [k]: e.target.value }));
    setErrors((prev) => ({ ...prev, [k]: undefined }));
  };

  const submit = (e: React.FormEvent) => {
    e.preventDefault();
    const found = validate(form);
    setErrors(found);
    if (Object.keys(found).length) {
      const first = Object.keys(found)[0];
      document.getElementById(`${uid}-${first}`)?.focus();
      return;
    }
    onSubmit({
      condition: form.condition.trim(),
      phase: form.phase,
      intervention: form.intervention.trim(),
      comparator: form.comparator.trim(),
      primary_question: form.primary_question.trim(),
      population: form.population.trim(),
      duration_weeks: Number(form.duration_weeks),
      alpha: Number(form.alpha),
      power: Number(form.power),
      expected_effect: { type: "proportions", control: Number(form.control), treatment: Number(form.treatment) },
      dropout: Number(form.dropout),
    });
  };

  const field = (k: keyof Form, label: string, props: React.ComponentProps<"input"> = {}, hint?: string) => (
    <div className="space-y-1">
      <Label htmlFor={`${uid}-${k}`}>{label}</Label>
      <Input
        id={`${uid}-${k}`}
        value={form[k]}
        onChange={set(k)}
        aria-invalid={!!errors[k]}
        aria-describedby={errors[k] || hint ? `${uid}-${k}-msg` : undefined}
        disabled={pending}
        {...props}
      />
      {(errors[k] || hint) && (
        <p id={`${uid}-${k}-msg`} className={errors[k] ? "text-xs text-destructive" : "text-xs text-muted-foreground"}>
          {errors[k] ?? hint}
        </p>
      )}
    </div>
  );

  return (
    <form onSubmit={submit} noValidate className="rounded-lg border bg-card" aria-label="Design brief">
      <div className="grid gap-x-6 gap-y-4 p-4 md:grid-cols-2">
        <div className="space-y-4">
          <h2 className="text-sm font-semibold">Design</h2>
          {field("condition", "Condition")}
          <div className="space-y-1">
            <Label htmlFor={`${uid}-phase`}>Phase</Label>
            <select
              id={`${uid}-phase`}
              value={form.phase}
              onChange={set("phase")}
              disabled={pending}
              className="h-8 w-full rounded-lg border border-input bg-transparent px-2.5 text-sm focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50 focus-visible:outline-none"
            >
              {PHASES.map(([v, l]) => (
                <option key={v} value={v}>
                  {l}
                </option>
              ))}
            </select>
          </div>
          {field("intervention", "Intervention", {}, "Drug, dose, route and schedule")}
          {field("comparator", "Comparator")}
          {field("primary_question", "Primary question")}
          {field("population", "Population")}
        </div>

        <div className="space-y-4">
          <h2 className="text-sm font-semibold">Statistics</h2>
          <div className="grid grid-cols-2 gap-3">
            {field("duration_weeks", "Duration (weeks)", { inputMode: "numeric" })}
            {field("dropout", "Expected dropout", { inputMode: "decimal" }, "A fraction, 0.1 is 10%")}
            {field("alpha", "Significance level", { inputMode: "decimal" }, "Two-sided alpha")}
            {field("power", "Power", { inputMode: "decimal" })}
          </div>
          <fieldset className="rounded-md border p-3">
            <legend className="px-1 text-xs font-medium">Expected response rate</legend>
            <div className="grid grid-cols-2 gap-3">
              {field("control", "Control arm", { inputMode: "decimal" })}
              {field("treatment", "Treatment arm", { inputMode: "decimal" })}
            </div>
            <p className="mt-2 text-xs text-muted-foreground">Rates as fractions. Sample size uses a two-proportion comparison.</p>
          </fieldset>
        </div>
      </div>

      <div className="flex flex-wrap items-center justify-between gap-3 border-t bg-muted/30 px-4 py-3">
        <p className="text-xs text-muted-foreground">The draft is a starting point for authors. It is checked by the same rules as an uploaded protocol.</p>
        <Button type="submit" disabled={pending}>
          {pending ? <Loader2 className="animate-spin" aria-hidden /> : null}
          Generate draft <ArrowRight aria-hidden />
        </Button>
      </div>
    </form>
  );
}
