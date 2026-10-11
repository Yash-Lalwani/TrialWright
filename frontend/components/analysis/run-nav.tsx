"use client";

import { Download } from "lucide-react";
import Link from "next/link";

import { Button } from "@/components/ui/button";
import { exportUrl, USE_MOCKS } from "@/lib/api";
import type { ExportFormat } from "@/lib/types";
import { cn } from "@/lib/utils";

const TABS = [
  { key: "review", label: "Review", href: (id: string) => `/runs/${id}` },
  { key: "burden", label: "Burden & peers", href: (id: string) => `/runs/${id}/burden` },
  { key: "trace", label: "Audit & trace", href: (id: string) => `/runs/${id}/trace` },
] as const;

const EXPORTS: { format: ExportFormat; label: string }[] = [
  { format: "report_pdf", label: "Issue report (PDF)" },
  { format: "report_csv", label: "Issues (CSV)" },
  { format: "docx", label: "M11 document (.docx)" },
  { format: "usdm", label: "USDM JSON" },
];

/** Links between the views of one run, plus the E4 exports. */
export function RunNav({ runId, protocolId, active }: { runId: string; protocolId: string; active: (typeof TABS)[number]["key"] }) {
  return (
    <div className="flex flex-wrap items-center justify-between gap-2 border-b bg-card px-4">
      <nav aria-label="Run views" className="flex items-stretch gap-1">
        {TABS.map((t) => (
          <Link
            key={t.key}
            href={t.href(runId)}
            aria-current={active === t.key ? "page" : undefined}
            className={cn(
              "relative px-2.5 py-2.5 text-sm font-medium text-muted-foreground transition-colors hover:text-foreground",
              "after:absolute after:inset-x-2 after:bottom-0 after:h-[2px] after:rounded-t-full",
              active === t.key && "text-foreground after:bg-primary",
            )}
          >
            {t.label}
          </Link>
        ))}
        <Link
          href={`/compare?protocol=${encodeURIComponent(protocolId)}&to=${encodeURIComponent(runId)}`}
          className="px-2.5 py-2.5 text-sm font-medium text-muted-foreground transition-colors hover:text-foreground"
        >
          Compare versions
        </Link>
      </nav>
      <ExportMenu runId={runId} />
    </div>
  );
}

function ExportMenu({ runId }: { runId: string }) {
  if (USE_MOCKS) {
    return <span className="py-2 text-xs text-muted-foreground">Exports need the live API</span>;
  }
  return (
    <details className="relative py-1.5">
      <summary className="list-none [&::-webkit-details-marker]:hidden">
        <Button asChild variant="outline" size="sm">
          <span>
            <Download aria-hidden /> Export
          </span>
        </Button>
      </summary>
      <ul className="absolute right-0 z-20 mt-1 w-56 rounded-md border bg-popover p-1 shadow-md">
        {EXPORTS.map((e) => (
          <li key={e.format}>
            <a href={exportUrl(runId, e.format) ?? "#"} className="block rounded px-2 py-1.5 text-sm hover:bg-muted">
              {e.label}
            </a>
          </li>
        ))}
      </ul>
    </details>
  );
}
