"use client";

import { FormEvent, useState } from "react";
import { api } from "@/lib/api";
import type { DocumentRecord } from "@/lib/types";

function formatBytes(bytes: number) {
  if (bytes < 1024 * 1024) return `${Math.ceil(bytes / 1024)} KB`;
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
}

export function DocumentManager({ initial }: { initial: DocumentRecord[] }) {
  const [documents, setDocuments] = useState(initial);
  const [message, setMessage] = useState("");

  async function upload(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setMessage("");
    const form = new FormData(event.currentTarget);
    try {
      const saved = await api.uploadDocument(form);
      setDocuments((current) => [saved, ...current]);
      event.currentTarget.reset();
      setMessage("Document added. Automatic upload remains disabled.");
    } catch (reason) {
      setMessage(reason instanceof Error ? reason.message : "Upload failed");
    }
  }

  async function toggle(item: DocumentRecord) {
    try {
      const updated = await api.approveDocument(item.id, !item.auto_upload_allowed);
      setDocuments((current) => current.map((document) => document.id === item.id ? updated : document));
    } catch (reason) {
      setMessage(reason instanceof Error ? reason.message : "Approval update failed");
    }
  }

  return (
    <>
      <section className="panel">
        <div className="panel-header"><div><h2>Add a document</h2><p>Files stay in the local vault. Approval is always off on upload.</p></div></div>
        <form className="form-grid upload-form" onSubmit={upload}>
          <label>File<input name="file" type="file" accept=".pdf,.doc,.docx,.txt,.png,.jpg,.jpeg" required /></label>
          <label>Document type<select name="document_type" defaultValue="resume"><option value="resume">Resume</option><option value="transcript">Transcript</option><option value="enrollment-verification">Enrollment verification</option><option value="proof-of-residency">Proof of residency</option><option value="financial-aid">Financial aid</option><option value="other">Other</option></select></label>
          <label>Version<input name="version" defaultValue="1" /></label>
          <button className="button primary" type="submit">Add to vault</button>
          {message ? <p className="form-message" role="status">{message}</p> : null}
        </form>
      </section>
      <section className="panel table-panel">
        <div className="panel-header"><div><h2>Document vault</h2><p>{documents.length} stored documents</p></div></div>
        {documents.length ? <div className="table-scroll"><table><thead><tr><th>Document</th><th>Type</th><th>Version</th><th>Size</th><th>Checksum</th><th>Auto-upload</th></tr></thead><tbody>
          {documents.map((item) => <tr key={item.id}><td><strong>{item.original_filename}</strong><small>{new Date(item.created_at).toLocaleDateString()}</small></td><td>{item.document_type}</td><td>{item.version}</td><td>{formatBytes(item.size_bytes)}</td><td className="mono checksum" title={item.sha256}>{item.sha256.slice(0, 12)}…</td><td><button className={`toggle ${item.auto_upload_allowed ? "on" : ""}`} aria-pressed={item.auto_upload_allowed} onClick={() => toggle(item)}><span />{item.auto_upload_allowed ? "Approved" : "Not approved"}</button></td></tr>)}
        </tbody></table></div> : <div className="empty-state"><span>—</span><strong>No documents in the vault</strong><p>Upload a document to store its metadata and integrity checksum.</p></div>}
      </section>
    </>
  );
}

