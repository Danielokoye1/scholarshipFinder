import { ApiUnavailable } from "@/components/api-unavailable";
import { AutomationControl } from "@/components/automation-control";
import { PageHeading } from "@/components/page-heading";
import { SettingsPanel } from "@/components/settings-panel";
import { SafetySettings } from "@/components/safety-settings";
import { PrioritySettingsPanel } from "@/components/priority-settings";
import { api } from "@/lib/api";

export default async function SystemPage() {
  const [settings, policies, priority] = await Promise.all([api.settings().catch(() => null), api.domainPolicies().catch(() => null), api.prioritySettings().catch(() => null)]);
  return <div className="page"><PageHeading eyebrow="Controls" title="System" description="Control local automation, application-domain decisions, and transparent priority weights." action={settings ? <AutomationControl initial={settings} /> : undefined} />{settings && policies && priority ? <><div className="safety-strip"><div><span>Data location</span><strong>Repository local</strong></div><div><span>External browser</span><strong>Read-only inspection</strong></div><div><span>Preparation</span><strong>Offline fill + validation</strong></div><div><span>Live / cloud</span><strong>Locked / disconnected</strong></div></div><SafetySettings initial={policies} /><PrioritySettingsPanel initial={priority} /><SettingsPanel initial={settings} /></> : <ApiUnavailable />}</div>;
}
