import Link from "next/link";
import { ApiUnavailable } from "@/components/api-unavailable";
import { PageHeading } from "@/components/page-heading";
import { api } from "@/lib/api";

const money = new Intl.NumberFormat("en-US", { style: "currency", currency: "USD", maximumFractionDigits: 0 });
const label = (value: string) => value.replaceAll("_", " ");

export default async function ApplicationsPage() {
  const data = await api.applications().catch(() => null);
  return <div className="page"><PageHeading eyebrow="Workflow" title="Applications" description="Stateful application records with safety status, priority, and an immutable event trail." />{data ? <section className="panel table-panel">{data.items.length ? <div className="table-scroll"><table><thead><tr><th>Scholarship</th><th>Workflow state</th><th>Safety</th><th>Award</th><th>Deadline</th><th>Priority</th><th /></tr></thead><tbody>{data.items.map((item) => <tr key={item.id}><td><strong>{item.scholarship_name}</strong><small>{item.provider ?? "Provider not recorded"}</small></td><td><span className="badge">{label(item.status)}</span></td><td><span className={`badge ${item.safety_status}`}>{label(item.safety_status)}</span></td><td>{item.award_max_cents == null ? "—" : money.format(item.award_max_cents / 100)}</td><td>{item.deadline ? new Date(item.deadline).toLocaleDateString() : "—"}</td><td><strong>{item.priority_score.toFixed(1)}</strong></td><td><Link className="text-link" href={`/applications/${item.id}`}>Open</Link></td></tr>)}</tbody></table></div> : <div className="empty-state"><span>0</span><strong>No application workflows</strong><p>Create one from an opportunity. The first action is a safety and eligibility check—not form filling.</p></div>}</section> : <ApiUnavailable />}</div>;
}
