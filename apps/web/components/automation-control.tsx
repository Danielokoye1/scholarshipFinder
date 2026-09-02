"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { api } from "@/lib/api";
import type { Settings } from "@/lib/types";

export function AutomationControl({ initial }: { initial: Settings }) {
  const router = useRouter();
  const [settings, setSettings] = useState(initial);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  async function run(action: string) {
    setBusy(true);
    setError("");
    try {
      setSettings(await api.systemAction(action));
      router.refresh();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "The action failed");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="automation-control">
      <div className="status-copy">
        <span className={`status-dot ${settings.automation_status}`} />
        <span>
          <small>Automation</small>
          <strong>{settings.automation_status}</strong>
        </span>
      </div>
      {settings.emergency_stop ? (
        <button className="button secondary" disabled={busy} onClick={() => run("clear-emergency-stop")}>Clear stop</button>
      ) : settings.automation_status === "running" ? (
        <button className="button secondary" disabled={busy} onClick={() => run("pause")}>Pause</button>
      ) : (
        <button className="button secondary" disabled={busy} onClick={() => run("resume")}>Resume</button>
      )}
      <button className="button danger" disabled={busy || settings.emergency_stop} onClick={() => run("emergency-stop")}>Emergency stop</button>
      {error ? <span className="inline-error">{error}</span> : null}
    </div>
  );
}
