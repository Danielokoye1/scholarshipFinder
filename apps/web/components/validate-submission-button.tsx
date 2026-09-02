"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { api } from "@/lib/api";

export function ValidateSubmissionButton({
  applicationId,
  enabled,
}: {
  applicationId: string;
  enabled: boolean;
}) {
  const router = useRouter();
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");

  async function validate() {
    setBusy(true);
    setMessage("");
    try {
      const snapshot = await api.validateSubmission(applicationId);
      setMessage(
        snapshot.status === "passed"
          ? "Dry-run validation passed. Live submission is still locked."
          : `${snapshot.blockers.length} blocking condition(s) were queued for review.`,
      );
      router.refresh();
    } catch (caught) {
      setMessage(caught instanceof Error ? caught.message : "Validation could not start");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="button-stack inspection-action">
      <button className="button primary" type="button" onClick={validate} disabled={!enabled || busy}>
        {busy ? "Validating…" : "Validate dry-run readiness"}
      </button>
      <span className="form-note">
        {enabled ? "Rechecks all safety evidence; cannot submit." : "Complete the offline fill without blockers first."}
      </span>
      {message ? <span className="form-message">{message}</span> : null}
    </div>
  );
}
