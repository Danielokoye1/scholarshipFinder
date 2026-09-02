"use client";

import { FormEvent, useState } from "react";
import { api } from "@/lib/api";
import type { ProfileField } from "@/lib/types";

export function ProfileEditor({ initial }: { initial: ProfileField[] }) {
  const [items, setItems] = useState(initial);
  const [message, setMessage] = useState("");

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setMessage("");
    const form = new FormData(event.currentTarget);
    const field = String(form.get("field")).trim();
    const rawValue = String(form.get("value")).trim();
    const status = String(form.get("status"));
    const source = String(form.get("source")).trim() || null;
    let value: unknown = rawValue;
    if (status === "unknown") value = null;
    try {
      const saved = await api.updateProfile(field, { value, status, source });
      setItems((current) => [...current.filter((item) => item.field_key !== field), saved].sort((a, b) => a.field_key.localeCompare(b.field_key)));
      event.currentTarget.reset();
      setMessage("Profile field saved.");
    } catch (reason) {
      setMessage(reason instanceof Error ? reason.message : "Could not save the field");
    }
  }

  return (
    <>
      <section className="panel">
        <div className="panel-header"><div><h2>Add or update a field</h2><p>Use dotted keys such as <code>education.gpa</code> or <code>contact.email</code>.</p></div></div>
        <form className="form-grid" onSubmit={submit}>
          <label>Field key<input name="field" pattern="[a-z][a-z0-9_]*(\.[a-z][a-z0-9_]*)*" required placeholder="education.institution" /></label>
          <label>Value<input name="value" placeholder="University name" /></label>
          <label>Status<select name="status" defaultValue="user_entered"><option value="user_entered">User entered</option><option value="verified">Verified</option><option value="unknown">Unknown</option></select></label>
          <label>Source<input name="source" defaultValue="Manual profile entry" /></label>
          <button className="button primary" type="submit">Save field</button>
          {message ? <p className="form-message" role="status">{message}</p> : null}
        </form>
      </section>
      <section className="panel table-panel">
        <div className="panel-header"><div><h2>Canonical profile</h2><p>{items.length} stored fields</p></div></div>
        {items.length ? (
          <div className="table-scroll"><table><thead><tr><th>Field</th><th>Value</th><th>Status</th><th>Source</th><th>Last verified</th></tr></thead><tbody>
            {items.map((item) => <tr key={item.field_key}><td className="mono">{item.field_key}</td><td>{item.value == null ? <span className="muted">Unknown</span> : String(item.value)}</td><td><span className={`badge ${item.status}`}>{item.status.replace("_", " ")}</span></td><td>{item.source ?? "—"}</td><td>{item.last_verified_at ? new Date(item.last_verified_at).toLocaleDateString() : "—"}</td></tr>)}
          </tbody></table></div>
        ) : <EmptyProfile />}
      </section>
    </>
  );
}

function EmptyProfile() {
  return <div className="empty-state"><span>—</span><strong>No profile data yet</strong><p>Add only information you know to be accurate. Unknown information should stay unknown.</p></div>;
}

