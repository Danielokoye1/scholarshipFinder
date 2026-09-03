from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import (
    Application,
    DryRunFill,
    ManualTask,
    Scholarship,
    SystemEvent,
    SystemSettings,
    ValidationSnapshot,
)
from app.schemas import DashboardMetrics


AWAITING_STATUSES = {"submitted", "acknowledged", "under_review", "finalist", "interview"}


def get_or_create_settings(db: Session) -> SystemSettings:
    current = db.get(SystemSettings, 1)
    if current is None:
        current = SystemSettings(id=1)
        db.add(current)
        db.commit()
        db.refresh(current)
    return current


def record_event(db: Session, event_type: str, message: str, severity: str = "info") -> None:
    db.add(SystemEvent(event_type=event_type, message=message, severity=severity))


def dashboard_metrics(db: Session) -> DashboardMetrics:
    week_start = datetime.now(UTC) - timedelta(days=7)
    opportunities = db.scalar(select(func.count()).select_from(Scholarship)) or 0
    opportunities_week = db.scalar(
        select(func.count()).select_from(Scholarship).where(Scholarship.created_at >= week_start)
    ) or 0
    likely_eligible = db.scalar(
        select(func.count())
        .select_from(Scholarship)
        .where(Scholarship.eligibility_status.in_({"eligible", "probably_eligible"}))
    ) or 0
    needs_information = db.scalar(
        select(func.count())
        .select_from(Scholarship)
        .where(Scholarship.eligibility_status == "needs_information")
    ) or 0
    ineligible = db.scalar(
        select(func.count())
        .select_from(Scholarship)
        .where(Scholarship.eligibility_status == "ineligible")
    ) or 0
    dry_runs = db.scalar(
        select(func.count()).select_from(DryRunFill).where(DryRunFill.status == "completed")
    ) or 0
    ready_for_preparation = db.scalar(
        select(func.count())
        .select_from(Application)
        .join(Scholarship, Scholarship.id == Application.scholarship_id)
        .where(
            Application.status == "ready_to_apply",
            Application.safety_status == "approved",
            Scholarship.eligibility_status == "eligible",
        )
    ) or 0
    validation_passes = db.scalar(
        select(func.count(func.distinct(ValidationSnapshot.application_id))).where(
            ValidationSnapshot.status == "passed"
        )
    ) or 0
    submitted = db.scalar(select(func.count()).select_from(Application).where(Application.submitted_at.is_not(None))) or 0
    submitted_week = db.scalar(
        select(func.count()).select_from(Application).where(Application.submitted_at >= week_start)
    ) or 0
    attention = db.scalar(select(func.count()).select_from(ManualTask).where(ManualTask.status == "open")) or 0
    awaiting = db.scalar(
        select(func.count()).select_from(Application).where(Application.status.in_(AWAITING_STATUSES))
    ) or 0
    won = db.scalar(select(func.count()).select_from(Application).where(Application.status == "awarded")) or 0
    total_won = db.scalar(select(func.coalesce(func.sum(Application.award_result_cents), 0))) or 0
    potential = db.scalar(
        select(func.coalesce(func.sum(Scholarship.award_max_cents), 0))
        .join(Application, Application.scholarship_id == Scholarship.id)
        .where(Application.status.not_in({"ineligible", "rejected", "expired"}))
    ) or 0
    return DashboardMetrics(
        opportunities_tracked=opportunities,
        opportunities_this_week=opportunities_week,
        likely_eligible=likely_eligible,
        needs_information=needs_information,
        ineligible_filtered=ineligible,
        ready_for_preparation=ready_for_preparation,
        dry_runs_completed=dry_runs,
        validation_passes=validation_passes,
        applications_submitted=submitted,
        potential_awards_cents=potential,
        applications_this_week=submitted_week,
        need_attention=attention,
        awaiting_decision=awaiting,
        awards_won=won,
        total_won_cents=total_won,
    )
