import type { Metadata } from "next";
import { Suspense } from "react";

import { BurdenPage as Burden } from "@/components/analysis/run-pages";
import { Skeleton } from "@/components/ui/skeleton";

export const metadata: Metadata = { title: "Burden & peers" };

export default function BurdenPage() {
  return (
    <Suspense fallback={<Skeleton className="m-6 h-96" />}>
      <Burden />
    </Suspense>
  );
}
