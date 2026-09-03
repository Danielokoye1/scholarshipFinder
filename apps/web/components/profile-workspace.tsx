"use client";

import { FormEvent, useMemo, useState } from "react";
import { api } from "@/lib/api";
import type { ProfileOverview, ProfileReviewIssue, ProfileWorkspaceField } from "@/lib/types";

type DraftField = ProfileWorkspaceField & { displayValue: string };

function toDraft(overview: ProfileOverview): Record<string, DraftField> {
  return Object.fromEntries(
    overview.sections.flatMap((section) =>
      section.fields.map((field) => [
        field.field_key,
        { ...field, displayValue: field.value == null ? "" : String(field.value) },
      ]),
    ),
  );
}

function issueCount(issues: ProfileReviewIssue[], severity: ProfileReviewIssue["severity"]) {
  return issues.filter((issue) => issue.severity === severity).length;
}

export function ProfileWorkspace({ initial }: { initial: ProfileOverview }) {
  const [overview, setOverview] = useState(initial);
  const [draft, setDraft] = useState(() => toDraft(initial));
  const [message, setMessage] = useState("");
  const [saving, setSaving] = useState(false);
  const actionIssues = useMemo(
    () => overview.issues.filter((issue) => issue.severity !== "success"),
    [overview.issues],
  );

  function updateField(fieldKey: string, value: string) {
    setDraft((current) => ({
      ...current,
      [fieldKey]: {
        ...current[fieldKey],
        displayValue: value,
        status: value ? "user_entered" : "unknown",
        source: value ? "Manual profile review" : null,
        last_verified_at: null,
      },
    }));
    setMessage("");
  }

  function applySuggestion(issue: ProfileReviewIssue) {
    const fieldKey = issue.field_keys[0];
    if (!fieldKey || issue.suggested_value == null || !draft[fieldKey]) return;
    updateField(fieldKey, String(issue.suggested_value));
    document.getElementById(fieldKey)?.focus();
    setMessage("Suggestion added to the form. Review it, then save your profile.");
  }

  async function save(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSaving(true);
    setMessage("");
    try {
      const saved = await api.updateProfileOverview(
        Object.values(draft).map((field) => ({
          field_key: field.field_key,
          value: field.status === "unknown" ? null : field.displayValue,
          status: field.status,
          source: field.source,
        })),
      );
      setOverview(saved);
      setDraft(toDraft(saved));
      setMessage("Profile reviewed and saved locally. No application was submitted.");
    } catch (reason) {
      setMessage(reason instanceof Error ? reason.message : "Could not save the profile");
    } finally {
      setSaving(false);
    }
  }

  return (
    <form onSubmit={save}>
      <section className="profile-summary" aria-label="Profile health">
        <div><span>Complete</span><strong>{overview.completeness_percent}%</strong><small>{overview.important_fields_complete} of {overview.important_fields_total} important facts</small></div>
        <div><span>Needs correction</span><strong className={issueCount(overview.issues, "error") ? "danger-text" : ""}>{issueCount(overview.issues, "error")}</strong><small>Conflicts or invalid values</small></div>
        <div><span>Review suggested</span><strong>{issueCount(overview.issues, "warning")}</strong><small>Missing or uncertain facts</small></div>
        <div><span>Document checks</span><strong>{overview.document_checks.filter((item) => item.status === "readable").length}/{overview.document_checks.length}</strong><small>Readable locally</small></div>
      </section>

      <div className="alert info profile-privacy-note">
        <strong>Local profile intelligence</strong>
        <span>Fields are checked together with your readable local documents. Document text is not stored as a second profile, and your address is not sent to an outside verifier.</span>
      </div>

      {actionIssues.length ? (
        <section className="panel profile-review-panel">
          <div className="panel-header"><div><h2>Review before this profile is used</h2><p>The system flags conflicts and asks you to confirm; it does not guess.</p></div><span className="count">{actionIssues.length}</span></div>
          <div className="profile-issues">
            {actionIssues.map((issue) => (
              <article className={`profile-issue ${issue.severity}`} key={issue.code}>
                <span className={`issue-marker ${issue.severity}`} aria-hidden="true" />
                <div><strong>{issue.title}</strong><p>{issue.message}</p>{issue.evidence_sources.length ? <small>Evidence: {issue.evidence_sources.join(", ")}</small> : null}</div>
                {issue.requires_confirmation ? <button className="button" type="button" onClick={() => applySuggestion(issue)}>Use {String(issue.suggested_value)}</button> : null}
              </article>
            ))}
          </div>
        </section>
      ) : null}

      <div className="profile-section-grid">
        {overview.sections.map((section) => (
          <section className="panel profile-section" key={section.key}>
            <div className="panel-header"><div><h2>{section.title}</h2><p>{section.fields.filter((field) => draft[field.field_key]?.displayValue).length} of {section.fields.length} fields entered</p></div></div>
            <div className="profile-fields">
              {section.fields.map((field) => {
                const current = draft[field.field_key];
                return (
                  <label className="profile-field" key={field.field_key} htmlFor={field.field_key}>
                    <span className="profile-field-label">{field.label}{field.important ? <em>Recommended</em> : null}{field.sensitive ? <i>Private</i> : null}</span>
                    {field.options.length ? (
                      <select id={field.field_key} value={current.displayValue} onChange={(event) => updateField(field.field_key, event.target.value)}>
                        <option value="">Select…</option>
                        {field.options.map((option) => <option value={option} key={option}>{option}</option>)}
                      </select>
                    ) : (
                      <input
                        id={field.field_key}
                        type={field.input_type}
                        step={field.input_type === "number" ? "0.01" : undefined}
                        value={current.displayValue}
                        onChange={(event) => updateField(field.field_key, event.target.value)}
                        autoComplete={field.field_key.startsWith("address.") ? "off" : undefined}
                        spellCheck={["education.institution", "education.degree", "education.major", "education.minor", "identity.citizenship", "identity.national_origin", "identity.race_ethnicity", "identity.residency"].includes(field.field_key)}
                      />
                    )}
                    {field.help_text ? <small>{field.help_text}</small> : null}
                    <span className="field-provenance"><span className={`badge ${current.status}`}>{current.status.replace("_", " ")}</span>{current.source ? <span title={current.source}>{current.source}</span> : <span>Not provided</span>}</span>
                  </label>
                );
              })}
            </div>
          </section>
        ))}
      </div>

      <section className="panel document-intelligence">
        <div className="panel-header"><div><h2>Document intelligence</h2><p>Files are read locally only for corroboration.</p></div></div>
        <div className="document-checks">
          {overview.document_checks.map((item) => (
            <div key={item.document_id}><strong>{item.document_type} <span className="document-version">{item.version}</span></strong><span className={`badge ${item.status === "readable" ? "verified" : "warning"}`}>{item.is_latest ? "current · " : "history · "}{item.status.replace("_", " ")}</span><small>{item.page_count ? `${item.page_count} page${item.page_count === 1 ? "" : "s"}` : "Page count unavailable"}</small></div>
          ))}
        </div>
      </section>

      <div className="profile-save-bar">
        <div><strong>Nothing leaves this device</strong><span>Saving updates your local profile only. Application submission remains locked.</span>{message ? <p className="form-message" role="status">{message}</p> : null}</div>
        <button className="button primary" type="submit" disabled={saving}>{saving ? "Checking profile…" : "Review & save profile"}</button>
      </div>
    </form>
  );
}
