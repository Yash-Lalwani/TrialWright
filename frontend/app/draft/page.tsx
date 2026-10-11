import type { Metadata } from "next";

import { DraftView } from "@/components/analysis/draft-view";
import { PageHeader } from "@/components/common/page-header";

export const metadata: Metadata = { title: "Draft" };

export default function DraftPage() {
  return (
    <div className="mx-auto w-full max-w-6xl space-y-5 px-4 py-6 md:px-6">
      <PageHeader
        title="Draft a protocol"
        description="Turn a design brief into an ICH M11 draft that cites similar trials as precedent. Pre-Flight then runs its own checks on the draft."
      />
      <DraftView />
    </div>
  );
}
