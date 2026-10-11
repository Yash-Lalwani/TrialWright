import { ShieldAlert } from "lucide-react";

/** F4: required on every page. The wording is fixed by the PRD; do not edit it. */
export const DISCLAIMER = "Pre-Flight assists protocol authors. It does not approve protocols.";

export function DisclaimerBanner() {
  return (
    <div
      role="note"
      aria-label="Disclaimer"
      className="flex shrink-0 items-center gap-2 border-b border-primary/15 bg-accent px-4 py-1.5 text-[13px] text-accent-foreground sm:px-5"
    >
      <ShieldAlert className="size-3.5 shrink-0 text-primary" aria-hidden />
      <span>{DISCLAIMER}</span>
    </div>
  );
}
