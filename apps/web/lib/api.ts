import type {
  ApplicationDetail,
  ApplicationList,
  BrowserRun,
  DryRunFill,
  DashboardData,
  DocumentRecord,
  DomainPolicy,
  ManualTask,
  PrioritySettings,
  ProfileField,
  SafetyAssessment,
  ScholarshipDetail,
  ScholarshipList,
  Settings,
  ValidationSnapshot,
} from "./types";

export const API_URL =
  process.env.NEXT_PUBLIC_SCHOLARSHIP_FINDER_API_URL ?? "http://127.0.0.1:8217";

async function readJson<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_URL}${path}`, { cache: "no-store", ...init });
  if (!response.ok) {
    const body = await response.json().catch(() => null);
    throw new Error(body?.detail ?? `Request failed (${response.status})`);
  }
  return response.json() as Promise<T>;
}

export const api = {
  dashboard: () => readJson<DashboardData>("/api/dashboard"),
  profile: () => readJson<ProfileField[]>("/api/profile"),
  documents: () => readJson<DocumentRecord[]>("/api/documents"),
  scholarships: () => readJson<ScholarshipList>("/api/scholarships"),
  scholarship: (id: string) => readJson<ScholarshipDetail>(`/api/scholarships/${id}`),
  createApplication: (scholarshipId: string) =>
    readJson<ApplicationDetail>("/api/applications", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ scholarship_id: scholarshipId }),
    }),
  applications: () => readJson<ApplicationList>("/api/applications"),
  application: (id: string) => readJson<ApplicationDetail>(`/api/applications/${id}`),
  reassessApplication: (id: string) =>
    readJson<ApplicationDetail>(`/api/applications/${id}/reassess-safety`, { method: "POST" }),
  inspectApplication: (id: string) =>
    readJson<BrowserRun>(`/api/applications/${id}/inspect`, { method: "POST" }),
  dryRunFill: (id: string) =>
    readJson<DryRunFill>(`/api/applications/${id}/dry-run-fill`, { method: "POST" }),
  validateSubmission: (id: string) =>
    readJson<ValidationSnapshot>(`/api/applications/${id}/validate-submission`, { method: "POST" }),
  tasks: () => readJson<ManualTask[]>("/api/tasks"),
  updateTask: (id: string, status: "resolved" | "dismissed") =>
    readJson<ManualTask>(`/api/tasks/${id}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ status }),
    }),
  safetyAssessment: (scholarshipId: string) =>
    readJson<SafetyAssessment | null>(`/api/safety/scholarships/${scholarshipId}`),
  domainPolicies: () => readJson<DomainPolicy[]>("/api/safety/domains"),
  setDomainPolicy: (body: { domain: string; decision: "approved" | "blocked"; notes: string }) =>
    readJson<DomainPolicy>("/api/safety/domains", {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    }),
  prioritySettings: () => readJson<PrioritySettings>("/api/priority/settings"),
  updatePrioritySettings: (body: Omit<PrioritySettings, "updated_at">) =>
    readJson<PrioritySettings>("/api/priority/settings", {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    }),
  settings: () => readJson<Settings>("/api/system/settings"),
  systemAction: (action: string) =>
    readJson<Settings>(`/api/system/${action}`, { method: "POST" }),
  updateSettings: (body: Partial<Settings>) =>
    readJson<Settings>("/api/system/settings", {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    }),
  updateProfile: (field: string, body: { value: unknown; status: string; source: string | null }) =>
    readJson<ProfileField>(`/api/profile/${field}`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    }),
  uploadDocument: (body: FormData) =>
    readJson<DocumentRecord>("/api/documents", { method: "POST", body }),
  approveDocument: (id: string, allowed: boolean) =>
    readJson<DocumentRecord>(`/api/documents/${id}/approval`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ auto_upload_allowed: allowed }),
    }),
};
