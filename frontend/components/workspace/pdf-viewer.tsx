"use client";

// Continuous-scroll PDF viewer with evidence overlays.
//
// Bounding boxes arrive in PDF points with a top-left origin (CONTRACTS.md §2) and
// are multiplied by the render scale. Pages are absolutely positioned from their
// known sizes, so scrolling to any page or bbox is plain arithmetic, and only
// pages near the viewport are rendered (protocols run to 150+ pages).
//
// Load this module with next/dynamic and ssr: false (pdf.js needs the browser).

import { ChevronLeft, ChevronRight, Maximize2, Minus, Plus } from "lucide-react";
import { Suspense, useCallback, useEffect, useLayoutEffect, useMemo, useRef, useState } from "react";
import { Document, Page, pdfjs } from "react-pdf";
import "react-pdf/dist/Page/TextLayer.css";

import { ErrorState } from "@/components/common/states";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { SEVERITY_COLOR, SEVERITY_META } from "@/lib/presentation";
import type { BBox, Severity } from "@/lib/types";
import { cn } from "@/lib/utils";

// Must be set in the module that renders <Document> (react-pdf README). Assets are
// copied from the matching pdfjs-dist version by scripts/copy-pdf-assets.mjs.
pdfjs.GlobalWorkerOptions.workerSrc = "/pdfjs/pdf.worker.min.mjs";
const PDF_OPTIONS = {
  standardFontDataUrl: "/pdfjs/standard_fonts/",
  cMapUrl: "/pdfjs/cmaps/",
  cMapPacked: true,
};

const PAD = 24;
const GAP = 16;
const RENDER_MARGIN = 1200;
const ZOOM_STEPS = [0.5, 0.75, 1, 1.25, 1.5, 2, 2.5, 3];
const MIN_SCALE = 0.4;
const MAX_SCALE = 3;

export interface Highlight {
  key: string;
  issueId: string;
  page: number;
  bbox: BBox;
  kind: "where" | "related" | "idle";
  severity: Severity;
  label: string;
}

/** Scroll request. A new `nonce` re-triggers the scroll and the evidence pulse. */
export interface FocusTarget {
  page: number;
  bbox: BBox | null;
  nonce: number;
}

interface Props {
  file: string;
  highlights: Highlight[];
  focus: FocusTarget | null;
  onSelectIssue: (issueId: string) => void;
}

type Zoom = { mode: "fit" } | { mode: "manual"; scale: number };

const prefersReducedMotion = () =>
  typeof window !== "undefined" && window.matchMedia("(prefers-reduced-motion: reduce)").matches;

export default function PdfViewer({ file, highlights, focus, onSelectIssue }: Props) {
  const scrollRef = useRef<HTMLDivElement>(null);
  /** Scroll position a focus request is heading to, and the request itself (see focus effect). */
  const scrollTarget = useRef<number | null>(null);
  const pendingFocus = useRef<FocusTarget | null>(null);
  const [sizes, setSizes] = useState<{ w: number; h: number }[]>([]);
  const [loadError, setLoadError] = useState<Error | null>(null);
  const [containerWidth, setContainerWidth] = useState(0);
  const [viewport, setViewport] = useState({ top: 0, height: 0 });
  const [zoom, setZoom] = useState<Zoom>({ mode: "fit" });

  // ---- geometry ----
  const maxWidth = useMemo(() => Math.max(1, ...sizes.map((s) => s.w)), [sizes]);
  const fitScale = containerWidth ? Math.max(MIN_SCALE, Math.min(MAX_SCALE, (containerWidth - 2 * PAD) / maxWidth)) : 1;
  const scale = zoom.mode === "fit" ? fitScale : zoom.scale;

  const tops = useMemo(() => {
    const out: number[] = [];
    let y = PAD;
    for (const s of sizes) {
      out.push(y);
      y += s.h * scale + GAP;
    }
    return out;
  }, [sizes, scale]);

  const totalHeight = sizes.length ? tops[tops.length - 1] + sizes[sizes.length - 1].h * scale + PAD : 0;
  const innerWidth = Math.max(containerWidth, maxWidth * scale + 2 * PAD);
  const pageLeft = useCallback(
    (index: number) => Math.max(PAD, (innerWidth - sizes[index].w * scale) / 2),
    [innerWidth, sizes, scale],
  );

  const currentPage = useMemo(() => {
    if (!tops.length) return 1;
    const probe = viewport.top + viewport.height * 0.35;
    let page = 1;
    for (let i = 0; i < tops.length; i++) if (tops[i] <= probe) page = i + 1;
    return page;
  }, [tops, viewport]);

  const isNearViewport = (i: number) =>
    tops[i] < viewport.top + viewport.height + RENDER_MARGIN &&
    tops[i] + sizes[i].h * scale > viewport.top - RENDER_MARGIN;

  // ---- scroll tracking ----
  const frame = useRef(0);
  const onScroll = () => {
    const el = scrollRef.current;
    if (el && scrollTarget.current !== null && Math.abs(el.scrollTop - scrollTarget.current) < 2) {
      pendingFocus.current = null;
      scrollTarget.current = null;
    }
    cancelAnimationFrame(frame.current);
    frame.current = requestAnimationFrame(() => {
      const el = scrollRef.current;
      if (!el) return;
      setViewport({ top: el.scrollTop, height: el.clientHeight });
    });
  };

  // Zoom and resize keep the same spot in view: the reading position is captured
  // right before the scale changes and restored once the new geometry is laid out.
  // Scrolling never triggers a restore.
  const pendingAnchor = useRef<{ page: number; fraction: number } | null>(null);
  const captureAnchor = useCallback(() => {
    const el = scrollRef.current;
    if (!el || !sizes.length) return;
    let i = 0;
    for (let k = 0; k < tops.length; k++) if (tops[k] <= el.scrollTop + 1) i = k;
    pendingAnchor.current = { page: i, fraction: (el.scrollTop - tops[i]) / (sizes[i].h * scale) };
  }, [sizes, tops, scale]);

  const captureRef = useRef(captureAnchor);
  useEffect(() => {
    captureRef.current = captureAnchor;
  }, [captureAnchor]);

  useLayoutEffect(() => {
    const el = scrollRef.current;
    const a = pendingAnchor.current;
    if (!el || !a || !sizes.length) return;
    pendingAnchor.current = null;
    el.scrollTop = tops[a.page] + a.fraction * sizes[a.page].h * scale;
  }, [tops, sizes, scale]);

  // ---- container size (fit width follows the panel width) ----
  const lastWidth = useRef(0);
  useEffect(() => {
    const el = scrollRef.current;
    if (!el) return;
    const observer = new ResizeObserver(() => {
      // Width 0 means the viewer is hidden (an ancestor Suspense or Activity boundary):
      // keep the last geometry instead of collapsing the layout.
      if (!el.clientWidth) return;
      if (lastWidth.current && el.clientWidth !== lastWidth.current) captureRef.current();
      lastWidth.current = el.clientWidth;
      setContainerWidth(el.clientWidth);
      setViewport({ top: el.scrollTop, height: el.clientHeight });
    });
    observer.observe(el);
    return () => observer.disconnect();
  }, []);

  // ---- navigation ----
  const scrollToPage = useCallback(
    (page: number, bbox: BBox | null = null, smooth = true) => {
      const el = scrollRef.current;
      if (!el || !sizes.length) return;
      const i = Math.min(Math.max(page, 1), sizes.length) - 1;
      const raw = bbox ? tops[i] + bbox[1] * scale - el.clientHeight * 0.3 : tops[i] - PAD / 2;
      const top = Math.min(Math.max(0, raw), el.scrollHeight - el.clientHeight);
      const left = bbox ? Math.max(0, pageLeft(i) + bbox[0] * scale - PAD) : el.scrollLeft;
      scrollTarget.current = top;
      el.scrollTo({ top, left, behavior: smooth && !prefersReducedMotion() ? "smooth" : "auto" });
    },
    [sizes, tops, scale, pageLeft],
  );

  // A focus request stays pending until the scroll reaches its target. If an ancestor
  // Suspense or Activity boundary hides the viewer mid-scroll, its effects re-run on
  // reveal and the pending request is re-applied instantly. Manual scroll input cancels it.
  const handledNonce = useRef<number | null>(null);
  const [pulseNonce, setPulseNonce] = useState<number | null>(null);
  useEffect(() => {
    // Wait for real geometry (page sizes and a measured width) before scrolling.
    if (!focus || !sizes.length || !containerWidth || handledNonce.current === focus.nonce) return;
    const first = handledNonce.current === null;
    handledNonce.current = focus.nonce;
    pendingFocus.current = focus;
    // The first focus (deep link) jumps; later ones glide so the reader keeps context.
    scrollToPage(focus.page, focus.bbox, !first);
    // Restart the pulse animation on the newly focused evidence (new key = new element).
    setPulseNonce(focus.nonce);
  }, [focus, sizes.length, containerWidth, scrollToPage]);

  const scrollToPageRef = useRef(scrollToPage);
  useEffect(() => {
    scrollToPageRef.current = scrollToPage;
  }, [scrollToPage]);
  useEffect(() => {
    const pending = pendingFocus.current;
    if (pending) scrollToPageRef.current(pending.page, pending.bbox, false);
  }, []);

  const cancelPendingFocus = () => {
    pendingFocus.current = null;
    scrollTarget.current = null;
  };

  const zoomBy = (direction: 1 | -1) => {
    const next =
      direction > 0 ? ZOOM_STEPS.find((z) => z > scale + 0.001) : [...ZOOM_STEPS].reverse().find((z) => z < scale - 0.001);
    captureAnchor();
    setZoom({ mode: "manual", scale: next ?? scale });
  };

  // ---- overlays by page ----
  const byPage = useMemo(() => {
    const map = new Map<number, Highlight[]>();
    // Idle first so the selected evidence paints on top.
    const order = { idle: 0, related: 1, where: 2 } as const;
    for (const h of [...highlights].sort((a, b) => order[a.kind] - order[b.kind])) {
      map.set(h.page, [...(map.get(h.page) ?? []), h]);
    }
    return map;
  }, [highlights]);

  return (
    <div className="flex h-full min-h-0 flex-col bg-muted">
      <Toolbar
        page={currentPage}
        pages={sizes.length}
        scale={scale}
        fit={zoom.mode === "fit"}
        onPage={(p) => scrollToPage(p)}
        onZoomIn={() => zoomBy(1)}
        onZoomOut={() => zoomBy(-1)}
        onFit={() => {
          captureAnchor();
          setZoom({ mode: "fit" });
        }}
      />

      <div
        ref={scrollRef}
        onScroll={onScroll}
        onWheel={cancelPendingFocus}
        onPointerDown={cancelPendingFocus}
        onKeyDown={cancelPendingFocus}
        tabIndex={0}
        role="region"
        aria-label={`Protocol document, page ${currentPage} of ${sizes.length || "?"}`}
        className="relative min-h-0 flex-1 overflow-auto outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-inset"
      >
        {loadError ? (
          <ErrorState className="m-6" title="Could not open the protocol PDF" error={loadError} />
        ) : (
          <Suspense fallback={<DocumentSkeleton />}>
            <Document
              file={file}
              options={PDF_OPTIONS}
              onLoadSuccess={async (pdf) => {
                const pages = await Promise.all(
                  Array.from({ length: pdf.numPages }, (_, i) => pdf.getPage(i + 1)),
                );
                setSizes(pages.map((p) => {
                  const v = p.getViewport({ scale: 1 });
                  return { w: v.width, h: v.height };
                }));
              }}
              onLoadError={setLoadError}
              loading={<DocumentSkeleton />}
              error={null}
            >
              <div className="relative" style={{ height: totalHeight, width: innerWidth }}>
                {sizes.map((size, i) => (
                  <div
                    key={i}
                    data-page={i + 1}
                    className="absolute overflow-hidden bg-white shadow-[0_1px_3px_rgb(16_24_40/0.12)] ring-1 ring-black/5"
                    style={{ top: tops[i], left: pageLeft(i), width: size.w * scale, height: size.h * scale }}
                  >
                    {isNearViewport(i) ? (
                      <>
                        {/* react-pdf 11 suspends (React `use`) while a page loads. A boundary per
                            page keeps that local; otherwise the nearest boundary would hide the
                            whole viewer and reset its scroll position. */}
                        <Suspense fallback={null}>
                          <Page
                            pageNumber={i + 1}
                            scale={scale}
                            renderAnnotationLayer={false}
                            loading={null}
                            className="pointer-events-auto"
                          />
                        </Suspense>
                        <div className="pointer-events-none absolute inset-0 z-[3]">
                          {(byPage.get(i + 1) ?? []).map((h) => (
                            <HighlightBox
                              key={h.kind === "idle" ? h.key : `${h.key}-${pulseNonce}`}
                              highlight={h}
                              scale={scale}
                              pulse={h.kind === "where" && pulseNonce !== null}
                              onSelect={onSelectIssue}
                            />
                          ))}
                        </div>
                      </>
                    ) : (
                      <span className="absolute inset-0 flex items-center justify-center text-xs text-muted-foreground">
                        Page {i + 1}
                      </span>
                    )}
                  </div>
                ))}
              </div>
            </Document>
          </Suspense>
        )}
      </div>
    </div>
  );
}

function HighlightBox({
  highlight: h,
  scale,
  pulse,
  onSelect,
}: {
  highlight: Highlight;
  scale: number;
  pulse: boolean;
  onSelect: (id: string) => void;
}) {
  const [x0, y0, x1, y1] = h.bbox;
  const style = {
    left: x0 * scale,
    top: y0 * scale,
    width: (x1 - x0) * scale,
    height: (y1 - y0) * scale,
    "--sev": SEVERITY_COLOR[h.severity],
  } as React.CSSProperties;

  if (h.kind === "idle") {
    return (
      <button
        type="button"
        aria-label={`Show issue: ${h.label}`}
        title={h.label}
        onClick={() => onSelect(h.issueId)}
        style={style}
        className="pointer-events-auto absolute border-b-2 border-(--sev) bg-hl-idle opacity-70 mix-blend-multiply transition-opacity hover:opacity-100 focus-visible:opacity-100 focus-visible:outline-2 focus-visible:outline-ring"
      />
    );
  }

  const isWhere = h.kind === "where";
  const boxHeight = (y1 - y0) * scale;
  return (
    <>
      <div
        style={style}
        className={cn(
          "absolute rounded-[2px]",
          isWhere
            ? "bg-hl-where outline-2 outline-offset-1 outline-(--sev)"
            : "bg-hl-related outline-2 outline-offset-1 outline-hl-related-border outline-dashed",
          pulse && "evidence-pulse",
        )}
      />
      {/* Tag sits in the page's left margin (protocol margins are ~1 in) so it never covers text. */}
      {scale >= 0.75 && (
        <span
          style={{ left: 4, top: y0 * scale + boxHeight / 2 - 8, "--sev": SEVERITY_COLOR[h.severity] } as React.CSSProperties}
          className={cn(
            "absolute rounded-sm px-1 py-px font-mono text-[11px] leading-[14px] font-medium whitespace-nowrap text-white shadow-sm",
            isWhere ? "bg-(--sev)" : "bg-hl-related-border",
          )}
          title={isWhere ? `${SEVERITY_META[h.severity].label}: ${h.label}` : `Related evidence: ${h.label}`}
        >
          {isWhere ? h.issueId : "Related"}
        </span>
      )}
    </>
  );
}

function Toolbar({
  page,
  pages,
  scale,
  fit,
  onPage,
  onZoomIn,
  onZoomOut,
  onFit,
}: {
  page: number;
  pages: number;
  scale: number;
  fit: boolean;
  onPage: (p: number) => void;
  onZoomIn: () => void;
  onZoomOut: () => void;
  onFit: () => void;
}) {
  const [draft, setDraft] = useState<string | null>(null);
  const commit = () => {
    const n = Number(draft);
    if (Number.isInteger(n) && n >= 1 && n <= pages) onPage(n);
    setDraft(null);
  };

  return (
    <div className="@container flex h-10 shrink-0 items-center gap-1 border-b bg-card px-2">
      <ToolButton label="Previous page" onClick={() => onPage(page - 1)} disabled={page <= 1}>
        <ChevronLeft />
      </ToolButton>
      <label className="flex items-center gap-1.5 text-[13px] text-muted-foreground">
        <span className="sr-only">Page number</span>
        <input
          inputMode="numeric"
          value={draft ?? String(page)}
          onFocus={(e) => {
            setDraft(String(page));
            e.currentTarget.select();
          }}
          onChange={(e) => setDraft(e.target.value.replace(/\D/g, ""))}
          onBlur={commit}
          onKeyDown={(e) => {
            if (e.key === "Enter") e.currentTarget.blur();
            if (e.key === "Escape") {
              setDraft(null);
              e.currentTarget.blur();
            }
          }}
          className="h-7 w-11 rounded-md border bg-background px-1.5 text-center text-[13px] text-foreground tabular focus-visible:ring-2 focus-visible:ring-ring/50 focus-visible:outline-none"
        />
        <span className="tabular">/ {pages || "–"}</span>
      </label>
      <ToolButton label="Next page" onClick={() => onPage(page + 1)} disabled={!pages || page >= pages}>
        <ChevronRight />
      </ToolButton>

      <HighlightLegend />

      <div className="ml-auto flex items-center gap-1">
        <ToolButton label="Zoom out" onClick={onZoomOut} disabled={scale <= ZOOM_STEPS[0]}>
          <Minus />
        </ToolButton>
        <span className="w-12 text-center text-[13px] text-muted-foreground tabular" aria-live="polite">
          {Math.round(scale * 100)}%
        </span>
        <ToolButton label="Zoom in" onClick={onZoomIn} disabled={scale >= MAX_SCALE}>
          <Plus />
        </ToolButton>
        <Button variant={fit ? "secondary" : "ghost"} size="sm" onClick={onFit} aria-pressed={fit}>
          <Maximize2 aria-hidden />
          Fit width
        </Button>
      </div>
    </div>
  );
}

/** Key for the overlay styles; matches the swatches in the issue detail. Hidden when the pane is narrow. */
function HighlightLegend() {
  return (
    <ul aria-label="Highlight key" className="ml-4 hidden items-center gap-3 text-xs text-muted-foreground @[40rem]:flex">
      <li className="flex items-center gap-1.5">
        <span aria-hidden className="size-3 rounded-[2px] border-[1.5px] border-foreground/60 bg-hl-where" />
        Evidence
      </li>
      <li className="flex items-center gap-1.5">
        <span aria-hidden className="size-3 rounded-[2px] border-[1.5px] border-dashed border-hl-related-border bg-hl-related" />
        Related
      </li>
      <li className="flex items-center gap-1.5">
        <span aria-hidden className="h-3 w-3 border-b-2 border-sev-advisory bg-hl-idle" />
        Other issues
      </li>
    </ul>
  );
}

function ToolButton({
  label,
  children,
  ...props
}: { label: string; children: React.ReactNode } & React.ComponentProps<typeof Button>) {
  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <Button variant="ghost" size="icon-sm" aria-label={label} {...props}>
          {children}
        </Button>
      </TooltipTrigger>
      <TooltipContent>{label}</TooltipContent>
    </Tooltip>
  );
}

function DocumentSkeleton() {
  return (
    <div className="mx-auto flex max-w-2xl flex-col gap-4 p-6" aria-busy="true" aria-label="Loading document">
      <Skeleton className="aspect-[8.5/11] w-full bg-card" />
    </div>
  );
}
