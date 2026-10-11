import { FilePenLine } from "lucide-react";
import type { Metadata } from "next";

import { PageHeader } from "@/components/common/page-header";
import { EmptyState } from "@/components/common/states";

export const metadata: Metadata = { title: "Draft" };

export default function DraftPage() {
  return (
    <div className="mx-auto w-full max-w-6xl space-y-6 px-4 py-6 md:px-6">
      <PageHeader
        title="Draft a protocol"
        description="Turn a design brief into an ICH M11 draft with precedent from similar trials and a self-check."
      />
      <div className="rounded-lg border bg-card">
        <EmptyState icon={FilePenLine} title="Not built yet">
          The brief form, precedent table, M11 draft and self-check are scheduled for build phase H15 to H18.
        </EmptyState>
      </div>
    </div>
  );
}
