import { ApiUnavailable } from "@/components/api-unavailable";
import { DocumentManager } from "@/components/document-manager";
import { PageHeading } from "@/components/page-heading";
import { api } from "@/lib/api";

export default async function DocumentsPage() {
  const documents = await api.documents().catch(() => null);
  return <div className="page"><PageHeading eyebrow="Local vault" title="Documents" description="Sensitive files remain local and require explicit approval before any automated use." />{documents ? <DocumentManager initial={documents} /> : <ApiUnavailable />}</div>;
}

