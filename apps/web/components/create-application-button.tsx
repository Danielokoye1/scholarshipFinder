"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { api } from "@/lib/api";

export function CreateApplicationButton({ scholarshipId }: { scholarshipId: string }) {
  const router = useRouter();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  async function create() {
    setBusy(true);
    setError("");
    try {
      const application = await api.createApplication(scholarshipId);
      router.push(`/applications/${application.id}`);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Could not create workflow");
      setBusy(false);
    }
  }

  return (
    <div className="button-stack">
      <button className="button primary" type="button" onClick={create} disabled={busy}>
        {busy ? "Checking safety…" : "Create safe workflow"}
      </button>
      {error ? <span className="form-error">{error}</span> : null}
    </div>
  );
}
