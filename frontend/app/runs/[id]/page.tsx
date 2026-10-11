import type { Metadata } from "next";
import { Suspense } from "react";

import { ReviewPage } from "@/components/analysis/run-pages";
import { WorkspaceSkeleton } from "@/components/workspace/workspace";

export const metadata: Metadata = { title: "Review" };

/** F1 workspace. The run id is read on the client so the review starts loading at once. */
export default function RunPage() {
  return (
    <Suspense fallback={<WorkspaceSkeleton />}>
      <ReviewPage />
    </Suspense>
  );
}
