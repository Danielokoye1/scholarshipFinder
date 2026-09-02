"use client";

import { FormEvent, useState } from "react";
import { api } from "@/lib/api";
import type { PrioritySettings } from "@/lib/types";

const weightFields = [
  ["eligibility_weight", "Eligibility"],
  ["award_weight", "Award value"],
  ["urgency_weight", "Deadline urgency"],
  ["completion_weight", "Completion"],
  ["effort_weight", "Lower manual effort"],
] as const;

export function PrioritySettingsPanel({ initial }: { initial: PrioritySettings }) {
  const [settings, setSettings] = useState(initial);
  const [message, setMessage] = useState("");
  const [busy, setBusy] = useState(false);
  async function submit(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setMessage("");
    try {
      const body = {
        eligibility_weight: settings.eligibility_weight,
        award_weight: settings.award_weight,
        urgency_weight: settings.urgency_weight,
        completion_weight: settings.completion_weight,
        effort_weight: settings.effort_weight,
        award_reference_cents: settings.award_reference_cents,
        urgency_window_days: settings.urgency_window_days,
      };
      const saved = await api.updatePrioritySettings(body);
      setSettings(saved);
      setMessage("Priority weights saved and all records recalculated.");
    } catch (caught) {
      setMessage(caught instanceof Error ? caught.message : "Could not update priorities");
    } finally {
      setBusy(false);
    }
  }
  return (
    <section className="panel settings-panel">
      <div className="panel-header"><div><h2>Priority model</h2><p>Visible, user-controlled weights; no opaque ranking</p></div></div>
      <form className="priority-form" onSubmit={submit}>
        <div className="weight-grid">{weightFields.map(([key, label]) => <label key={key}>{label}<input type="number" min="0" max="1" step="0.05" value={settings[key]} onChange={(event) => setSettings((current) => ({ ...current, [key]: Number(event.target.value) }))} /></label>)}</div>
        <div className="weight-grid secondary"><label>Award reference, dollars<input type="number" min="1" value={settings.award_reference_cents / 100} onChange={(event) => setSettings((current) => ({ ...current, award_reference_cents: Number(event.target.value) * 100 }))} /></label><label>Urgency window, days<input type="number" min="1" max="365" value={settings.urgency_window_days} onChange={(event) => setSettings((current) => ({ ...current, urgency_window_days: Number(event.target.value) }))} /></label></div>
        <button className="button primary" disabled={busy}>{busy ? "Recalculating…" : "Save and recalculate"}</button>
        {message ? <p className="form-message">{message}</p> : null}
      </form>
    </section>
  );
}
