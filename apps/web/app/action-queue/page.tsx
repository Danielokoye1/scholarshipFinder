import { ActionQueueList } from "@/components/action-queue-list";
import { ApiUnavailable } from "@/components/api-unavailable";
import { PageHeading } from "@/components/page-heading";
import { api } from "@/lib/api";

export default async function ActionQueuePage() {
  const tasks = await api.tasks().catch(() => null);
  return <div className="page"><PageHeading eyebrow="Manual control" title="Action Queue" description="Only the specific items that require your judgment, ordered by explicit priority." />{tasks ? <><div className="alert info"><strong>External pages never open automatically</strong><span>Review links yourself and avoid entering sensitive information while a safety task is unresolved.</span></div><ActionQueueList initial={tasks} /></> : <ApiUnavailable />}</div>;
}
