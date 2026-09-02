import { ApiUnavailable } from "@/components/api-unavailable";
import { PageHeading } from "@/components/page-heading";
import { ProfileEditor } from "@/components/profile-editor";
import { api } from "@/lib/api";

export default async function ProfilePage() {
  const fields = await api.profile().catch(() => null);
  return <div className="page"><PageHeading eyebrow="Source of truth" title="Profile" description="Verified personal data and its provenance. Nothing is inferred when a value is missing." />{fields ? <ProfileEditor initial={fields} /> : <ApiUnavailable />}</div>;
}

