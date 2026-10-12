"use client";

import { ChevronRight, FileQuestion } from "lucide-react";
import Link from "next/link";
import type { ReactNode } from "react";

import { EmptyState, ErrorState } from "@/components/common/states";
import { Skeleton } from "@/components/ui/skeleton";
import { ApiError } from "@/lib/api";
import { protocolName } from "@/lib/presentation";
import { useProtocols, useRun } from "@/lib/queries";
import type { Run } from "@/lib/types";

import { RunNav } from "./run-nav";

/** Loads a run and frames a run sub-page with the protocol title and the run navigation. */
export function RunShell({
  runId,
  active,
  children,
}: {
  runId: string;
  active: "burden" | "trace";
  children: (run: Run) => ReactNode;
}) {
  const run = useRun(runId);
  const protocols = useProtocols();

  if (run.isPending) {
    return (
      <div className="mx-auto max-w-6xl space-y-4 p-6" aria-busy="true">
        <Skeleton className="h-6 w-2/3" />
        <Skeleton className="h-40 w-full" />
        <Skeleton className="h-64 w-full" />
      </div>
    );
  }
  if (run.isError) {
    const notFound = run.error instanceof ApiError && run.error.status === 404;
    return (
      <div className="mx-auto max-w-xl p-6">
        {notFound ? (
          <div className="rounded-lg border bg-card">
            <EmptyState icon={FileQuestion} title={`Run ${runId} was not found`}>
              <Link href="/protocol" className="font-medium text-primary hover:underline">Back to protocols</Link>
            </EmptyState>
          </div>
        ) : (
          <ErrorState error={run.error} onRetry={() => void run.refetch()} />
        )}
      </div>
    );
  }

  const protocol = protocols.data?.items.find((p) => p.protocol_id === run.data.protocol_id);
  return (
    <div className="flex flex-col">
      <div className="border-b bg-card px-4 py-3">
        <nav aria-label="Breadcrumb" className="flex items-center gap-1 text-xs text-muted-foreground">
          <Link href="/protocol" className="hover:text-foreground hover:underline">Protocols</Link>
          <ChevronRight className="size-3" aria-hidden />
          <span className="font-mono">{protocol?.nct_id ?? run.data.protocol_id}</span>
        </nav>
        <h1 className="mt-1 truncate text-base font-semibold">{protocolName(protocol, run.data.protocol_id)}</h1>
      </div>
      <RunNav runId={runId} protocolId={run.data.protocol_id} active={active} />
      <div className="mx-auto w-full max-w-6xl space-y-5 px-4 py-5 md:px-6">
        {run.data.status === "complete" ? (
          children(run.data)
        ) : (
          <EmptyState icon={FileQuestion} title="This review has not finished yet">
            <Link href={`/runs/${runId}`} className="font-medium text-primary hover:underline">Open the review</Link>
          </EmptyState>
        )}
      </div>
    </div>
  );
}
