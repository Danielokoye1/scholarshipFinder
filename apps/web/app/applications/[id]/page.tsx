import Link from "next/link";
import { notFound } from "next/navigation";
import { ApiUnavailable } from "@/components/api-unavailable";
import { PageHeading } from "@/components/page-heading";
import { ReassessSafetyButton } from "@/components/reassess-safety-button";
import { api } from "@/lib/api";

const label = (value: string) => value.replaceAll("_", " ");

export default async function ApplicationDetailPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  let application;
  try { application = await api.application(id); } catch (error) {
    if (error instanceof Error && error.message === "Application not found") notFound();
    return <div className="page"><PageHeading title="Application" description="Could not load this local workflow." /><ApiUnavailable /></div>;
  }
  const assessment = application.current_safety_assessment;
  return <div className="page detail-page"><PageHeading eyebrow="Application workflow" title={application.scholarship_name} description={`${application.provider ?? "Provider not recorded"} · version ${application.version}`} action={<ReassessSafetyButton applicationId={application.id} />} />
    <div className={`safety-banner ${application.safety_status}`}><div><span className="badge-label">Safety gate</span><strong>{label(application.safety_status)}</strong><p>{application.safety_status === "approved" ? "Destination checks passed. Phase 3 still prevents all browser data entry." : "Personal data entry is locked."}</p></div><div><span className="badge-label">Assessment</span><p>{assessment?.application_domain ?? "No verified destination"}</p>{assessment?.reasons.length ? <ul>{assessment.reasons.map((reason) => <li key={reason}>{reason}</li>)}</ul> : null}</div></div>
    <div className="application-stats"><div><span>State</span><strong>{label(application.status)}</strong></div><div><span>Eligibility</span><strong>{label(application.eligibility_status)}</strong></div><div><span>Priority</span><strong>{application.priority_score.toFixed(1)}</strong></div><div><span>Completion</span><strong>{application.completion_percent.toFixed(0)}%</strong></div></div>
    {application.safety_status !== "approved" ? <div className="alert error"><strong>Do not enter personal information</strong><span>Review the exact destination independently, save a domain decision under <Link href="/system">System</Link>, then reassess here.</span></div> : <div className="alert info"><strong>Preparation remains locked</strong><span>This phase organizes work only. It does not open, fill, upload to, or submit any external form.</span></div>}
    <div className="detail-grid"><section className="panel"><div className="panel-header"><div><h2>Action items</h2><p>Manual decisions associated with this workflow</p></div></div>{application.tasks.length ? <ul className="item-list">{application.tasks.map((task) => <li key={task.id}><div><span className={`badge ${task.status === "open" ? "warning" : "verified"}`}>{task.status}</span><strong>{task.title}</strong><p>{task.required_action}</p></div></li>)}</ul> : <div className="empty-state compact"><span>✓</span><strong>No tasks</strong></div>}</section>
      <section className="panel"><div className="panel-header"><div><h2>External destination</h2><p>Never opened automatically</p></div></div><div className="panel-copy">{application.application_url ? <><p className="mono break-word">{application.application_url}</p><a className="text-link" href={application.application_url} target="_blank" rel="noreferrer noopener">Open manually in a new tab ↗</a></> : <p>No application URL has been verified.</p>}</div></section></div>
    <section className="panel"><div className="panel-header"><div><h2>State history</h2><p>Append-only workflow events</p></div></div><ol className="timeline">{application.events.map((event) => <li key={event.id}><span className="timeline-dot" /><div><strong>{label(event.to_status)}</strong><p>{event.reason}</p><small>{new Date(event.created_at).toLocaleString()} · {event.actor}</small></div></li>)}</ol></section>
    <Link className="text-link" href="/applications">← Back to applications</Link>
  </div>;
}
