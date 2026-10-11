"use client";

import { ChevronDown, Download, GitCompare, Gauge } from "lucide-react";
import Link from "next/link";
import { useEffect, useRef } from "react";

import { Button } from "@/components/ui/button";
import { exportUrl } from "@/lib/api";
import type { ExportFormat } from "@/lib/types";

const EXPORTS: { format: ExportFormat; label: string; hint: string }[] = [
  { format: "report_pdf", label: "Review report (PDF)", hint: "Issues, scores and decisions" },
  { format: "report_csv", label: "Issues (CSV)", hint: "One row per issue" },
  { format: "docx", label: "Protocol with fixes (.docx)", hint: "Accepted fixes applied" },
  { format: "usdm", label: "Protocol Graph (USDM JSON)", hint: "Machine-readable structure" },
];

/** Links from the review to the other run pages, and the four exports (4.7). */
export function RunActions({ runId, protocolId }: { runId: string; protocolId: string }) {
  const menu = useRef<HTMLDetailsElement>(null);

  // Close the menu on outside click or Escape, as a native <details> would not.
  useEffect(() => {
    const close = (e: Event) => {
      const el = menu.current;
      if (!el?.open) return;
      if (e instanceof KeyboardEvent ? e.key === "Escape" : !el.contains(e.target as Node)) el.open = false;
    };
    document.addEventListener("pointerdown", close);
    document.addEventListener("keydown", close);
    return () => {
      document.removeEventListener("pointerdown", close);
      document.removeEventListener("keydown", close);
    };
  }, []);

  const realExports = EXPORTS.map((e) => ({ ...e, url: exportUrl(runId, e.format) }));
  const available = realExports.some((e) => e.url);

  return (
    <div className="flex flex-wrap items-center gap-1.5">
      <Button asChild variant="outline" size="xs">
        <Link href={`/runs/${runId}/burden`}>
          <Gauge aria-hidden /> Burden and peers
        </Link>
      </Button>
      <Button asChild variant="outline" size="xs">
        <Link href={`/compare?protocol=${encodeURIComponent(protocolId)}&to=${encodeURIComponent(runId)}`}>
          <GitCompare aria-hidden /> Compare versions
        </Link>
      </Button>
      <details ref={menu} className="relative" data-export-menu>
        <summary className="inline-flex h-6 cursor-pointer list-none items-center gap-1 rounded-[min(var(--radius-md),10px)] border bg-background px-2 text-xs font-medium hover:bg-muted focus-visible:ring-3 focus-visible:ring-ring/50 focus-visible:outline-none [&::-webkit-details-marker]:hidden">
          <Download className="size-3" aria-hidden /> Export <ChevronDown className="size-3" aria-hidden />
        </summary>
        <div className="absolute right-0 z-30 mt-1 w-64 rounded-md border bg-card p-1 shadow-lg">
          {!available && (
            <p className="px-2 py-1.5 text-xs text-muted-foreground">
              Exports are produced by the backend. They are off while the app runs on mock data.
            </p>
          )}
          {realExports.map((e) =>
            e.url ? (
              <a key={e.format} href={e.url} download className="block rounded-sm px-2 py-1.5 text-sm hover:bg-muted focus-visible:ring-2 focus-visible:ring-ring/50 focus-visible:outline-none">
                {e.label}
                <span className="block text-xs text-muted-foreground">{e.hint}</span>
              </a>
            ) : (
              <span key={e.format} aria-disabled className="block cursor-not-allowed rounded-sm px-2 py-1.5 text-sm text-muted-foreground opacity-60">
                {e.label}
              </span>
            ),
          )}
        </div>
      </details>
    </div>
  );
}
