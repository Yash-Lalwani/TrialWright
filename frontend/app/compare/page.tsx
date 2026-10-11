import type { Metadata } from "next";
import { Suspense } from "react";

import { CompareView } from "@/components/analysis/compare-view";
import { PageHeader } from "@/components/common/page-header";
import { Skeleton } from "@/components/ui/skeleton";

export const metadata: Metadata = { title: "Compare versions" };

export default function ComparePage() {
  return (
    <div className="mx-auto w-full max-w-6xl space-y-5 px-4 py-6 md:px-6">
      <PageHeader
        title="Compare versions"
        description="See which issues a protocol revision resolved, which are new, and how the Pre-Flight score changed."
      />
      {/* useSearchParams is runtime data; Suspense keeps the page shell static (cacheComponents). */}
      <Suspense fallback={<Skeleton className="h-64 w-full" />}>
        <CompareView />
      </Suspense>
    </div>
  );
}
