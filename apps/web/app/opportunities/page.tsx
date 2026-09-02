import { ApiUnavailable } from "@/components/api-unavailable";
import { OpportunityTable } from "@/components/opportunity-table";
import { PageHeading } from "@/components/page-heading";
import { api } from "@/lib/api";

export default async function OpportunitiesPage() {
  const data = await api.scholarships().catch(() => null);
  return <div className="page"><PageHeading eyebrow="Intelligence" title="Opportunities" description="Evidence-backed scholarships ranked with visible criteria and guarded by destination safety." />{data ? <><div className="alert info"><strong>Review before workflow</strong><span>Safety approval is separate from legitimacy and eligibility. No personal information is entered from this screen.</span></div><OpportunityTable initial={data.items} /></> : <ApiUnavailable />}</div>;
}
