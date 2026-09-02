"use client";

import { FormEvent, useState } from "react";
import { api } from "@/lib/api";
import type { DomainPolicy } from "@/lib/types";

export function SafetySettings({ initial }: { initial: DomainPolicy[] }) {
  const [policies, setPolicies] = useState(initial);
  const [domain, setDomain] = useState("");
  const [decision, setDecision] = useState<"approved" | "blocked">("approved");
  const [notes, setNotes] = useState("");
  const [message, setMessage] = useState("");
  const [busy, setBusy] = useState(false);

  async function submit(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setMessage("");
    try {
      const saved = await api.setDomainPolicy({ domain, decision, notes });
      setPolicies((current) => [...current.filter((item) => item.id !== saved.id), saved].sort((a, b) => a.domain.localeCompare(b.domain)));
      setDomain("");
      setNotes("");
      setMessage(`${saved.domain} marked ${saved.decision}. Reassess affected workflows explicitly.`);
    } catch (caught) {
      setMessage(caught instanceof Error ? caught.message : "Could not save domain policy");
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="panel settings-panel">
      <div className="panel-header"><div><h2>Application-domain safety</h2><p>Default deny: each exact destination requires a local decision</p></div></div>
      <div className="safety-callout"><strong>Approval is not a guarantee.</strong><p>Only approve a hostname after independently confirming it belongs to the scholarship provider. Sensitive data, payment requests, insecure URLs, and suspicious destinations still override approval.</p></div>
      <form className="domain-form" onSubmit={submit}>
        <label>Hostname<input required value={domain} onChange={(event) => setDomain(event.target.value)} placeholder="apply.example.org" /></label>
        <label>Decision<select value={decision} onChange={(event) => setDecision(event.target.value as "approved" | "blocked")}><option value="approved">Approve</option><option value="blocked">Block</option></select></label>
        <label className="notes-field">Review notes<input required minLength={3} value={notes} onChange={(event) => setNotes(event.target.value)} placeholder="How you verified ownership or why you blocked it" /></label>
        <button className={`button ${decision === "blocked" ? "danger" : "primary"}`} disabled={busy}>{busy ? "Saving…" : "Save local decision"}</button>
        {message ? <p className="form-message">{message}</p> : null}
      </form>
      {policies.length ? <div className="table-scroll"><table><thead><tr><th>Domain</th><th>Decision</th><th>Notes</th><th>Updated</th></tr></thead><tbody>{policies.map((policy) => <tr key={policy.id}><td className="mono">{policy.domain}</td><td><span className={`badge ${policy.decision}`}>{policy.decision}</span></td><td>{policy.notes}</td><td>{new Date(policy.updated_at).toLocaleDateString()}</td></tr>)}</tbody></table></div> : <div className="empty-state compact"><span>!</span><strong>No approved domains</strong><p>Every application remains in review until you add a local decision.</p></div>}
    </section>
  );
}
