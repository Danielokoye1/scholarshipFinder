"use client";

import Link from "next/link";
import { useMemo, useState } from "react";
import type { ScholarshipSummary } from "@/lib/types";

const money = new Intl.NumberFormat("en-US", {
  style: "currency",
  currency: "USD",
  maximumFractionDigits: 0,
});

function label(value: string) {
  return value.replaceAll("_", " ");
}

export function OpportunityTable({ initial }: { initial: ScholarshipSummary[] }) {
  const [query, setQuery] = useState("");
  const [eligibility, setEligibility] = useState("all");
  const [safety, setSafety] = useState("all");
  const items = useMemo(() => {
    const term = query.trim().toLowerCase();
    return initial.filter((item) => {
      const matchesText = !term || `${item.canonical_name} ${item.provider ?? ""}`.toLowerCase().includes(term);
      return matchesText && (eligibility === "all" || item.eligibility_status === eligibility) && (safety === "all" || item.safety_status === safety);
    });
  }, [initial, query, eligibility, safety]);

  return (
    <section className="panel table-panel">
      <div className="filter-bar">
        <label>Search<input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Name or provider" /></label>
        <label>Eligibility<select value={eligibility} onChange={(event) => setEligibility(event.target.value)}><option value="all">All</option><option value="eligible">Eligible</option><option value="needs_information">Needs information</option><option value="ineligible">Ineligible</option></select></label>
        <label>Safety<select value={safety} onChange={(event) => setSafety(event.target.value)}><option value="all">All</option><option value="approved">Approved</option><option value="review_required">Review required</option><option value="blocked">Blocked</option></select></label>
        <span className="filter-count">{items.length} shown</span>
      </div>
      {items.length ? <div className="table-scroll"><table><thead><tr><th>Opportunity</th><th>Eligibility</th><th>Safety</th><th>Award</th><th>Deadline</th><th>Priority</th><th /></tr></thead><tbody>{items.map((item) => <tr key={item.id}><td><strong>{item.canonical_name}</strong><small>{item.provider ?? "Provider not recorded"}</small></td><td><span className={`badge ${item.eligibility_status === "eligible" ? "verified" : item.eligibility_status === "ineligible" ? "blocked" : "warning"}`}>{label(item.eligibility_status)}</span></td><td><span className={`badge ${item.safety_status}`}>{label(item.safety_status)}</span></td><td>{item.award_max_cents == null ? "—" : money.format(item.award_max_cents / 100)}</td><td>{item.deadline ? new Date(item.deadline).toLocaleDateString() : "Rolling / unknown"}</td><td><strong>{item.priority_score.toFixed(1)}</strong></td><td><Link className="text-link" href={`/opportunities/${item.id}`}>Review</Link></td></tr>)}</tbody></table></div> : <div className="empty-state"><span>0</span><strong>No matching opportunities</strong><p>Adjust the filters or ingest a scholarship through the local API.</p></div>}
    </section>
  );
}
