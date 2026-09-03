"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { api } from "@/lib/api";
import type { Settings } from "@/lib/types";

const toggles: Array<[keyof Settings, string, string]> = [
  ["discovery_enabled", "Discovery", "Search approved sources on a schedule"],
  ["eligibility_enabled", "Eligibility checking", "Evaluate extracted rules against verified data"],
  ["preparation_enabled", "Application preparation", "Allow inspection, offline filling, and validation in Dry Run mode"],
  ["automatic_submission_enabled", "Automatic submission", "Safety-gated until the controlled-submission phase"],
  ["email_monitoring_enabled", "Email monitoring", "Gmail identified; read-only OAuth is not connected yet"],
];

export function SettingsPanel({ initial }: { initial: Settings }) {
  const router = useRouter();
  const [settings, setSettings] = useState(initial);
  const [message, setMessage] = useState("");

  async function update(key: keyof Settings, value: boolean | string) {
    setMessage("");
    try {
      setSettings(await api.updateSettings({ [key]: value }));
      router.refresh();
    } catch (reason) {
      setMessage(reason instanceof Error ? reason.message : "Setting could not be updated");
    }
  }

  return (
    <section className="panel settings-panel">
      <div className="panel-header"><div><h2>Automation permissions</h2><p>Capabilities are deny-by-default and stored locally.</p></div></div>
      <div className="setting-row">
        <div><strong>Operating mode</strong><p>Live autonomous mode is not available in this phase.</p></div>
        <select value={settings.operating_mode} onChange={(event) => update("operating_mode", event.target.value)}><option value="discovery_only">Discovery only</option><option value="dry_run">Dry run</option><option value="assisted">Assisted</option><option value="autonomous" disabled>Autonomous — locked</option></select>
      </div>
      {toggles.map(([key, title, detail]) => {
        const locked = key === "automatic_submission_enabled" || key === "email_monitoring_enabled";
        return <div className="setting-row" key={key}><div><strong>{title}</strong><p>{detail}</p></div><button className={`toggle ${settings[key] ? "on" : ""}`} disabled={locked} aria-pressed={Boolean(settings[key])} onClick={() => update(key, !settings[key])}><span />{locked ? "Unavailable" : settings[key] ? "On" : "Off"}</button></div>;
      })}
      {message ? <div className="alert error">{message}</div> : null}
    </section>
  );
}
