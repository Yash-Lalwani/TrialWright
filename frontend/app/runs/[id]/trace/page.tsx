import type { Metadata } from "next";
import { Suspense } from "react";

import { TracePage as Trace } from "@/components/analysis/run-pages";
import { Skeleton } from "@/components/ui/skeleton";

export const metadata: Metadata = { title: "Audit & trace" };

export default function TracePage() {
  return (
    <Suspense fallback={<Skeleton className="m-6 h-96" />}>
      <Trace />
    </Suspense>
  );
}
