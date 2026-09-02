import { ApiUnavailable } from "@/components/api-unavailable";
import { PageHeading } from "@/components/page-heading";
import { ProfileWorkspace } from "@/components/profile-workspace";
import { api } from "@/lib/api";

export default async function ProfilePage() {
  const overview = await api.profileOverview().catch(() => null);
  return <div className="page"><PageHeading eyebrow="Your source of truth" title="Profile intelligence" description="One reviewed profile built from your entries, context, and locally corroborated documents." />{overview ? <ProfileWorkspace initial={overview} /> : <ApiUnavailable />}</div>;
}
