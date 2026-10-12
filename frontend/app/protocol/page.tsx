import { HomeIntro } from "@/components/upload/home-intro";
import { RecentProtocols } from "@/components/upload/recent-protocols";
import { UploadForm } from "@/components/upload/upload-form";

export default function ProtocolsPage() {
  return (
    <>
      <HomeIntro />
      <div className="mx-auto w-full max-w-6xl space-y-5 px-4 py-6 md:px-6">
        <UploadForm />
        <RecentProtocols />
      </div>
    </>
  );
}
