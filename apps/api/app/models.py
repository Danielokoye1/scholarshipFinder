import enum
import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


def now_utc() -> datetime:
    return datetime.now(UTC)


class ProfileFieldStatus(str, enum.Enum):
    VERIFIED = "verified"
    USER_ENTERED = "user_entered"
    UNKNOWN = "unknown"


class AutomationStatus(str, enum.Enum):
    RUNNING = "running"
    PAUSED = "paused"
    STOPPED = "stopped"


class OperatingMode(str, enum.Enum):
    DISCOVERY_ONLY = "discovery_only"
    DRY_RUN = "dry_run"
    ASSISTED = "assisted"
    AUTONOMOUS = "autonomous"


class ProfileField(Base):
    __tablename__ = "profile_fields"

    id: Mapped[int] = mapped_column(primary_key=True)
    field_key: Mapped[str] = mapped_column(String(180), unique=True, index=True)
    value_json: Mapped[Any | None] = mapped_column(JSON, nullable=True)
    status: Mapped[str] = mapped_column(String(32), default=ProfileFieldStatus.UNKNOWN.value)
    source: Mapped[str | None] = mapped_column(String(500), nullable=True)
    last_verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc, onupdate=now_utc)


class Document(Base):
    __tablename__ = "documents"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    original_filename: Mapped[str] = mapped_column(String(255))
    stored_filename: Mapped[str] = mapped_column(String(255), unique=True)
    document_type: Mapped[str] = mapped_column(String(80))
    version: Mapped[str] = mapped_column(String(40), default="1")
    content_type: Mapped[str | None] = mapped_column(String(120), nullable=True)
    size_bytes: Mapped[int] = mapped_column(Integer)
    sha256: Mapped[str] = mapped_column(String(64), index=True)
    auto_upload_allowed: Mapped[bool] = mapped_column(Boolean, default=False)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc, onupdate=now_utc)


class SystemSettings(Base):
    __tablename__ = "system_settings"

    id: Mapped[int] = mapped_column(primary_key=True, default=1)
    automation_status: Mapped[str] = mapped_column(String(32), default=AutomationStatus.PAUSED.value)
    operating_mode: Mapped[str] = mapped_column(String(32), default=OperatingMode.DISCOVERY_ONLY.value)
    discovery_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    eligibility_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    preparation_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    automatic_submission_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    email_monitoring_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    emergency_stop: Mapped[bool] = mapped_column(Boolean, default=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc, onupdate=now_utc)


class SystemEvent(Base):
    __tablename__ = "system_events"

    id: Mapped[int] = mapped_column(primary_key=True)
    event_type: Mapped[str] = mapped_column(String(80))
    message: Mapped[str] = mapped_column(String(1000))
    severity: Mapped[str] = mapped_column(String(20), default="info")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc, index=True)


class Scholarship(Base):
    __tablename__ = "scholarships"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    canonical_name: Mapped[str] = mapped_column(String(300))
    provider: Mapped[str | None] = mapped_column(String(200), nullable=True)
    source_url: Mapped[str] = mapped_column(String(2000), unique=True, index=True)
    application_url: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    award_max_cents: Mapped[int | None] = mapped_column(Integer, nullable=True)
    deadline: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    eligibility_status: Mapped[str] = mapped_column(String(40), default="needs_information")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc, onupdate=now_utc)


class Application(Base):
    __tablename__ = "applications"
    __table_args__ = (UniqueConstraint("scholarship_id", name="uq_application_scholarship"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    scholarship_id: Mapped[str] = mapped_column(ForeignKey("scholarships.id"))
    status: Mapped[str] = mapped_column(String(48), default="discovered", index=True)
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    award_result_cents: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc, onupdate=now_utc)


class ManualTask(Base):
    __tablename__ = "manual_tasks"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    application_id: Mapped[str | None] = mapped_column(ForeignKey("applications.id"), nullable=True)
    category: Mapped[str] = mapped_column(String(60))
    title: Mapped[str] = mapped_column(String(300))
    required_action: Mapped[str] = mapped_column(String(1000))
    status: Mapped[str] = mapped_column(String(24), default="open", index=True)
    deadline: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc, onupdate=now_utc)

