import type { DashboardData, DocumentRecord, ProfileField, Settings } from "./types";

export const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8000";

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

