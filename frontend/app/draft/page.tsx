import type { Metadata } from "next";
import { Suspense } from "react";

import { DraftView } from "@/components/draft/draft-view";
import { Skeleton } from "@/components/ui/skeleton";

export const metadata: Metadata = { title: "Draft" };

export default function DraftPage() {
  return (
    <Suspense fallback={<Skeleton className="m-6 h-96" />}>
      <DraftView />
    </Suspense>
  );
}
