"use client";

import { Workspace } from "@/components/workspace/workspace";

import { BurdenView } from "./burden-view";
import { RouteId } from "./route-id";
import { RunShell } from "./run-shell";
import { TraceView } from "./trace-view";

export const ReviewPage = () => <RouteId>{(id) => <Workspace key={id} runId={id} />}</RouteId>;

export const BurdenPage = () => (
  <RouteId>{(id) => <RunShell key={id} runId={id} active="burden">{(run) => <BurdenView run={run} />}</RunShell>}</RouteId>
);

export const TracePage = () => (
  <RouteId>{(id) => <RunShell key={id} runId={id} active="trace">{(run) => <TraceView run={run} />}</RunShell>}</RouteId>
);
