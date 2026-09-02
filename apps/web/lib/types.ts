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

export type ProfileWorkspaceField = {
  field_key: string;
  label: string;
  value: unknown;
  status: "verified" | "user_entered" | "unknown";
  source: string | null;
  last_verified_at: string | null;
  input_type: string;
  options: string[];
  important: boolean;
  sensitive: boolean;
  help_text: string;
};

export type ProfileReviewIssue = {
  code: string;
  severity: "success" | "info" | "warning" | "error";
  title: string;
  message: string;
  field_keys: string[];
  evidence_sources: string[];
  suggested_value: unknown;
  requires_confirmation: boolean;
};

export type ProfileOverview = {
  completeness_percent: number;
  important_fields_complete: number;
  important_fields_total: number;
  sections: Array<{
    key: string;
    title: string;
    fields: ProfileWorkspaceField[];
  }>;
  issues: ProfileReviewIssue[];
  document_checks: Array<{
    document_id: string;
    document_type: string;
    version: string;
    is_latest: boolean;
    status: "readable" | "locked" | "no_text" | "missing" | "unsupported" | "too_large" | "unreadable";
    page_count: number | null;
  }>;
  external_address_verification: "not_performed";
  generated_at: string;
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

export type SafetyStatus = "approved" | "review_required" | "blocked";

export type ScholarshipSummary = {
  id: string;
  canonical_name: string;
  provider: string | null;
  source_url: string;
  application_url: string | null;
  award_min_cents: number | null;
  award_max_cents: number | null;
  deadline: string | null;
  deadline_timezone: string | null;
  deadline_type: string;
  legitimacy_status: "verified" | "likely_legitimate" | "review_required" | "blocked";
  legitimacy_score: number;
  eligibility_status: "eligible" | "probably_eligible" | "needs_information" | "ineligible";
  eligibility_score: number;
  automation_level: number;
  safety_status: SafetyStatus;
  priority_score: number;
  last_verified_at: string | null;
  created_at: string;
};

export type ScholarshipDetail = ScholarshipSummary & {
  description: string | null;
  award_description: string | null;
  raw_deadline_text: string | null;
  requirements: Record<string, unknown>;
  legitimacy_signals: string[];
  rules: Array<{
    id: string;
    requirement: string;
    field_key: string | null;
    operator: string;
    expected_value: unknown;
    confidence: number;
    needs_review: boolean;
    source_quote: string | null;
  }>;
  checks: Array<{
    id: string;
    rule_id: string;
    requirement: string;
    field_key: string | null;
    profile_value: unknown;
    result: "pass" | "fail" | "unknown" | "needs_verification";
    evidence: string;
    confidence: number;
    evaluation_run_id: string;
    is_current: boolean;
    evaluated_at: string;
  }>;
};

export type ScholarshipList = {
  items: ScholarshipSummary[];
  total: number;
  offset: number;
  limit: number;
};

export type SafetyAssessment = {
  id: string;
  scholarship_id: string;
  application_id: string | null;
  application_domain: string | null;
  status: SafetyStatus;
  score: number;
  reasons: string[];
  is_current: boolean;
  assessed_at: string;
};

export type ManualTask = {
  id: string;
  application_id: string | null;
  scholarship_id: string | null;
  category: string;
  title: string;
  required_action: string;
  status: "open" | "resolved" | "dismissed";
  direct_url: string | null;
  priority_score: number;
  deadline: string | null;
  resolved_at: string | null;
  created_at: string;
};

export type ApplicationSummary = {
  id: string;
  scholarship_id: string;
  scholarship_name: string;
  provider: string | null;
  award_max_cents: number | null;
  deadline: string | null;
  application_url: string | null;
  status: string;
  safety_status: SafetyStatus;
  automation_level: number;
  completion_percent: number;
  priority_score: number;
  manual_effort_score: number;
  submitted_at: string | null;
  version: number;
  updated_at: string;
};

export type ApplicationDetail = ApplicationSummary & {
  eligibility_status: ScholarshipSummary["eligibility_status"];
  current_safety_assessment: SafetyAssessment | null;
  latest_inspection: BrowserRun | null;
  latest_fill: DryRunFill | null;
  latest_validation: ValidationSnapshot | null;
  events: Array<{
    id: string;
    from_status: string | null;
    to_status: string;
    reason: string;
    actor: string;
    metadata: Record<string, unknown>;
    created_at: string;
  }>;
  tasks: ManualTask[];
};

export type FormFieldPlan = {
  id: string;
  ordinal: number;
  form_index: number;
  tag_name: string;
  input_type: string;
  label: string;
  required: boolean;
  disabled: boolean;
  autocomplete: string | null;
  profile_field_key: string | null;
  mapping_confidence: number;
  profile_status: string | null;
  disposition: "auto_answerable" | "missing_profile_data" | "manual_review" | "blocked_sensitive" | "not_applicable";
  reason: string;
};

export type BrowserRun = {
  id: string;
  application_id: string;
  status: "running" | "completed" | "blocked" | "failed";
  adapter: string;
  start_url: string;
  final_url: string | null;
  initial_domain: string;
  final_domain: string | null;
  redirect_chain: string[];
  page_title: string | null;
  response_status: number | null;
  page_content_hash: string | null;
  field_count: number;
  required_field_count: number;
  automatable_field_count: number;
  automatable_percent: number;
  detected_barriers: string[];
  blocked_requests: Array<{ url: string; category: string; reason: string }>;
  error_category: string | null;
  error_message: string | null;
  started_at: string;
  finished_at: string | null;
  fields: FormFieldPlan[];
};

export type FillFieldEvidence = {
  id: string;
  ordinal: number;
  label: string;
  profile_field_key: string;
  profile_status: "verified";
  source_reference: string;
  profile_updated_at: string;
  value_type: string;
  value_hash: string;
  result: "filled";
  reason: string;
};

export type DryRunFill = {
  id: string;
  application_id: string;
  browser_run_id: string;
  status: "running" | "completed" | "blocked" | "failed";
  execution_scope: "offline_synthetic";
  source_page_hash: string;
  manifest_hash: string | null;
  field_count: number;
  filled_field_count: number;
  skipped_field_count: number;
  errors: Array<{ category: string; message: string }>;
  started_at: string;
  finished_at: string | null;
  fields: FillFieldEvidence[];
};

export type ValidationSnapshot = {
  id: string;
  application_id: string;
  browser_run_id: string;
  dry_run_fill_id: string;
  safety_assessment_id: string;
  status: "passed" | "blocked";
  operating_mode: "dry_run";
  source_page_hash: string;
  fill_manifest_hash: string;
  validation_manifest_hash: string;
  eligibility_run_id: string | null;
  checks: Array<{ code: string; status: "passed" | "blocked"; message: string }>;
  blockers: Array<{ code: string; status: "blocked"; message: string }>;
  profile_manifest: Array<Record<string, unknown>>;
  document_manifest: Array<Record<string, unknown>>;
  created_at: string;
};

export type ApplicationList = {
  items: ApplicationSummary[];
  total: number;
  offset: number;
  limit: number;
};

export type DomainPolicy = {
  id: string;
  domain: string;
  decision: "approved" | "blocked";
  notes: string;
  created_at: string;
  updated_at: string;
};

export type PrioritySettings = {
  eligibility_weight: number;
  award_weight: number;
  urgency_weight: number;
  completion_weight: number;
  effort_weight: number;
  award_reference_cents: number;
  urgency_window_days: number;
  updated_at: string;
};
