import type { Metadata } from "next";
import { Suspense } from "react";

import { CompareView } from "@/components/analysis/compare-view";
import { Skeleton } from "@/components/ui/skeleton";

export const metadata: Metadata = { title: "Compare" };

/** E5. useSearchParams needs a Suspense boundary under cacheComponents. */
export default function ComparePage() {
  return (
    <Suspense fallback={<Skeleton className="m-6 h-96" />}>
      <CompareView />
    </Suspense>
  );
}
