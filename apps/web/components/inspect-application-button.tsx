"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { api } from "@/lib/api";

export function InspectApplicationButton({
  applicationId,
  enabled,
}: {
  applicationId: string;
  enabled: boolean;
}) {
  const router = useRouter();
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");

  async function inspect() {
    setBusy(true);
    setMessage("");
    try {
      const run = await api.inspectApplication(applicationId);
      setMessage(
        run.status === "completed"
          ? `Inspected ${run.field_count} fields without entering data.`
          : run.error_message ?? "Inspection stopped safely.",
      );
      router.refresh();
    } catch (caught) {
      setMessage(caught instanceof Error ? caught.message : "Inspection could not start");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="button-stack inspection-action">
      <button className="button primary" type="button" onClick={inspect} disabled={!enabled || busy}>
        {busy ? "Inspecting read-only…" : "Inspect application form"}
      </button>
      <span className="form-note">
        {enabled ? "Fresh isolated browser; no values, uploads, or clicks." : "Resolve safety and eligibility gates first."}
      </span>
      {message ? <span className="form-message">{message}</span> : null}
    </div>
  );
}
