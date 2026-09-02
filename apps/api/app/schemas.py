from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


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

