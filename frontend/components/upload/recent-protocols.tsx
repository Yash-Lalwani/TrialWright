"use client";

import { ArrowRight, CircleX, FileText, Loader2 } from "lucide-react";
import Link from "next/link";

import { EmptyState, ErrorState } from "@/components/common/states";
import { Skeleton } from "@/components/ui/skeleton";
import { formatDateTime, formatPhase, protocolName } from "@/lib/presentation";
import { useProtocols } from "@/lib/queries";
import type { LatestRun } from "@/lib/types";
import { cn } from "@/lib/utils";

export function RecentProtocols() {
  const { data, isPending, isError, error, refetch } = useProtocols();

  return (
    <section aria-labelledby="recent-heading" className="rounded-lg border bg-card">
      <div className="flex items-center justify-between border-b px-5 py-3">
        <h2 id="recent-heading" className="text-sm font-semibold">
          Recent protocols
        </h2>
        {data && <span className="text-xs text-muted-foreground tabular">{data.items.length} total</span>}
      </div>

      {isPending && (
        <div className="space-y-2 p-4" aria-busy="true" aria-label="Loading protocols">
          {[0, 1, 2].map((i) => (
            <Skeleton key={i} className="h-10 w-full" />
          ))}
        </div>
      )}

      {isError && <ErrorState className="m-4" error={error} onRetry={() => void refetch()} />}

      {data && data.items.length === 0 && (
        <EmptyState icon={FileText} title="No protocols yet">
          Upload a protocol PDF above to start the first review.
        </EmptyState>
      )}

      {data && data.items.length > 0 && (
        <div className="relative overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b text-left text-xs text-muted-foreground">
                <th scope="col" className="px-5 py-2 font-medium">Protocol</th>
                <th scope="col" className="px-3 py-2 font-medium">Registry</th>
                <th scope="col" className="px-3 py-2 font-medium">Uploaded</th>
                <th scope="col" className="px-3 py-2 text-right font-medium">Score</th>
                <th scope="col" className="px-5 py-2 font-medium"><span className="sr-only">Action</span></th>
              </tr>
            </thead>
            <tbody>
              {data.items.map((p) => (
                <tr key={p.protocol_id} className="border-b transition-colors duration-150 last:border-0 hover:bg-muted/50">
                  <td className="max-w-md px-5 py-2.5">
                    <div className="truncate font-medium" title={protocolName(p, p.protocol_id)}>{protocolName(p, p.protocol_id)}</div>
                    <div className="truncate text-xs text-muted-foreground">
                      {p.filename}
                      {p.pages != null ? ` · ${p.pages} pages` : ""} · {formatPhase(p.phase)}
                      {p.condition ? ` · ${p.condition}` : ""}
                    </div>
                  </td>
                  <td className="px-3 py-2.5 font-mono text-xs whitespace-nowrap text-muted-foreground">
                    {p.nct_id ?? "Not registered"}
                  </td>
                  <td className="px-3 py-2.5 text-xs whitespace-nowrap text-muted-foreground tabular">
                    {formatDateTime(p.uploaded_at)}
                  </td>
                  <td className="px-3 py-2.5 text-right">
                    <LatestScore run={p.latest_run} />
                  </td>
                  <td className="px-5 py-2.5 text-right">
                    {p.latest_run ? (
                      <Link
                        href={`/runs/${p.latest_run.run_id}`}
                        className="inline-flex items-center gap-1 rounded-sm text-sm font-medium whitespace-nowrap text-primary hover:underline"
                      >
                        {p.latest_run.status === "complete" ? "Open review" : "View run"}
                        <ArrowRight className="size-3.5" aria-hidden />
                      </Link>
                    ) : null}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}

function LatestScore({ run }: { run: LatestRun | null }) {
  if (!run) return <span className="text-xs text-muted-foreground">Not reviewed</span>;
  if (run.status === "queued" || run.status === "running") {
    return (
      <span className="inline-flex items-center gap-1 text-xs text-muted-foreground">
        <Loader2 className="size-3 animate-spin motion-reduce:animate-none" aria-hidden />
        Running
      </span>
    );
  }
  if (run.status === "failed" || run.score == null) {
    return (
      <span className="inline-flex items-center gap-1 text-xs font-medium text-sev-critical">
        <CircleX className="size-3.5" aria-hidden />
        Failed
      </span>
    );
  }
  return (
    <span className="inline-flex items-center justify-end gap-2">
      <span className="hidden h-1.5 w-14 overflow-hidden rounded-full bg-muted sm:block" aria-hidden>
        <span className={cn("block h-full rounded-full bg-primary")} style={{ width: `${run.score}%` }} />
      </span>
      <span className="w-7 text-right font-semibold tabular">{run.score}</span>
    </span>
  );
}
