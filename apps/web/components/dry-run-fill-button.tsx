"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { api } from "@/lib/api";

export function DryRunFillButton({
  applicationId,
  enabled,
}: {
  applicationId: string;
  enabled: boolean;
}) {
  const router = useRouter();
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");

  async function fillOffline() {
    setBusy(true);
    setMessage("");
    try {
      const run = await api.dryRunFill(applicationId);
      setMessage(
        run.status === "completed"
          ? `Verified ${run.filled_field_count} fields offline. No external form received data.`
          : run.errors[0]?.message ?? "Dry run stopped safely.",
      );
      router.refresh();
    } catch (caught) {
      setMessage(caught instanceof Error ? caught.message : "Offline dry run could not start");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="button-stack inspection-action">
      <button className="button primary" type="button" onClick={fillOffline} disabled={!enabled || busy}>
        {busy ? "Filling offline…" : "Run offline fill test"}
      </button>
      <span className="form-note">
        {enabled ? "Requires Dry Run mode and Preparation enabled in System." : "Complete a barrier-free inspection first."}
      </span>
      {message ? <span className="form-message">{message}</span> : null}
    </div>
  );
}
