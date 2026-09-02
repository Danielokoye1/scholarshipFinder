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
