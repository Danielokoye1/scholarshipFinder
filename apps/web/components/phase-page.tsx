import { PageHeading } from "./page-heading";

export function PhasePage({ title, question, phase }: { title: string; question: string; phase: string }) {
  return <div className="page"><PageHeading eyebrow={phase} title={title} description={question} /><section className="panel"><div className="empty-state phase"><span>—</span><strong>Not enabled yet</strong><p>This workspace is intentionally limited to the Phase 1 foundation. No simulated records are shown.</p></div></section></div>;
}

