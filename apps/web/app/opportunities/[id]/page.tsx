import Link from "next/link";
import { notFound } from "next/navigation";
import { ApiUnavailable } from "@/components/api-unavailable";
import { CreateApplicationButton } from "@/components/create-application-button";
import { PageHeading } from "@/components/page-heading";
import { api } from "@/lib/api";

const money = new Intl.NumberFormat("en-US", { style: "currency", currency: "USD", maximumFractionDigits: 0 });
const label = (value: string) => value.replaceAll("_", " ");

export default async function OpportunityDetailPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  let item;
  try { item = await api.scholarship(id); } catch (error) {
    if (error instanceof Error && error.message === "Scholarship not found") notFound();
    return <div className="page"><PageHeading title="Opportunity" description="Could not load this local record." /><ApiUnavailable /></div>;
  }
  const assessment = await api.safetyAssessment(id).catch(() => null);
  return <div className="page detail-page"><PageHeading eyebrow="Opportunity review" title={item.canonical_name} description={item.provider ?? "Provider not recorded"} action={<CreateApplicationButton scholarshipId={item.id} />} />
    <div className={`safety-banner ${item.safety_status}`}><div><span className="badge-label">Safety</span><strong>{label(item.safety_status)}</strong><p>{assessment?.application_domain ? `Destination: ${assessment.application_domain}` : "No distinct application destination has been verified."}</p></div><div><span className="badge-label">Why</span>{assessment?.reasons.length ? <ul>{assessment.reasons.map((reason) => <li key={reason}>{reason}</li>)}</ul> : <p>No current assessment details.</p>}</div></div>
    <div className="detail-grid"><section className="panel"><div className="panel-header"><div><h2>Opportunity facts</h2><p>Captured from the recorded source</p></div></div><dl className="fact-list"><div><dt>Eligibility</dt><dd><span className={`badge ${item.eligibility_status === "eligible" ? "verified" : "warning"}`}>{label(item.eligibility_status)}</span></dd></div><div><dt>Legitimacy</dt><dd><span className={`badge ${item.legitimacy_status}`}>{label(item.legitimacy_status)}</span></dd></div><div><dt>Maximum award</dt><dd>{item.award_max_cents == null ? "Not recorded" : money.format(item.award_max_cents / 100)}</dd></div><div><dt>Deadline</dt><dd>{item.deadline ? new Date(item.deadline).toLocaleString() : item.deadline_type}</dd></div><div><dt>Priority score</dt><dd>{item.priority_score.toFixed(1)} / 100</dd></div></dl><div className="external-links"><a href={item.source_url} target="_blank" rel="noreferrer noopener">Open recorded source ↗</a>{item.application_url ? <a href={item.application_url} target="_blank" rel="noreferrer noopener">Inspect application destination ↗</a> : null}</div></section>
      <section className="panel"><div className="panel-header"><div><h2>Legitimacy signals</h2><p>Screening indicators, not a guarantee</p></div></div>{item.legitimacy_signals.length ? <ul className="plain-list">{item.legitimacy_signals.map((signal) => <li key={signal}>{signal}</li>)}</ul> : <p className="panel-copy">No signals were recorded.</p>}</section></div>
    <section className="panel"><div className="panel-header"><div><h2>Eligibility evidence</h2><p>Rules are grounded in captured source quotes</p></div></div>{item.rules.length ? <div className="table-scroll"><table><thead><tr><th>Requirement</th><th>Profile field</th><th>Result</th><th>Evidence</th></tr></thead><tbody>{item.rules.map((rule) => { const check = item.checks.find((candidate) => candidate.rule_id === rule.id); return <tr key={rule.id}><td><strong>{rule.requirement}</strong><small>{rule.operator} · {(rule.confidence * 100).toFixed(0)}% extraction confidence</small></td><td className="mono">{rule.field_key ?? "manual review"}</td><td><span className={`badge ${check?.result === "pass" ? "verified" : check?.result === "fail" ? "blocked" : "warning"}`}>{label(check?.result ?? "unknown")}</span></td><td><small className="quote">“{rule.source_quote ?? "No quote recorded"}”</small></td></tr>; })}</tbody></table></div> : <div className="empty-state compact"><span>?</span><strong>No eligibility rules recorded</strong><p>Review the source before treating this opportunity as a match.</p></div>}</section>
    <Link className="text-link" href="/opportunities">← Back to opportunities</Link>
  </div>;
}
