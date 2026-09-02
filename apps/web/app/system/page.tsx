import { ApiUnavailable } from "@/components/api-unavailable";
import { AutomationControl } from "@/components/automation-control";
import { PageHeading } from "@/components/page-heading";
import { SettingsPanel } from "@/components/settings-panel";
import { SafetySettings } from "@/components/safety-settings";
import { PrioritySettingsPanel } from "@/components/priority-settings";
import { api } from "@/lib/api";

export default async function SystemPage() {
  const [settings, policies, priority] = await Promise.all([api.settings().catch(() => null), api.domainPolicies().catch(() => null), api.prioritySettings().catch(() => null)]);
  return <div className="page"><PageHeading eyebrow="Controls" title="System" description="Control local automation, application-domain decisions, and transparent priority weights." action={settings ? <AutomationControl initial={settings} /> : undefined} />{settings && policies && priority ? <><div className="safety-strip"><div><span>Data location</span><strong>Repository local</strong></div><div><span>Browser</span><strong>Read-only inspection</strong></div><div><span>Filling</span><strong>Offline dry run only</strong></div><div><span>Live submission</span><strong>Phase 5 locked</strong></div></div><SafetySettings initial={policies} /><PrioritySettingsPanel initial={priority} /><SettingsPanel initial={settings} /></> : <ApiUnavailable />}</div>;
}
