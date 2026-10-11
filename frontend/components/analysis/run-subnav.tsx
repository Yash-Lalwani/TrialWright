import { ChevronRight } from "lucide-react";
import Link from "next/link";

import { cn } from "@/lib/utils";

/** Header for the pages under /runs/{id}: breadcrumb, title, and a switch back to the review. */
export function RunPageHeader({
  runId,
  protocolName,
  current,
  title,
  description,
}: {
  runId: string;
  protocolName: string;
  current: "burden";
  title: string;
  description: string;
}) {
  return (
    <div>
      <nav aria-label="Breadcrumb" className="flex min-w-0 items-center gap-1 text-xs text-muted-foreground">
        <Link href="/" className="rounded-sm hover:text-foreground hover:underline">
          Protocols
        </Link>
        <ChevronRight className="size-3 shrink-0" aria-hidden />
        <Link href={`/runs/${runId}`} className="truncate rounded-sm hover:text-foreground hover:underline">
          {protocolName}
        </Link>
      </nav>
      <div className="mt-2 flex flex-wrap items-end justify-between gap-3">
        <div className="min-w-0">
          <h1 className="text-xl font-semibold tracking-tight">{title}</h1>
          <p className="mt-1 max-w-3xl text-sm text-muted-foreground">{description}</p>
        </div>
        <ReviewTabs runId={runId} current={current} />
      </div>
    </div>
  );
}

export function ReviewTabs({ runId, current }: { runId: string; current: "review" | "burden" }) {
  const items = [
    { key: "review", label: "Review", href: `/runs/${runId}` },
    { key: "burden", label: "Burden and peers", href: `/runs/${runId}/burden` },
  ] as const;
  return (
    <nav aria-label="Review sections" className="inline-flex rounded-lg bg-muted p-[3px] text-sm">
      {items.map((item) => (
        <Link
          key={item.key}
          href={item.href}
          aria-current={item.key === current ? "page" : undefined}
          className={cn(
            "rounded-md px-3 py-1 font-medium text-muted-foreground transition-colors hover:text-foreground focus-visible:ring-2 focus-visible:ring-ring/50 focus-visible:outline-none",
            item.key === current && "bg-card text-foreground shadow-sm",
          )}
        >
          {item.label}
        </Link>
      ))}
    </nav>
  );
}
