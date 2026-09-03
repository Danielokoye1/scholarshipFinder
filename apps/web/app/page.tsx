import { ApiUnavailable } from "@/components/api-unavailable";
import { AutomationControl } from "@/components/automation-control";
import { EmptyState } from "@/components/empty-state";
import { PageHeading } from "@/components/page-heading";
import { api } from "@/lib/api";

const currency = new Intl.NumberFormat("en-US", { style: "currency", currency: "USD", maximumFractionDigits: 0 });

export default async function DashboardPage() {
  const data = await api.dashboard().catch(() => null);
  if (!data) return <div className="page"><PageHeading eyebrow="Overview" title="Dashboard" description="Your local scholarship operations at a glance." /><ApiUnavailable /></div>;
  const metrics = [
    ["Opportunities tracked", data.metrics.opportunities_tracked.toLocaleString()],
    ["Likely eligible", data.metrics.likely_eligible.toLocaleString()],
    ["Needs information", data.metrics.needs_information.toLocaleString()],
    ["Ineligible filtered", data.metrics.ineligible_filtered.toLocaleString()],
    ["Dry runs completed", data.metrics.dry_runs_completed.toLocaleString()],
    ["Applications submitted", data.metrics.applications_submitted.toLocaleString()],
    ["Potential awards", currency.format(data.metrics.potential_awards_cents / 100)],
    ["Applications this week", data.metrics.applications_this_week.toLocaleString()],
    ["Need your attention", data.metrics.need_attention.toLocaleString()],
    ["Awaiting decision", data.metrics.awaiting_decision.toLocaleString()],
    ["Awards won", data.metrics.awards_won.toLocaleString()],
    ["Total won", currency.format(data.metrics.total_won_cents / 100)],
  ];

  return (
    <div className="page">
      <PageHeading eyebrow="Overview" title="Dashboard" description="Your local scholarship operations at a glance." action={<AutomationControl initial={data.settings} />} />
      {data.settings.operating_mode === "discovery_only" ? <div className="alert info"><strong>Discovery-only safety mode</strong><span>Application preparation and submission are disabled.</span></div> : null}
      <section className="metrics" aria-label="Application metrics">{metrics.map(([label, value]) => <div className="metric" key={label}><span>{label}</span><strong>{value}</strong></div>)}</section>
      <div className="dashboard-grid">
        <section className="panel attention-panel"><div className="panel-header"><div><h2>Needs your attention</h2><p>Blocking actions ordered by urgency</p></div><span className="count">{data.attention.length}</span></div>{data.attention.length ? <ul className="item-list">{data.attention.map((task) => <li key={task.id}><div><span className="badge warning">{task.category}</span><strong>{task.title}</strong><p>{task.required_action}</p></div>{task.deadline ? <time>{new Date(task.deadline).toLocaleDateString()}</time> : null}</li>)}</ul> : <EmptyState title="You’re all caught up" detail="No tasks currently need your input." />}</section>
        <section className="panel"><div className="panel-header"><div><h2>Upcoming deadlines</h2><p>Next 30 days</p></div></div>{data.upcoming_deadlines.length ? <ul className="item-list">{data.upcoming_deadlines.map((item) => <li key={item.id}><div><strong>{item.name}</strong><p>{item.provider ?? "Provider not recorded"}</p></div><time>{new Date(item.deadline).toLocaleDateString()}</time></li>)}</ul> : <EmptyState title="No upcoming deadlines" detail="Deadlines appear here after opportunities are added." />}</section>
        <section className="panel activity-panel"><div className="panel-header"><div><h2>System activity</h2><p>Persistent local audit events</p></div></div>{data.activity.length ? <ul className="activity-list">{data.activity.map((event) => <li key={event.id}><time>{new Date(event.created_at).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}</time><span className={`activity-marker ${event.severity}`} /><p>{event.message}</p></li>)}</ul> : <EmptyState title="No activity yet" detail="System events will be recorded here as they happen." />}</section>
      </div>
    </div>
  );
}
