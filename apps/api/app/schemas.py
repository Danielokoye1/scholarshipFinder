from datetime import datetime
import re
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


ProfileStatus = Literal["verified", "user_entered", "unknown"]
OperatingMode = Literal["discovery_only", "dry_run", "assisted", "autonomous"]
AutomationStatus = Literal["running", "paused", "stopped"]


class ProfileFieldWrite(BaseModel):
    value: Any | None = None
    status: ProfileStatus = "user_entered"
    source: str | None = Field(default="Manual profile entry", max_length=500)

    @model_validator(mode="after")
    def validate_verified_source(self) -> "ProfileFieldWrite":
        if self.status == "verified" and not self.source:
            raise ValueError("Verified fields require a source")
        if self.status == "unknown" and self.value is not None:
            raise ValueError("Unknown fields cannot carry a value")
        return self


class ProfileFieldRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    field_key: str
    value: Any | None = Field(validation_alias="value_json", serialization_alias="value")
    status: ProfileStatus
    source: str | None
    last_verified_at: datetime | None
    updated_at: datetime


class ProfileBulkFieldWrite(ProfileFieldWrite):
    field_key: str = Field(min_length=3, max_length=180)

    @field_validator("field_key")
    @classmethod
    def valid_field_key(cls, value: str) -> str:
        if not re.fullmatch(r"[a-z][a-z0-9_]*(\.[a-z][a-z0-9_]*)*", value):
            raise ValueError("field_key must be a dotted canonical profile key")
        return value


class ProfileBulkWrite(BaseModel):
    items: list[ProfileBulkFieldWrite] = Field(min_length=1, max_length=100)

    @model_validator(mode="after")
    def unique_field_keys(self) -> "ProfileBulkWrite":
        keys = [item.field_key for item in self.items]
        if len(keys) != len(set(keys)):
            raise ValueError("Each profile field may appear only once")
        return self


class ProfileWorkspaceFieldRead(BaseModel):
    field_key: str
    label: str
    value: Any | None
    status: ProfileStatus
    source: str | None
    last_verified_at: datetime | None
    input_type: str
    options: list[str]
    important: bool
    sensitive: bool
    help_text: str


class ProfileSectionRead(BaseModel):
    key: str
    title: str
    fields: list[ProfileWorkspaceFieldRead]


class ProfileReviewIssueRead(BaseModel):
    code: str
    severity: Literal["success", "info", "warning", "error"]
    title: str
    message: str
    field_keys: list[str]
    evidence_sources: list[str]
    suggested_value: Any | None
    requires_confirmation: bool


class ProfileDocumentCheckRead(BaseModel):
    document_id: str
    document_type: str
    version: str
    is_latest: bool
    status: Literal["readable", "locked", "no_text", "missing", "unsupported", "too_large", "unreadable"]
    page_count: int | None


class ProfileOverviewRead(BaseModel):
    completeness_percent: float
    important_fields_complete: int
    important_fields_total: int
    sections: list[ProfileSectionRead]
    issues: list[ProfileReviewIssueRead]
    document_checks: list[ProfileDocumentCheckRead]
    external_address_verification: Literal["not_performed"]
    generated_at: datetime


class DocumentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    original_filename: str
    document_type: str
    version: str
    content_type: str | None
    size_bytes: int
    sha256: str
    auto_upload_allowed: bool
    expires_at: datetime | None
    created_at: datetime


class DocumentApprovalWrite(BaseModel):
    auto_upload_allowed: bool


class SystemSettingsRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    automation_status: AutomationStatus
    operating_mode: OperatingMode
    discovery_enabled: bool
    eligibility_enabled: bool
    preparation_enabled: bool
    automatic_submission_enabled: bool
    email_monitoring_enabled: bool
    emergency_stop: bool
    updated_at: datetime


class SystemSettingsWrite(BaseModel):
    operating_mode: OperatingMode | None = None
    discovery_enabled: bool | None = None
    eligibility_enabled: bool | None = None
    preparation_enabled: bool | None = None
    automatic_submission_enabled: bool | None = None
    email_monitoring_enabled: bool | None = None


class ActivityRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    event_type: str
    message: str
    severity: str
    created_at: datetime


class DashboardMetrics(BaseModel):
    applications_submitted: int
    potential_awards_cents: int
    applications_this_week: int
    need_attention: int
    awaiting_decision: int
    awards_won: int
    total_won_cents: int


class DashboardResponse(BaseModel):
    metrics: DashboardMetrics
    settings: SystemSettingsRead
    activity: list[ActivityRead]
    attention: list[dict[str, Any]]
    upcoming_deadlines: list[dict[str, Any]]


RuleOperator = Literal[
    "equals",
    "not_equals",
    "gte",
    "lte",
    "in",
    "contains_any",
    "contains_all",
    "is_true",
    "exists",
]
EligibilityCheckResult = Literal["pass", "fail", "unknown", "needs_verification"]
EligibilityStatus = Literal["eligible", "probably_eligible", "needs_information", "ineligible"]
LegitimacyStatus = Literal["verified", "likely_legitimate", "review_required", "blocked"]


class EligibilityRuleWrite(BaseModel):
    requirement: str = Field(min_length=3, max_length=4000)
    field_key: str | None = Field(default=None, max_length=180)
    operator: RuleOperator
    expected_value: Any | None = None
    confidence: float = Field(ge=0, le=1)
    needs_review: bool = False
    source_quote: str = Field(min_length=1, max_length=10000)

    @field_validator("field_key")
    @classmethod
    def valid_field_key(cls, value: str | None) -> str | None:
        if value is not None and not re.fullmatch(r"[a-z][a-z0-9_]*(\.[a-z][a-z0-9_]*)*", value):
            raise ValueError("field_key must be a dotted canonical profile key")
        return value

    @model_validator(mode="after")
    def expected_value_matches_operator(self) -> "EligibilityRuleWrite":
        if self.operator not in {"exists", "is_true"} and self.expected_value is None:
            raise ValueError(f"{self.operator} requires expected_value")
        if self.operator in {"in", "contains_any", "contains_all"} and not isinstance(
            self.expected_value, list
        ):
            raise ValueError(f"{self.operator} requires expected_value to be a list")
        return self


class ScholarshipIngest(BaseModel):
    name: str = Field(min_length=2, max_length=300)
    provider: str | None = Field(default=None, max_length=200)
    source_url: str = Field(min_length=10, max_length=2000)
    application_url: str | None = Field(default=None, max_length=2000)
    description: str | None = Field(default=None, max_length=30000)
    award_min_cents: int | None = Field(default=None, ge=0)
    award_max_cents: int | None = Field(default=None, ge=0)
    award_description: str | None = Field(default=None, max_length=500)
    raw_deadline_text: str | None = Field(default=None, max_length=300)
    deadline: datetime | None = None
    deadline_type: Literal["fixed", "rolling", "recurring", "unknown"] = "unknown"
    requirements: dict[str, Any] = Field(default_factory=dict)
    source_text: str = Field(min_length=1, max_length=100000)
    source_adapter: str = Field(default="manual", min_length=2, max_length=80)
    rules: list[EligibilityRuleWrite] = Field(default_factory=list, max_length=100)

    @model_validator(mode="after")
    def validate_award_and_deadline(self) -> "ScholarshipIngest":
        if (
            self.award_min_cents is not None
            and self.award_max_cents is not None
            and self.award_min_cents > self.award_max_cents
        ):
            raise ValueError("award_min_cents cannot exceed award_max_cents")
        if self.deadline is not None and not self.raw_deadline_text:
            raise ValueError("A normalized deadline requires the original raw_deadline_text")
        if self.deadline is not None and self.deadline.tzinfo is None:
            raise ValueError("A normalized deadline must include a timezone offset")
        return self


class IngestResult(BaseModel):
    scholarship_id: str
    created: bool
    duplicate_reason: str | None = None
    duplicate_confidence: float | None = None
    legitimacy_status: LegitimacyStatus
    eligibility_status: EligibilityStatus


class EligibilityRuleRead(BaseModel):
    id: str
    requirement: str
    field_key: str | None
    operator: RuleOperator
    expected_value: Any | None
    confidence: float
    needs_review: bool
    source_quote: str | None


class EligibilityCheckRead(BaseModel):
    id: str
    rule_id: str
    requirement: str
    field_key: str | None
    profile_value: Any | None
    result: EligibilityCheckResult
    evidence: str
    confidence: float
    evaluation_run_id: str
    is_current: bool
    evaluated_at: datetime


class ScholarshipSummary(BaseModel):
    id: str
    canonical_name: str
    provider: str | None
    source_url: str
    application_url: str | None
    award_min_cents: int | None
    award_max_cents: int | None
    deadline: datetime | None
    deadline_timezone: str | None
    deadline_type: str
    legitimacy_status: LegitimacyStatus
    legitimacy_score: float
    eligibility_status: EligibilityStatus
    eligibility_score: float
    automation_level: int
    safety_status: Literal["approved", "review_required", "blocked"]
    priority_score: float
    last_verified_at: datetime | None
    created_at: datetime


class ScholarshipList(BaseModel):
    items: list[ScholarshipSummary]
    total: int
    offset: int
    limit: int


class ScholarshipDetail(ScholarshipSummary):
    description: str | None
    award_description: str | None
    raw_deadline_text: str | None
    requirements: dict[str, Any]
    legitimacy_signals: list[str]
    rules: list[EligibilityRuleRead]
    checks: list[EligibilityCheckRead]


class EvaluationBatchResult(BaseModel):
    evaluated: int
    eligible: int
    ineligible: int
    needs_information: int


ApplicationStatus = Literal[
    "discovered",
    "eligibility_check",
    "ineligible",
    "ready_to_apply",
    "application_started",
    "filling",
    "needs_user_input",
    "needs_essay",
    "needs_2fa",
    "needs_captcha",
    "needs_recommendation",
    "needs_signature",
    "needs_review",
    "ready_to_submit",
    "submitting",
    "submitted",
    "submission_unconfirmed",
    "failed",
    "follow_up",
    "awarded",
    "rejected",
    "expired",
    "cancelled",
]


class ApplicationCreate(BaseModel):
    scholarship_id: str = Field(min_length=1, max_length=36)
    manual_effort_score: float = Field(default=0.5, ge=0, le=1)


class ApplicationTransitionWrite(BaseModel):
    to_status: ApplicationStatus
    reason: str = Field(min_length=3, max_length=1000)
    expected_version: int = Field(ge=1)


class ApplicationEventRead(BaseModel):
    id: str
    from_status: str | None
    to_status: str
    reason: str
    actor: str
    metadata: dict[str, Any]
    created_at: datetime


class SafetyAssessmentRead(BaseModel):
    id: str
    scholarship_id: str
    application_id: str | None
    application_domain: str | None
    status: Literal["approved", "review_required", "blocked"]
    score: float
    reasons: list[str]
    is_current: bool
    assessed_at: datetime


class ManualTaskRead(BaseModel):
    id: str
    application_id: str | None
    scholarship_id: str | None
    category: str
    title: str
    required_action: str
    status: Literal["open", "resolved", "dismissed"]
    direct_url: str | None
    priority_score: float
    deadline: datetime | None
    resolved_at: datetime | None
    created_at: datetime


class ManualTaskUpdate(BaseModel):
    status: Literal["resolved", "dismissed"]


class ApplicationSummary(BaseModel):
    id: str
    scholarship_id: str
    scholarship_name: str
    provider: str | None
    award_max_cents: int | None
    deadline: datetime | None
    application_url: str | None
    status: ApplicationStatus
    safety_status: Literal["approved", "review_required", "blocked"]
    automation_level: int
    completion_percent: float
    priority_score: float
    manual_effort_score: float
    submitted_at: datetime | None
    version: int
    updated_at: datetime


class ApplicationList(BaseModel):
    items: list[ApplicationSummary]
    total: int
    offset: int
    limit: int


class ApplicationDetail(ApplicationSummary):
    eligibility_status: EligibilityStatus
    current_safety_assessment: SafetyAssessmentRead | None
    latest_inspection: "BrowserRunRead | None" = None
    latest_fill: "DryRunFillRead | None" = None
    latest_validation: "ValidationSnapshotRead | None" = None
    events: list[ApplicationEventRead]
    tasks: list[ManualTaskRead]


class FormFieldPlanRead(BaseModel):
    id: str
    ordinal: int
    form_index: int
    tag_name: str
    input_type: str
    label: str
    required: bool
    disabled: bool
    autocomplete: str | None
    profile_field_key: str | None
    mapping_confidence: float
    profile_status: str | None
    disposition: Literal[
        "auto_answerable",
        "missing_profile_data",
        "manual_review",
        "blocked_sensitive",
        "not_applicable",
    ]
    reason: str


class BrowserRunRead(BaseModel):
    id: str
    application_id: str
    status: Literal["running", "completed", "blocked", "failed"]
    adapter: str
    start_url: str
    final_url: str | None
    initial_domain: str
    final_domain: str | None
    redirect_chain: list[str]
    page_title: str | None
    response_status: int | None
    page_content_hash: str | None
    field_count: int
    required_field_count: int
    automatable_field_count: int
    automatable_percent: float
    detected_barriers: list[str]
    blocked_requests: list[dict[str, str]]
    error_category: str | None
    error_message: str | None
    started_at: datetime
    finished_at: datetime | None
    fields: list[FormFieldPlanRead] = Field(default_factory=list)


class FillFieldEvidenceRead(BaseModel):
    id: str
    ordinal: int
    label: str
    profile_field_key: str
    profile_status: Literal["verified"]
    source_reference: str
    profile_updated_at: datetime
    value_type: str
    value_hash: str
    result: Literal["filled"]
    reason: str


class DryRunFillRead(BaseModel):
    id: str
    application_id: str
    browser_run_id: str
    status: Literal["running", "completed", "blocked", "failed"]
    execution_scope: Literal["offline_synthetic"]
    source_page_hash: str
    manifest_hash: str | None
    field_count: int
    filled_field_count: int
    skipped_field_count: int
    errors: list[dict[str, str]]
    started_at: datetime
    finished_at: datetime | None
    fields: list[FillFieldEvidenceRead] = Field(default_factory=list)


class ValidationSnapshotRead(BaseModel):
    id: str
    application_id: str
    browser_run_id: str
    dry_run_fill_id: str
    safety_assessment_id: str
    status: Literal["passed", "blocked"]
    operating_mode: Literal["dry_run"]
    source_page_hash: str
    fill_manifest_hash: str
    validation_manifest_hash: str
    eligibility_run_id: str | None
    checks: list[dict[str, str]]
    blockers: list[dict[str, str]]
    profile_manifest: list[dict[str, Any]]
    document_manifest: list[dict[str, Any]]
    created_at: datetime


class DomainPolicyWrite(BaseModel):
    domain: str = Field(min_length=3, max_length=253)
    decision: Literal["approved", "blocked"]
    notes: str = Field(min_length=3, max_length=2000)

    @field_validator("domain")
    @classmethod
    def normalize_domain(cls, value: str) -> str:
        domain = value.strip().casefold().removeprefix("www.").rstrip(".")
        if "://" in domain or "/" in domain or not re.fullmatch(r"[a-z0-9.-]+", domain):
            raise ValueError("Provide a hostname only, such as apply.example.org")
        if ".." in domain or domain.startswith(".") or domain.endswith("."):
            raise ValueError("Invalid domain")
        return domain


class DomainPolicyRead(BaseModel):
    id: str
    domain: str
    decision: Literal["approved", "blocked"]
    notes: str
    created_at: datetime
    updated_at: datetime


class PrioritySettingsRead(BaseModel):
    eligibility_weight: float
    award_weight: float
    urgency_weight: float
    completion_weight: float
    effort_weight: float
    award_reference_cents: int
    urgency_window_days: int
    updated_at: datetime


class PrioritySettingsWrite(BaseModel):
    eligibility_weight: float = Field(ge=0, le=1)
    award_weight: float = Field(ge=0, le=1)
    urgency_weight: float = Field(ge=0, le=1)
    completion_weight: float = Field(ge=0, le=1)
    effort_weight: float = Field(ge=0, le=1)
    award_reference_cents: int = Field(ge=100, le=100_000_000)
    urgency_window_days: int = Field(ge=1, le=365)

    @model_validator(mode="after")
    def at_least_one_weight(self) -> "PrioritySettingsWrite":
        if not any(
            (
                self.eligibility_weight,
                self.award_weight,
                self.urgency_weight,
                self.completion_weight,
                self.effort_weight,
            )
        ):
            raise ValueError("At least one priority weight must be greater than zero")
        return self


ApplicationDetail.model_rebuild()
