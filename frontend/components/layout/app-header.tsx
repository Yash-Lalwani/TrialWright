"use client";

import { Database, FileCheck2, PlugZap, Unplug } from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { Suspense } from "react";

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
  return (
    <header className="flex h-13 shrink-0 items-center gap-3 bg-brand px-3 text-brand-foreground sm:gap-6 sm:px-5">
      <Link
        href="/"
        className="flex shrink-0 items-center gap-2.5 rounded-sm font-semibold tracking-tight whitespace-nowrap focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-white"
      >
        <span className="flex size-7 items-center justify-center rounded-md bg-white text-brand">
          <FileCheck2 className="size-4" aria-hidden />
        </span>
        <span className="hidden text-[15px] min-[400px]:inline">Pre-Flight</span>
        <span className="hidden border-l border-white/20 pl-2.5 text-[13px] font-normal text-brand-muted md:inline">
          Protocol review
        </span>
      </Link>

      {/* usePathname is runtime data; Suspense keeps the header in the static shell (cacheComponents). */}
      <Suspense fallback={<NavLinks pathname={null} />}>
        <ActiveNavLinks />
      </Suspense>

      <div className="ml-auto">
        <DataSourceIndicator />
      </div>
    </header>
  );
}

function ActiveNavLinks() {
  return <NavLinks pathname={usePathname()} />;
}

function NavLinks({ pathname }: { pathname: string | null }) {
  return (
    <nav aria-label="Main" className="flex h-full items-stretch gap-0.5 sm:gap-1">
      {NAV.map((item) => {
        const active = pathname !== null && item.match(pathname);
        return (
          <Link
            key={item.href}
            href={item.href}
            aria-current={active ? "page" : undefined}
            className={cn(
              "relative flex items-center px-2 text-sm font-medium text-brand-muted transition-colors duration-150 hover:text-white sm:px-3",
              "focus-visible:outline-2 focus-visible:-outline-offset-4 focus-visible:outline-white",
              "after:absolute after:inset-x-2 after:bottom-0 after:h-[3px] after:rounded-t-full",
              active && "text-white after:bg-white",
            )}
          >
            {item.label}
          </Link>
        );
      })}
    </nav>
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
            className="inline-flex items-center gap-1.5 rounded-md border border-transparent bg-sev-minor-bg px-2 py-1 text-xs font-medium text-sev-minor focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-white"
          >
            <Database className="size-3.5" aria-hidden />
            <span className="sr-only sm:not-sr-only">Mock data</span>
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
        ok
          ? "border-transparent bg-status-present-bg text-status-present"
          : "border-transparent bg-sev-critical-bg text-sev-critical",
      )}
      title={API_URL}
    >
      <Icon className="size-3.5" aria-hidden />
      {health.isPending ? "Connecting…" : ok ? `API ${health.data.llm_mode}` : "API unreachable"}
    </span>
  );
}
