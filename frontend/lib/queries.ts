// TanStack Query hooks over lib/api.ts. Keys are shared so mutations can update caches.

"use client";

import { useQuery } from "@tanstack/react-query";

import * as api from "./api";

export const keys = {
  health: ["health"] as const,
  protocols: ["protocols"] as const,
  run: (runId: string) => ["run", runId] as const,
  issues: (runId: string) => ["issues", runId] as const,
  completeness: (runId: string) => ["completeness", runId] as const,
};

export const useHealth = () => useQuery({ queryKey: keys.health, queryFn: api.getHealth, retry: false });

export const useProtocols = () => useQuery({ queryKey: keys.protocols, queryFn: api.listProtocols });

export const useRun = (runId: string) => useQuery({ queryKey: keys.run(runId), queryFn: () => api.getRun(runId) });

/** All issues for a run; the workspace filters client-side so counts stay visible per filter. */
export const useIssues = (runId: string, enabled = true) =>
  useQuery({ queryKey: keys.issues(runId), queryFn: () => api.listIssues(runId), enabled });

export const useCompleteness = (runId: string, enabled = true) =>
  useQuery({ queryKey: keys.completeness(runId), queryFn: () => api.getCompleteness(runId), enabled });
