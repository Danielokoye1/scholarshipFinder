from datetime import UTC, datetime
from typing import Any

from sqlalchemy.orm import Session

from app.models import Application, ApplicationEvent


APPLICATION_STATES = {
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
}

ALLOWED_TRANSITIONS = {
    "discovered": {"eligibility_check", "expired", "cancelled"},
    "eligibility_check": {"ineligible", "ready_to_apply", "needs_user_input", "needs_review", "expired"},
    "ineligible": {"eligibility_check", "cancelled"},
    "ready_to_apply": {"application_started", "needs_review", "expired", "cancelled"},
    "application_started": {"filling", "needs_review", "failed", "cancelled"},
    "filling": {
        "needs_user_input",
        "needs_essay",
        "needs_2fa",
        "needs_captcha",
        "needs_recommendation",
        "needs_signature",
        "needs_review",
        "ready_to_submit",
        "failed",
    },
    "needs_user_input": {"filling", "eligibility_check", "needs_review", "cancelled"},
    "needs_essay": {"filling", "needs_review", "cancelled"},
    "needs_2fa": {"filling", "needs_review", "cancelled"},
    "needs_captcha": {"filling", "needs_review", "cancelled"},
    "needs_recommendation": {"filling", "needs_review", "cancelled"},
    "needs_signature": {"filling", "needs_review", "cancelled"},
    "needs_review": {"eligibility_check", "ready_to_apply", "filling", "cancelled", "expired"},
    "ready_to_submit": {"submitting", "needs_review", "cancelled", "expired"},
    "submitting": {"submitted", "submission_unconfirmed", "failed"},
    "submitted": {"follow_up", "awarded", "rejected"},
    "submission_unconfirmed": {"submitted", "needs_review", "failed"},
    "failed": {"ready_to_apply", "application_started", "needs_review", "cancelled"},
    "follow_up": {"awarded", "rejected", "needs_review"},
    "awarded": set(),
    "rejected": set(),
    "expired": set(),
    "cancelled": set(),
}

DATA_ENTRY_STATES = {"application_started", "filling", "ready_to_submit", "submitting"}
LOCKED_PHASE_3_STATES = {"application_started", "filling", "ready_to_submit", "submitting", "submitted"}


class InvalidTransition(ValueError):
    pass


def transition_application(
    db: Session,
    application: Application,
    to_status: str,
    reason: str,
    *,
    actor: str = "system",
    metadata: dict[str, Any] | None = None,
    enforce_phase_gate: bool = True,
) -> ApplicationEvent:
    if to_status not in APPLICATION_STATES:
        raise InvalidTransition(f"Unknown application state: {to_status}")
    if to_status not in ALLOWED_TRANSITIONS.get(application.status, set()):
        raise InvalidTransition(f"Cannot transition from {application.status} to {to_status}")
    if to_status in DATA_ENTRY_STATES and application.safety_status != "approved":
        raise InvalidTransition("Personal data entry is blocked until application safety is approved")
    if to_status in DATA_ENTRY_STATES and application.scholarship_id is None:
        raise InvalidTransition("The application has no scholarship record")
    if enforce_phase_gate and to_status in LOCKED_PHASE_3_STATES:
        raise InvalidTransition("Browser preparation and submission remain disabled in Phase 3")

    previous = application.status
    application.status = to_status
    application.version += 1
    if to_status == "application_started" and application.started_at is None:
        application.started_at = datetime.now(UTC)
    event = ApplicationEvent(
        application_id=application.id,
        from_status=previous,
        to_status=to_status,
        reason=reason,
        actor=actor,
        metadata_json=metadata or {},
    )
    db.add(event)
    return event


def record_initial_state(db: Session, application: Application, reason: str) -> None:
    db.add(
        ApplicationEvent(
            application_id=application.id,
            from_status=None,
            to_status=application.status,
            reason=reason,
            actor="system",
            metadata_json={},
        )
    )

