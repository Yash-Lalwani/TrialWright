import type { Metadata } from "next";
import { Suspense } from "react";

import { BurdenView } from "@/components/analysis/burden-view";
import { Skeleton } from "@/components/ui/skeleton";

export const metadata: Metadata = { title: "Burden and peers" };

/** Burden (4.8), peer comparison (4.9) and precedent (4.10) for one run. */
export default function BurdenPage({ params }: PageProps<"/runs/[id]/burden">) {
  return (
    <Suspense fallback={<Skeleton className="m-6 h-96" />}>
      {params.then(({ id }) => (
        <BurdenView key={id} runId={id} />
      ))}
    </Suspense>
  );
}
