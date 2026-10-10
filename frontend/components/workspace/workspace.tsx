"use client";

import { useQueryClient } from "@tanstack/react-query";
import { ChevronRight, CircleX, FileQuestion, Lock, SearchX } from "lucide-react";
import dynamic from "next/dynamic";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { RunProgress } from "@/components/common/run-progress";
import { EmptyState, ErrorState } from "@/components/common/states";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { ApiError, protocolPdfUrl, subscribeRunEvents } from "@/lib/api";
import { formatDateTime, formatDuration, formatUsd, MODE_LABEL, SEVERITY_META } from "@/lib/presentation";
import { keys, useIssues, useProtocols, useRun } from "@/lib/queries";
import type { Issue, ProgressEvent, ProtocolListItem, Run, RunStep, Where } from "@/lib/types";

import { CompletenessPanel } from "./completeness-panel";
import { applyFilters, ClearFilters, EMPTY_FILTERS, IssueFilters, isFiltered, type IssueFilterState } from "./issue-filters";
import { IssueList } from "./issue-list";
import type { FocusTarget, Highlight } from "./pdf-viewer";
import { ScoreCard } from "./score-card";
import { SplitPane } from "./split-pane";

const PdfViewer = dynamic(() => import("./pdf-viewer"), {
  ssr: false,
  loading: () => (
    <div className="flex h-full items-center justify-center bg-muted p-6">
      <Skeleton className="aspect-[8.5/11] w-full max-w-2xl bg-card" />
    </div>
  ),
});

export function Workspace({ runId }: { runId: string }) {
  const run = useRun(runId);
  const protocols = useProtocols();

  if (run.isPending) return <WorkspaceSkeleton />;

  if (run.isError) {
    const notFound = run.error instanceof ApiError && run.error.status === 404;
    return (
      <div className="mx-auto max-w-xl p-6">
        {notFound ? (
          <div className="rounded-lg border bg-card">
            <EmptyState icon={FileQuestion} title={`Run ${runId} was not found`}>
              <Link href="/" className="font-medium text-primary hover:underline">
                Back to protocols
              </Link>
            </EmptyState>
          </div>
        ) : (
          <ErrorState title="Could not load this review" error={run.error} onRetry={() => void run.refetch()} />
        )}
      </div>
    );
  }

  const protocol = protocols.data?.items.find((p) => p.protocol_id === run.data.protocol_id);

  if (run.data.status === "failed") return <FailedRun run={run.data} protocol={protocol} />;
  if (run.data.status !== "complete" || !run.data.score) return <LiveRun run={run.data} protocol={protocol} />;
  return <ReviewWorkspace run={run.data} protocol={protocol} />;
}

// ---------------------------------------------------------------------------

function ReviewWorkspace({ run, protocol }: { run: Run; protocol: ProtocolListItem | undefined }) {
  const issuesQuery = useIssues(run.run_id);
  const searchParams = useSearchParams();
  const [selectedId, setSelectedId] = useState<string | null>(searchParams.get("issue"));
  const [filters, setFilters] = useState<IssueFilterState>(EMPTY_FILTERS);
  const [focus, setFocus] = useState<FocusTarget | null>(null);
  const [tab, setTab] = useState("issues");
  const nonce = useRef(0);

  const sorted = useMemo(
    () =>
      [...(issuesQuery.data?.items ?? [])].sort(
        (a, b) =>
          SEVERITY_META[a.severity].rank - SEVERITY_META[b.severity].rank ||
          (a.where.page ?? Infinity) - (b.where.page ?? Infinity),
      ),
    [issuesQuery.data],
  );
  const visible = useMemo(() => applyFilters(sorted, filters), [sorted, filters]);
  // A selection hidden by the filters is dropped rather than shown out of context.
  const selected = visible.find((i) => i.id === selectedId) ?? null;

  const focusOn = useCallback((page: number | null, bbox: Where["bbox"]) => {
    if (!page) return;
    nonce.current += 1;
    setFocus({ page, bbox, nonce: nonce.current });
  }, []);

  const select = useCallback(
    (id: string | null) => {
      setSelectedId(id);
      // Shallow URL update so a selected issue can be deep-linked and shared.
      const url = new URL(window.location.href);
      if (id) url.searchParams.set("issue", id);
      else url.searchParams.delete("issue");
      window.history.replaceState(null, "", url);
      const issue = id ? sorted.find((i) => i.id === id) : null;
      if (issue) {
        setTab("issues");
        focusOn(issue.where.page, issue.where.bbox);
      }
    },
    [sorted, focusOn],
  );

  // Deep link: focus the issue named in ?issue= once the issues have loaded.
  const deepLinked = useRef(false);
  useEffect(() => {
    if (deepLinked.current || !selectedId || !sorted.length) return;
    deepLinked.current = true;
    const issue = sorted.find((i) => i.id === selectedId);
    if (issue) focusOn(issue.where.page, issue.where.bbox);
  }, [selectedId, sorted, focusOn]);

  const highlights = useMemo(() => buildHighlights(visible, selected), [visible, selected]);

  return (
    <div className="flex flex-col lg:h-full">
      <WorkspaceHeader run={run} protocol={protocol} />

      <SplitPane
        storageKey="preflight.workspace.panelWidth"
        sideLabel="review panel"
        main={
          <PdfViewer
            file={protocolPdfUrl(run.protocol_id)}
            highlights={highlights}
            focus={focus}
            onSelectIssue={select}
          />
        }
        side={
        <aside aria-label="Review panel" className="flex min-h-0 flex-1 flex-col">
          <Tabs value={tab} onValueChange={setTab} className="flex min-h-0 flex-1 flex-col gap-0">
            <div className="border-b px-3 py-2">
              <TabsList className="w-full">
                <TabsTrigger value="issues">
                  Issues <span className="text-xs text-muted-foreground tabular">{issuesQuery.data?.total ?? ""}</span>
                </TabsTrigger>
                <TabsTrigger value="completeness">M11 &amp; SPIRIT completeness</TabsTrigger>
              </TabsList>
            </div>

            <TabsContent value="issues" className="flex min-h-0 flex-col">
              {issuesQuery.isPending && (
                <div className="space-y-2 p-3" aria-busy="true" aria-label="Loading issues">
                  {Array.from({ length: 8 }, (_, i) => (
                    <Skeleton key={i} className="h-12 w-full" />
                  ))}
                </div>
              )}
              {issuesQuery.isError && (
                <ErrorState className="m-3" error={issuesQuery.error} onRetry={() => void issuesQuery.refetch()} />
              )}
              {issuesQuery.data && (
                <>
                  <div className="space-y-2 border-b p-3">
                    <IssueFilters issues={sorted} value={filters} onChange={setFilters} />
                    <div className="flex items-center justify-between text-xs text-muted-foreground" aria-live="polite">
                      <span>
                        Showing <span className="font-medium text-foreground tabular">{visible.length}</span> of{" "}
                        <span className="tabular">{sorted.length}</span>
                      </span>
                      {isFiltered(filters) && <ClearFilters onClear={() => setFilters(EMPTY_FILTERS)} />}
                    </div>
                  </div>
                  <div className="min-h-0 flex-1 overflow-y-auto">
                    {visible.length ? (
                      <IssueList
                        issues={visible}
                        selectedId={selected?.id ?? null}
                        onSelect={select}
                        onLocate={(where) => focusOn(where.page, where.bbox)}
                      />
                    ) : (
                      <EmptyState icon={SearchX} title={sorted.length ? "No issues match these filters" : "No issues found"}>
                        {sorted.length > 0 && <ClearFilters onClear={() => setFilters(EMPTY_FILTERS)} />}
                      </EmptyState>
                    )}
                  </div>
                </>
              )}
            </TabsContent>

            <TabsContent value="completeness" className="min-h-0 overflow-y-auto">
              <CompletenessPanel runId={run.run_id} onGoToPage={(page) => focusOn(page, null)} />
            </TabsContent>
          </Tabs>
        </aside>
        }
      />
    </div>
  );
}

/** Faint boxes for every visible issue; the selected one gets the strong `where` and `related` styles. */
function buildHighlights(visible: Issue[], selected: Issue | null): Highlight[] {
  const out: Highlight[] = [];
  for (const issue of visible) {
    if (issue.id === selected?.id || !issue.where.page || !issue.where.bbox) continue;
    out.push({
      key: `${issue.id}-idle`,
      issueId: issue.id,
      page: issue.where.page,
      bbox: issue.where.bbox,
      kind: "idle",
      severity: issue.severity,
      label: `${SEVERITY_META[issue.severity].label}: ${issue.title}`,
    });
  }
  if (selected) {
    selected.related.forEach((r, i) => {
      if (r.page && r.bbox) {
        out.push({ key: `${selected.id}-rel-${i}`, issueId: selected.id, page: r.page, bbox: r.bbox, kind: "related", severity: selected.severity, label: r.section ?? "Related evidence" });
      }
    });
    if (selected.where.page && selected.where.bbox) {
      out.push({ key: `${selected.id}-where`, issueId: selected.id, page: selected.where.page, bbox: selected.where.bbox, kind: "where", severity: selected.severity, label: selected.title });
    }
  }
  return out;
}

// ---------------------------------------------------------------------------

function WorkspaceHeader({ run, protocol }: { run: Run; protocol: ProtocolListItem | undefined }) {
  return (
    <div className="flex shrink-0 flex-col gap-3 border-b bg-card px-4 py-3 xl:flex-row xl:items-center xl:gap-6">
      <div className="min-w-0 flex-1">
        <nav aria-label="Breadcrumb" className="flex items-center gap-1 text-xs text-muted-foreground">
          <Link href="/" className="rounded-sm transition-colors hover:text-foreground hover:underline">
            Protocols
          </Link>
          <ChevronRight className="size-3" aria-hidden />
          <span className="truncate font-mono">{protocol?.nct_id ?? run.protocol_id}</span>
        </nav>
        <h1 className="mt-1 truncate text-base leading-6 font-semibold" title={protocol?.title}>
          {protocol?.title ?? run.protocol_id}
        </h1>
        <p className="mt-0.5 flex flex-wrap items-center gap-x-2 text-xs text-muted-foreground">
          <span>Version {run.version_label}</span>
          <span aria-hidden>·</span>
          <span className="inline-flex items-center gap-1">
            {run.mode === "rules_only" && <Lock className="size-3" aria-hidden />}
            {MODE_LABEL[run.mode]}
          </span>
          {run.finished_at && (
            <>
              <span aria-hidden>·</span>
              <span className="tabular">Reviewed {formatDateTime(run.finished_at)}</span>
            </>
          )}
          <span aria-hidden>·</span>
          <span className="tabular">{formatDuration(run.duration_s)}</span>
          {run.llm_cost_usd != null && run.mode === "full" && (
            <>
              <span aria-hidden>·</span>
              <span className="tabular">LLM cost {formatUsd(run.llm_cost_usd)}</span>
            </>
          )}
        </p>
      </div>
      {run.score && <ScoreCard score={run.score} />}
    </div>
  );
}

function LiveRun({ run, protocol }: { run: Run; protocol: ProtocolListItem | undefined }) {
  const queryClient = useQueryClient();
  const [events, setEvents] = useState<Partial<Record<RunStep, ProgressEvent>>>({});
  const [error, setError] = useState<string | null>(null);

  useEffect(
    () =>
      subscribeRunEvents(run.run_id, {
        onProgress: (e) => setEvents((prev) => ({ ...prev, [e.step]: e })),
        onComplete: () => {
          void queryClient.invalidateQueries({ queryKey: keys.run(run.run_id) });
          void queryClient.invalidateQueries({ queryKey: keys.issues(run.run_id) });
        },
        onError: setError,
      }),
    [run.run_id, queryClient],
  );

  return (
    <div className="mx-auto max-w-xl space-y-4 p-6">
      <div>
        <h1 className="text-base font-semibold">{protocol?.title ?? run.protocol_id}</h1>
        <p className="text-sm text-muted-foreground">Review in progress · {MODE_LABEL[run.mode]}</p>
      </div>
      <div className="rounded-lg border bg-card p-4">
        <RunProgress events={events} failed={!!error} />
      </div>
      {error && <ErrorState title="The review stopped" error={new Error(error)} />}
    </div>
  );
}

function FailedRun({ run, protocol }: { run: Run; protocol: ProtocolListItem | undefined }) {
  return (
    <div className="mx-auto max-w-xl p-6">
      <div className="rounded-lg border bg-card">
        <EmptyState icon={CircleX} title="This review did not complete">
          <p>
            {protocol?.title ?? run.protocol_id} · {MODE_LABEL[run.mode]} · started {formatDateTime(run.started_at)}
          </p>
          <p className="mt-2">No score or issues were produced. Upload the protocol again to start a new review.</p>
          <Button asChild variant="outline" size="sm" className="mt-3">
            <Link href="/">Back to protocols</Link>
          </Button>
        </EmptyState>
      </div>
    </div>
  );
}

export function WorkspaceSkeleton() {
  return (
    <div className="flex h-full flex-col" aria-busy="true" aria-label="Loading review">
      <div className="space-y-3 border-b bg-card px-4 py-3">
        <Skeleton className="h-4 w-40" />
        <Skeleton className="h-5 w-2/3" />
        <Skeleton className="h-10 w-full" />
      </div>
      <div className="flex min-h-0 flex-1">
        <div className="flex-1 bg-muted p-6">
          <Skeleton className="mx-auto aspect-[8.5/11] max-w-2xl bg-card" />
        </div>
        <div className="hidden w-[420px] space-y-2 border-l bg-card p-3 lg:block">
          {Array.from({ length: 8 }, (_, i) => (
            <Skeleton key={i} className="h-12 w-full" />
          ))}
        </div>
      </div>
    </div>
  );
}
