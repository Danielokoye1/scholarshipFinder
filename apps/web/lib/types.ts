export type Settings = {
  automation_status: "running" | "paused" | "stopped";
  operating_mode: "discovery_only" | "dry_run" | "assisted" | "autonomous";
  discovery_enabled: boolean;
  eligibility_enabled: boolean;
  preparation_enabled: boolean;
  automatic_submission_enabled: boolean;
  email_monitoring_enabled: boolean;
  emergency_stop: boolean;
  updated_at: string;
};

export type DashboardData = {
  metrics: {
    applications_submitted: number;
    potential_awards_cents: number;
    applications_this_week: number;
    need_attention: number;
    awaiting_decision: number;
    awards_won: number;
    total_won_cents: number;
  };
  settings: Settings;
  activity: Array<{
    id: number;
    event_type: string;
    message: string;
    severity: string;
    created_at: string;
  }>;
  attention: Array<{
    id: string;
    category: string;
    title: string;
    required_action: string;
    deadline: string | null;
  }>;
  upcoming_deadlines: Array<{
    id: string;
    name: string;
    provider: string | null;
    deadline: string;
    award_max_cents: number | null;
  }>;
};

export type ProfileField = {
  field_key: string;
  value: unknown;
  status: "verified" | "user_entered" | "unknown";
  source: string | null;
  last_verified_at: string | null;
  updated_at: string;
};

export type DocumentRecord = {
  id: string;
  original_filename: string;
  document_type: string;
  version: string;
  content_type: string | null;
  size_bytes: number;
  sha256: string;
  auto_upload_allowed: boolean;
  expires_at: string | null;
  created_at: string;
};

