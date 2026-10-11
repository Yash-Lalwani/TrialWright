import { FlaskConical } from "lucide-react";
import type { Metadata } from "next";

import { PageHeader } from "@/components/common/page-header";
import { EmptyState } from "@/components/common/states";

export const metadata: Metadata = { title: "Evidence" };

export default function EvidencePage() {
  return (
    <div className="mx-auto w-full max-w-6xl space-y-6 px-4 py-6 md:px-6">
      <PageHeader
        title="Evidence"
        description="PreflightBench results: recall, precision, ablation, hallucination rate, human baseline and an ROI calculator."
      />
      <div className="rounded-lg border bg-card">
        <EmptyState icon={FlaskConical} title="Not built yet">
          This page is scheduled for build phase H15 to H18. It will show results from <code>preflight bench</code> only,
          never placeholder numbers presented as measurements.
        </EmptyState>
      </div>
    </div>
  );
}
