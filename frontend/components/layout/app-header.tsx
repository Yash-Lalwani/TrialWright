"use client";

import { Database, FileCheck2, PlugZap, Unplug } from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";

import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { API_URL, USE_MOCKS } from "@/lib/api";
import { useHealth } from "@/lib/queries";
import { cn } from "@/lib/utils";

const NAV = [
  { href: "/", label: "Protocols", match: (p: string) => p === "/" || p.startsWith("/runs") },
  { href: "/draft", label: "Draft", match: (p: string) => p.startsWith("/draft") },
  { href: "/evidence", label: "Evidence", match: (p: string) => p.startsWith("/evidence") },
];

export function AppHeader() {
  const pathname = usePathname();
  return (
    <header className="flex h-12 shrink-0 items-center gap-6 border-b bg-card px-4">
      <Link href="/" className="flex items-center gap-2 rounded-sm font-semibold tracking-tight text-foreground">
        <span className="flex size-7 items-center justify-center rounded-md bg-primary text-primary-foreground">
          <FileCheck2 className="size-4" aria-hidden />
        </span>
        <span>Pre-Flight</span>
        <span className="hidden text-[13px] font-normal text-muted-foreground md:inline">Protocol review</span>
      </Link>

      <nav aria-label="Main" className="flex h-full items-stretch gap-1">
        {NAV.map((item) => {
          const active = item.match(pathname);
          return (
            <Link
              key={item.href}
              href={item.href}
              aria-current={active ? "page" : undefined}
              className={cn(
                "relative flex items-center px-3 text-sm font-medium text-muted-foreground transition-colors hover:text-foreground",
                "after:absolute after:inset-x-2 after:bottom-0 after:h-0.5 after:rounded-full",
                active && "text-foreground after:bg-primary",
              )}
            >
              {item.label}
            </Link>
          );
        })}
      </nav>

      <div className="ml-auto">
        <DataSourceIndicator />
      </div>
    </header>
  );
}

/** Makes it impossible to mistake mock responses for a real analysis. */
function DataSourceIndicator() {
  const health = useHealth();
  if (USE_MOCKS) {
    return (
      <Tooltip>
        <TooltipTrigger asChild>
          <span
            tabIndex={0}
            className="inline-flex items-center gap-1.5 rounded-md border border-sev-minor-border bg-sev-minor-bg px-2 py-1 text-xs font-medium text-sev-minor"
          >
            <Database className="size-3.5" aria-hidden />
            Mock data
          </span>
        </TooltipTrigger>
        <TooltipContent side="bottom" className="max-w-64">
          Responses come from frontend/mocks and a synthetic sample protocol. Nothing is sent to a server and no
          result shown is a real analysis.
        </TooltipContent>
      </Tooltip>
    );
  }
  const ok = health.isSuccess;
  const Icon = ok ? PlugZap : Unplug;
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 rounded-md border px-2 py-1 text-xs font-medium",
        ok ? "border-status-present/30 text-status-present" : "border-sev-critical-border text-sev-critical",
      )}
      title={API_URL}
    >
      <Icon className="size-3.5" aria-hidden />
      {health.isPending ? "Connecting…" : ok ? `API ${health.data.llm_mode}` : "API unreachable"}
    </span>
  );
}
