import type { Metadata } from "next";

import { EvidenceView } from "@/components/analysis/evidence-view";
import { PageHeader } from "@/components/common/page-header";

export const metadata: Metadata = { title: "Evidence" };

export default function EvidencePage() {
  return (
    <div className="mx-auto w-full max-w-6xl space-y-5 px-4 py-6 md:px-6">
      <PageHeader
        title="Evidence"
        description="How well Pre-Flight works, measured with PreflightBench: real protocols with documented injected errors, a held-out test set, an ablation and a retrospective registry check."
      />
      <EvidenceView />
    </div>
  );
}
