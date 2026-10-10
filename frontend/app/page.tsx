import { PageHeader } from "@/components/common/page-header";
import { RecentProtocols } from "@/components/upload/recent-protocols";
import { UploadForm } from "@/components/upload/upload-form";

export default function ProtocolsPage() {
  return (
    <div className="mx-auto w-full max-w-6xl space-y-5 px-4 py-6 md:px-6">
      <PageHeader
        title="Protocols"
        description="Upload a protocol to check it for completeness, internal consistency, participant burden and amendment risk."
      />
      <UploadForm />
      <RecentProtocols />
    </div>
  );
}
