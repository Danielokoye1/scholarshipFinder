"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { api } from "@/lib/api";

export function ReassessSafetyButton({ applicationId }: { applicationId: string }) {
  const router = useRouter();
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");
  async function reassess() {
    setBusy(true);
    setMessage("");
    try {
      const application = await api.reassessApplication(applicationId);
      setMessage(`Safety is ${application.safety_status.replaceAll("_", " ")}.`);
      router.refresh();
    } catch (caught) {
      setMessage(caught instanceof Error ? caught.message : "Could not reassess");
    } finally {
      setBusy(false);
    }
  }
  return <div className="button-stack"><button className="button" type="button" onClick={reassess} disabled={busy}>{busy ? "Rechecking…" : "Reassess safety"}</button>{message ? <span className="form-note">{message}</span> : null}</div>;
}
