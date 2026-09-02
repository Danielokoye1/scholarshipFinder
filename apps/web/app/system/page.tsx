import { ApiUnavailable } from "@/components/api-unavailable";
import { AutomationControl } from "@/components/automation-control";
import { PageHeading } from "@/components/page-heading";
import { SettingsPanel } from "@/components/settings-panel";
import { api } from "@/lib/api";

export default async function SystemPage() {
  const settings = await api.settings().catch(() => null);
  return <div className="page"><PageHeading eyebrow="Controls" title="System" description="Control local automation capabilities and inspect the active safety posture." action={settings ? <AutomationControl initial={settings} /> : undefined} />{settings ? <><div className="safety-strip"><div><span>Network</span><strong>Localhost only</strong></div><div><span>Submission</span><strong>Safety locked</strong></div><div><span>Telemetry</span><strong>Disabled</strong></div><div><span>Mode</span><strong>{settings.operating_mode.replaceAll("_", " ")}</strong></div></div><SettingsPanel initial={settings} /></> : <ApiUnavailable />}</div>;
}

