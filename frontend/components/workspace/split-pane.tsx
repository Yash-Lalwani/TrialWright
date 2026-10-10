"use client";

import { useEffect, useRef, useState, type ReactNode } from "react";

import { cn } from "@/lib/utils";

const STEP = 16;
const BIG_STEP = 64;

/**
 * Two-pane layout with a draggable, keyboard-operable divider (lg and up).
 * The divider is a `role="separator"` whose value is the side pane width.
 * Arrow keys resize (Shift for larger steps), Home/End jump to the limits, and
 * Enter or a double-click restores the default. Below lg the panes stack and
 * the divider is hidden. The width is remembered per browser (best effort).
 */
export function SplitPane({
  main,
  side,
  sideLabel,
  storageKey,
  defaultSide = 440,
  minSide = 360,
  minMain = 440,
}: {
  main: ReactNode;
  side: ReactNode;
  sideLabel: string;
  storageKey: string;
  defaultSide?: number;
  minSide?: number;
  minMain?: number;
}) {
  const containerRef = useRef<HTMLDivElement>(null);
  const [width, setWidth] = useState(defaultSide);
  const [containerWidth, setContainerWidth] = useState(0);
  const [dragging, setDragging] = useState(false);

  // 1px for the divider itself, so the main pane keeps at least minMain.
  const maxSide = containerWidth ? Math.max(minSide, containerWidth - minMain - 1) : 720;
  const clamp = (w: number) => Math.round(Math.min(Math.max(w, minSide), maxSide));
  const sideWidth = clamp(width);

  // Restore the remembered width after hydration (storage may be unavailable).
  useEffect(() => {
    try {
      const saved = Number(window.localStorage.getItem(storageKey));
      // Client-only value; reading it during render would mismatch the server HTML.
      // eslint-disable-next-line react-hooks/set-state-in-effect
      if (saved > 0) setWidth(saved);
    } catch {
      // Private mode or blocked storage: keep the default.
    }
  }, [storageKey]);

  useEffect(() => {
    const el = containerRef.current;
    if (!el) return;
    const observer = new ResizeObserver(() => setContainerWidth(el.clientWidth));
    observer.observe(el);
    return () => observer.disconnect();
  }, []);

  const commit = (w: number) => {
    const next = clamp(w);
    setWidth(next);
    try {
      window.localStorage.setItem(storageKey, String(next));
    } catch {
      // Best effort only.
    }
  };

  const widthAt = (clientX: number) => {
    const rect = containerRef.current?.getBoundingClientRect();
    return rect ? rect.right - clientX : sideWidth;
  };

  return (
    <div ref={containerRef} className="flex min-h-0 flex-1 flex-col lg:flex-row">
      <div className="h-[70vh] min-w-0 flex-1 border-b lg:h-auto lg:border-b-0">{main}</div>

      <div
        role="separator"
        aria-orientation="vertical"
        aria-label={`Resize ${sideLabel}`}
        aria-valuemin={minSide}
        aria-valuemax={maxSide}
        aria-valuenow={sideWidth}
        aria-valuetext={`${sideLabel} ${sideWidth} pixels wide`}
        tabIndex={0}
        onPointerDown={(e) => {
          if (e.button !== 0) return;
          e.currentTarget.setPointerCapture(e.pointerId);
          setDragging(true);
        }}
        onPointerMove={(e) => {
          if (dragging) setWidth(clamp(widthAt(e.clientX)));
        }}
        onPointerUp={(e) => {
          if (!dragging) return;
          e.currentTarget.releasePointerCapture(e.pointerId);
          setDragging(false);
          commit(widthAt(e.clientX));
        }}
        onPointerCancel={() => setDragging(false)}
        onDoubleClick={() => commit(defaultSide)}
        onKeyDown={(e) => {
          const step = e.shiftKey ? BIG_STEP : STEP;
          const keys: Record<string, number> = {
            ArrowLeft: sideWidth + step,
            ArrowRight: sideWidth - step,
            Home: minSide,
            End: maxSide,
            Enter: defaultSide,
          };
          if (e.key in keys) {
            e.preventDefault();
            commit(keys[e.key]);
          }
        }}
        className={cn(
          "group relative z-10 hidden w-px shrink-0 cursor-col-resize touch-none bg-border outline-none select-none lg:block",
          "after:absolute after:inset-y-0 after:-right-1 after:-left-1 after:content-['']",
          "hover:bg-primary/40 focus-visible:bg-primary",
          dragging && "bg-primary",
        )}
      >
        <span
          aria-hidden
          className={cn(
            "absolute top-1/2 left-1/2 h-8 w-1.5 -translate-x-1/2 -translate-y-1/2 rounded-full border bg-card shadow-[0_1px_2px_rgb(16_24_40/0.12)] transition-colors duration-150",
            "group-hover:border-primary/50 group-focus-visible:border-primary group-focus-visible:ring-2 group-focus-visible:ring-ring/40",
            dragging && "border-primary",
          )}
        />
      </div>

      <div
        className={cn("flex min-h-0 flex-col bg-card lg:w-(--side-w) lg:shrink-0", dragging && "select-none")}
        style={{ "--side-w": `${sideWidth}px` } as React.CSSProperties}
      >
        {side}
      </div>
    </div>
  );
}
