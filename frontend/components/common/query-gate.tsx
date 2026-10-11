import type { UseQueryResult } from "@tanstack/react-query";
import { Hourglass, SearchX } from "lucide-react";
import type { ReactNode } from "react";

import { ApiError } from "@/lib/api";

import { ErrorState } from "./states";
import { Skeleton } from "@/components/ui/skeleton";

/**
 * Renders a query's loading, "not available yet" and error states so pages only write the happy path.
 * B's endpoints answer 409 when the Protocol Graph is not built and 404 when there is no peer set or
 * benchmark; both are expected situations, not failures, and carry a message worth showing.
 */
export function QueryGate<T>({
  query,
  skeleton = <Skeleton className="h-40 w-full" />,
  children,
}: {
  query: UseQueryResult<T>;
  skeleton?: ReactNode;
  children: (data: T) => ReactNode;
}) {
  if (query.isPending) return <div aria-busy="true">{skeleton}</div>;
  if (query.isError) {
    const error = query.error;
    if (error instanceof ApiError && (error.status === 404 || error.status === 409)) {
      const Icon = error.status === 409 ? Hourglass : SearchX;
      return (
        <div role="status" data-unavailable={error.status} className="flex items-start gap-3 rounded-lg border bg-muted/40 p-4">
          <Icon className="mt-0.5 size-4 shrink-0 text-muted-foreground" aria-hidden />
          <div className="text-sm">
            <p className="font-medium">{error.status === 409 ? "Not ready yet" : "Not available for this protocol"}</p>
            <p className="mt-0.5 text-muted-foreground">{error.message}</p>
          </div>
        </div>
      );
    }
    return <ErrorState error={error} onRetry={() => void query.refetch()} />;
  }
  return <>{children(query.data)}</>;
}
