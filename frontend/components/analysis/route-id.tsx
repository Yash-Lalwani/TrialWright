"use client";

import { useParams } from "next/navigation";
import type { ReactNode } from "react";

/**
 * Reads the [id] route segment on the client. Awaiting `params` in a server page left the
 * dynamic hole of the partial prerender unresolved for many seconds; useParams is immediate.
 */
export function RouteId({ children }: { children: (id: string) => ReactNode }) {
  const { id } = useParams<{ id: string }>();
  return <>{children(id)}</>;
}
