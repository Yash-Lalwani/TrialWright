"use client";

import { useId, useState } from "react";

import { formatUsd } from "@/lib/presentation";
import { cn } from "@/lib/utils";

/** CONTRACTS 4.13 and EVALUATION §7. Inputs and sources are fixed by the plan; only the sliders are ours. */
const PRESETS = {
  phase2: { label: "Phase II", cost: 141_000 },
  phase3: { label: "Phase III", cost: 535_000 },
} as const;
type PresetKey = keyof typeof PRESETS;

const DELAY_MONTHS = 3;

export function RoiCalculator({ recall, recallIsMeasured }: { recall: number; recallIsMeasured: boolean }) {
  const [phase, setPhase] = useState<PresetKey>("phase3");
  const [pAmend, setPAmend] = useState(0.57);
  const [share, setShare] = useState(0.45);
  const [cost, setCost] = useState<number>(PRESETS.phase3.cost);
  const [catchRate, setCatchRate] = useState(recall);

  const avoidable = pAmend * share * cost;
  const avoided = avoidable * catchRate;
  const months = pAmend * share * DELAY_MONTHS * catchRate;

  const pick = (key: PresetKey) => {
    setPhase(key);
    setCost(PRESETS[key].cost);
  };
  const reset = () => {
    setPhase("phase3");
    setPAmend(0.57);
    setShare(0.45);
    setCost(PRESETS.phase3.cost);
    setCatchRate(recall);
  };

  return (
    <div className="grid gap-6 lg:grid-cols-[minmax(0,3fr)_minmax(0,2fr)]">
      <div className="space-y-4">
        <fieldset>
          <legend className="text-xs font-medium">Trial phase (sets cost per amendment)</legend>
          <div className="mt-1.5 inline-flex rounded-lg bg-muted p-[3px]" role="radiogroup" aria-label="Trial phase">
            {(Object.keys(PRESETS) as PresetKey[]).map((k) => (
              <button
                key={k}
                type="button"
                role="radio"
                aria-checked={phase === k}
                data-phase={k}
                onClick={() => pick(k)}
                className={cn(
                  "rounded-md px-3 py-1 text-sm font-medium text-muted-foreground transition-colors focus-visible:ring-2 focus-visible:ring-ring/50 focus-visible:outline-none",
                  phase === k && "bg-card text-foreground shadow-sm",
                )}
              >
                {PRESETS[k].label}
              </button>
            ))}
          </div>
        </fieldset>

        <Slider id="p_amend" label="Chance of a substantial amendment" value={pAmend} min={0.1} max={0.9} step={0.01} onChange={setPAmend} format={pct} />
        <Slider id="share" label="Share of amendments that were avoidable" value={share} min={0.33} max={0.6} step={0.01} onChange={setShare} format={pct} hint="Conservative end is one third" />
        <Slider id="cost" label="Direct cost per amendment" value={cost} min={50_000} max={800_000} step={1_000} onChange={setCost} format={formatUsd} />
        <Slider
          id="catch"
          label="Share Pre-Flight catches"
          value={catchRate}
          min={0.1}
          max={1}
          step={0.01}
          onChange={setCatchRate}
          format={pct}
          hint={recallIsMeasured ? `Starts at the measured recall, ${pct(recall)}` : `Starts at the placeholder recall, ${pct(recall)}. Not a measurement.`}
        />
        <button
          type="button"
          onClick={reset}
          className="rounded-sm text-xs font-medium text-primary underline-offset-2 hover:underline focus-visible:ring-2 focus-visible:ring-ring/50 focus-visible:outline-none"
        >
          Reset to the default values
        </button>

        <div className="rounded-md border bg-muted/30 p-3 text-xs leading-relaxed text-muted-foreground">
          <p className="font-medium text-foreground">Sources</p>
          <ul className="mt-1 list-disc space-y-0.5 pl-4">
            <li>Chance of amendment 0.57, share avoidable 0.45 and median direct cost per amendment ($141,000 Phase II, $535,000 Phase III): Getz et al., 2016.</li>
            <li>Conservative share avoidable, about one third: ERG, 2014.</li>
            <li>About 3 months of delay for trials with an amendment: Applied Clinical Trials.</li>
            <li>Catch rate: Pre-Flight recall from the benchmark above.</li>
          </ul>
          <p className="mt-2">Assumes one substantial amendment per amended protocol, which understates cost when there are several. This is an illustration, not a forecast for any specific trial.</p>
        </div>
      </div>

      <div className="space-y-3" aria-live="polite">
        <Result label="Avoidable amendment cost, per protocol" value={formatUsd(Math.round(avoidable))} id="roi-avoidable" />
        <Result label="Expected cost avoided with Pre-Flight" value={formatUsd(Math.round(avoided))} id="roi-avoided" strong />
        <Result label="Expected delay avoided" value={`${months.toFixed(2)} months (${Math.round(months * 30.4)} days)`} id="roi-months" />
        <p className="font-mono text-[11px] leading-relaxed text-muted-foreground">
          {pct(pAmend)} × {pct(share)} × {formatUsd(cost)} × {pct(catchRate)}
        </p>
      </div>
    </div>
  );
}

const pct = (v: number) => `${Math.round(v * 100)}%`;

function Result({ label, value, id, strong }: { label: string; value: string; id: string; strong?: boolean }) {
  return (
    <div className={cn("rounded-lg border px-4 py-3", strong ? "border-primary/30 bg-accent" : "bg-card")}>
      <p className="text-xs text-muted-foreground">{label}</p>
      <p id={id} className={cn("mt-0.5 font-semibold tabular", strong ? "text-3xl leading-9 text-primary" : "text-xl leading-7")}>
        {value}
      </p>
    </div>
  );
}

function Slider({
  id,
  label,
  value,
  min,
  max,
  step,
  onChange,
  format,
  hint,
}: {
  id: string;
  label: string;
  value: number;
  min: number;
  max: number;
  step: number;
  onChange: (v: number) => void;
  format: (v: number) => string;
  hint?: string;
}) {
  const uid = useId();
  return (
    <div>
      <div className="flex items-baseline justify-between gap-3">
        <label htmlFor={`${uid}-${id}`} className="text-sm font-medium">
          {label}
        </label>
        <output htmlFor={`${uid}-${id}`} className="text-sm font-semibold tabular">
          {format(value)}
        </output>
      </div>
      <input
        id={`${uid}-${id}`}
        data-roi={id}
        type="range"
        min={min}
        max={max}
        step={step}
        value={value}
        onChange={(e) => onChange(Number(e.target.value))}
        className="mt-1 w-full"
      />
      {hint && <p className="text-xs text-muted-foreground">{hint}</p>}
    </div>
  );
}
