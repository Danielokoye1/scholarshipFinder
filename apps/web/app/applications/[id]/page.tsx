import Link from "next/link";
import { notFound } from "next/navigation";
import { ApiUnavailable } from "@/components/api-unavailable";
import { DryRunFillButton } from "@/components/dry-run-fill-button";
import { InspectApplicationButton } from "@/components/inspect-application-button";
import { PageHeading } from "@/components/page-heading";
import { ReassessSafetyButton } from "@/components/reassess-safety-button";
import { api } from "@/lib/api";

const label = (value: string) => value.replaceAll("_", " ");

function dispositionClass(value: string) {
  if (value === "auto_answerable") return "verified";
  if (value === "blocked_sensitive") return "blocked";
  return "warning";
}

export default async function ApplicationDetailPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  let application;
  try {
    application = await api.application(id);
  } catch (error) {
    if (error instanceof Error && error.message === "Application not found") notFound();
    return <div className="page"><PageHeading title="Application" description="Could not load this local workflow." /><ApiUnavailable /></div>;
  }
  const assessment = application.current_safety_assessment;
  const run = application.latest_inspection;
  const fill = application.latest_fill;
  const canInspect = application.status === "ready_to_apply" && application.safety_status === "approved" && application.eligibility_status === "eligible";
  const canFill = canInspect && run?.status === "completed" && run.detected_barriers.length === 0;

  return <div className="page detail-page">
    <PageHeading eyebrow="Application workflow" title={application.scholarship_name} description={`${application.provider ?? "Provider not recorded"} · version ${application.version}`} action={<ReassessSafetyButton applicationId={application.id} />} />
    <div className={`safety-banner ${application.safety_status}`}>
      <div><span className="badge-label">Safety gate</span><strong>{label(application.safety_status)}</strong><p>{application.safety_status === "approved" ? "Phase 5 may test verified mappings offline but cannot enter data on the destination." : "Browser inspection and personal data use are locked."}</p></div>
      <div><span className="badge-label">Assessment</span><p>{assessment?.application_domain ?? "No verified destination"}</p>{assessment?.reasons.length ? <ul>{assessment.reasons.map((reason) => <li key={reason}>{reason}</li>)}</ul> : null}</div>
    </div>
    <div className="application-stats"><div><span>State</span><strong>{label(application.status)}</strong></div><div><span>Eligibility</span><strong>{label(application.eligibility_status)}</strong></div><div><span>Priority</span><strong>{application.priority_score.toFixed(1)}</strong></div><div><span>Form readiness</span><strong>{run ? `${run.automatable_percent.toFixed(0)}%` : "Not inspected"}</strong></div></div>
    {application.safety_status !== "approved" ? <div className="alert error"><strong>Do not enter personal information</strong><span>Review the exact destination independently, save a domain decision under <Link href="/system">System</Link>, then reassess here.</span></div> : <div className="alert info"><strong>No live-site filling</strong><span>Inspection remains read-only. Fill tests run on a locally generated form with networking disabled, and live submission remains hard-locked.</span></div>}

    <section className="panel inspection-panel">
      <div className="panel-header"><div><h2>Application form plan</h2><p>Labels and provenance only—profile values are never included</p></div><InspectApplicationButton applicationId={application.id} enabled={canInspect} /></div>
      {run ? <>
        <div className="inspection-summary"><div><span>Run status</span><strong className={`status-text ${run.status}`}>{label(run.status)}</strong></div><div><span>Fields found</span><strong>{run.field_count}</strong></div><div><span>Required</span><strong>{run.required_field_count}</strong></div><div><span>Deterministically answerable</span><strong>{run.automatable_field_count}</strong></div><div><span>Inspected</span><strong>{new Date(run.started_at).toLocaleString()}</strong></div></div>
        {run.error_message ? <div className="alert error inspection-alert"><strong>Inspection stopped</strong><span>{run.error_message}</span></div> : null}
        {run.detected_barriers.length ? <div className="barrier-row"><span>Manual checkpoints</span>{run.detected_barriers.map((barrier) => <span className="badge warning" key={barrier}>{label(barrier)}</span>)}</div> : null}
        {run.fields.length ? <div className="table-scroll"><table><thead><tr><th>Form field</th><th>Required</th><th>Profile mapping</th><th>Disposition</th><th>Reason</th></tr></thead><tbody>{run.fields.map((field) => <tr key={field.id}><td><strong>{field.label}</strong><small>{field.tag_name} · {field.input_type}</small></td><td>{field.required ? "Yes" : "No"}</td><td>{field.profile_field_key ? <><span className="mono">{field.profile_field_key}</span><small>{(field.mapping_confidence * 100).toFixed(0)}% mapping · {field.profile_status ?? "unknown"}</small></> : "—"}</td><td><span className={`badge ${dispositionClass(field.disposition)}`}>{label(field.disposition)}</span></td><td className="field-reason">{field.reason}</td></tr>)}</tbody></table></div> : <div className="empty-state compact"><span>0</span><strong>No form fields recorded</strong><p>{run.status === "completed" ? "The page may not contain a standard application form." : "Review the inspection error and destination."}</p></div>}
        <div className="inspection-evidence"><span>Final destination</span><code>{run.final_url ?? run.start_url}</code><span>Page hash</span><code>{run.page_content_hash ?? "Unavailable"}</code></div>
      </> : <div className="empty-state"><span>⌕</span><strong>Form not inspected</strong><p>Once safety and eligibility are approved, run a fresh read-only inspection to identify required fields and manual checkpoints.</p></div>}
    </section>

    <section className="panel inspection-panel">
      <div className="panel-header"><div><h2>Offline filling evidence</h2><p>Hashes and verified provenance only—answer values are not copied into this record</p></div><DryRunFillButton applicationId={application.id} enabled={canFill} /></div>
      {fill ? <>
        <div className="inspection-summary"><div><span>Run status</span><strong className={`status-text ${fill.status}`}>{label(fill.status)}</strong></div><div><span>Scope</span><strong>{label(fill.execution_scope)}</strong></div><div><span>Fields verified</span><strong>{fill.filled_field_count}</strong></div><div><span>Skipped</span><strong>{fill.skipped_field_count}</strong></div><div><span>Completed</span><strong>{new Date(fill.started_at).toLocaleString()}</strong></div></div>
        {fill.errors.length ? <div className="alert error inspection-alert"><strong>Dry run stopped</strong><span>{fill.errors[0].message}</span></div> : null}
        {fill.fields.length ? <div className="table-scroll"><table><thead><tr><th>Form field</th><th>Canonical source</th><th>Provenance</th><th>Result</th><th>Value evidence</th></tr></thead><tbody>{fill.fields.map((field) => <tr key={field.id}><td><strong>{field.label}</strong><small>Field {field.ordinal + 1}</small></td><td><span className="mono">{field.profile_field_key}</span><small>{field.profile_status}</small></td><td>{field.source_reference}<small>Profile checked {new Date(field.profile_updated_at).toLocaleString()}</small></td><td><span className="badge verified">{field.result}</span></td><td><span className="mono">sha256:{field.value_hash.slice(0, 12)}…</span><small>{field.value_type}; raw value not retained here</small></td></tr>)}</tbody></table></div> : null}
        <div className="inspection-evidence"><span>Manifest hash</span><code>{fill.manifest_hash ?? "Unavailable"}</code><span>Source page hash</span><code>{fill.source_page_hash}</code></div>
      </> : <div className="empty-state"><span>◇</span><strong>No offline fill evidence</strong><p>Switch System to Dry Run, enable Application preparation, and complete a barrier-free inspection first.</p></div>}
    </section>

    <div className="detail-grid"><section className="panel"><div className="panel-header"><div><h2>Action items</h2><p>Manual decisions associated with this workflow</p></div></div>{application.tasks.length ? <ul className="item-list">{application.tasks.map((task) => <li key={task.id}><div><span className={`badge ${task.status === "open" ? "warning" : "verified"}`}>{task.status}</span><strong>{task.title}</strong><p>{task.required_action}</p></div></li>)}</ul> : <div className="empty-state compact"><span>✓</span><strong>No tasks</strong></div>}</section>
      <section className="panel"><div className="panel-header"><div><h2>External destination</h2><p>Never opened automatically</p></div></div><div className="panel-copy">{application.application_url ? <><p className="mono break-word">{application.application_url}</p><a className="text-link" href={application.application_url} target="_blank" rel="noreferrer noopener">Open manually in a new tab ↗</a></> : <p>No application URL has been verified.</p>}</div></section></div>
    <section className="panel"><div className="panel-header"><div><h2>State history</h2><p>Append-only workflow events</p></div></div><ol className="timeline">{application.events.map((event) => <li key={event.id}><span className="timeline-dot" /><div><strong>{label(event.to_status)}</strong><p>{event.reason}</p><small>{new Date(event.created_at).toLocaleString()} · {event.actor}</small></div></li>)}</ol></section>
    <Link className="text-link" href="/applications">← Back to applications</Link>
  </div>;
}
