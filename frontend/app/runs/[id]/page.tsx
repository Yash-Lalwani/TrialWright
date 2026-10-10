import type { Metadata } from "next";
import { Suspense } from "react";

import { Workspace, WorkspaceSkeleton } from "@/components/workspace/workspace";

export const metadata: Metadata = { title: "Review" };

/** F1 workspace. Params are resolved inside Suspense so the shell still prerenders (cacheComponents). */
export default function RunPage({ params }: PageProps<"/runs/[id]">) {
  return (
    <Suspense fallback={<WorkspaceSkeleton />}>
      {params.then(({ id }) => (
        <Workspace runId={id} />
      ))}
    </Suspense>
  );
}
