"use client";

import Link from "next/link";
import { useState } from "react";
import { api } from "@/lib/api";
import type { ManualTask } from "@/lib/types";

export function ActionQueueList({ initial }: { initial: ManualTask[] }) {
  const [tasks, setTasks] = useState(initial);
  const [error, setError] = useState("");
  async function close(id: string, status: "resolved" | "dismissed") {
    setError("");
    try {
      await api.updateTask(id, status);
      setTasks((current) => current.filter((task) => task.id !== id));
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Could not update task");
    }
  }
  return (
    <section className="panel">
      <div className="panel-header"><div><h2>Open actions</h2><p>Highest priority first; every external link requires your click</p></div><span className="count">{tasks.length}</span></div>
      {error ? <div className="alert error queue-error">{error}</div> : null}
      {tasks.length ? <ul className="queue-list">{tasks.map((task) => <li key={task.id}><div className="queue-score"><strong>{task.priority_score.toFixed(0)}</strong><span>priority</span></div><div className="queue-copy"><span className={`badge ${task.category === "safety_review" ? "warning" : ""}`}>{task.category.replaceAll("_", " ")}</span><h3>{task.title}</h3><p>{task.required_action}</p><div className="queue-links">{task.application_id ? <Link href={`/applications/${task.application_id}`}>Open workflow</Link> : null}{task.scholarship_id ? <Link href={`/opportunities/${task.scholarship_id}`}>Review opportunity</Link> : null}{task.direct_url ? <a href={task.direct_url} target="_blank" rel="noreferrer noopener">Open external page ↗</a> : null}</div></div><div className="queue-actions">{task.deadline ? <time>{new Date(task.deadline).toLocaleDateString()}</time> : null}<button className="button" type="button" onClick={() => close(task.id, "resolved")}>Resolve</button><button className="button" type="button" onClick={() => close(task.id, "dismissed")}>Dismiss</button></div></li>)}</ul> : <div className="empty-state"><span>✓</span><strong>No open actions</strong><p>Safety reviews and missing-information requests will appear here.</p></div>}
    </section>
  );
}
