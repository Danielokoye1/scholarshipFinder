from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.models import Application, PrioritySettings, Scholarship


def get_or_create_priority_settings(db: Session) -> PrioritySettings:
    settings = db.get(PrioritySettings, 1)
    if settings is None:
        settings = PrioritySettings(id=1)
        db.add(settings)
        db.flush()
    return settings


def calculate_priority(
    scholarship: Scholarship,
    settings: PrioritySettings,
    application: Application | None = None,
) -> float:
    eligibility = (
        scholarship.eligibility_score
        if scholarship.eligibility_status == "eligible"
        else 0.0
        if scholarship.eligibility_status == "ineligible"
        else scholarship.eligibility_score * 0.5
    )
    award = min((scholarship.award_max_cents or 0) / settings.award_reference_cents, 1.0)
    if scholarship.deadline is None:
        urgency = 0.2
    else:
        deadline = scholarship.deadline
        if deadline.tzinfo is None:
            deadline = deadline.replace(tzinfo=UTC)
        days = (deadline - datetime.now(UTC)).total_seconds() / 86_400
        urgency = 0.0 if days < 0 else max(0.0, 1.0 - days / settings.urgency_window_days)
    completion = (application.completion_percent / 100) if application else 0.0
    effort = 1.0 - (application.manual_effort_score if application else 0.5)
    weighted = (
        eligibility * settings.eligibility_weight
        + award * settings.award_weight
        + urgency * settings.urgency_weight
        + completion * settings.completion_weight
        + effort * settings.effort_weight
    )
    total_weight = (
        settings.eligibility_weight
        + settings.award_weight
        + settings.urgency_weight
        + settings.completion_weight
        + settings.effort_weight
    )
    return round(100 * weighted / total_weight, 2) if total_weight else 0.0


def refresh_priority(
    db: Session, scholarship: Scholarship, application: Application | None = None
) -> float:
    score = calculate_priority(scholarship, get_or_create_priority_settings(db), application)
    scholarship.priority_score = score
    if application:
        application.priority_score = score
    return score

