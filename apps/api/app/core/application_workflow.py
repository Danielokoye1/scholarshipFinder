from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.priority import refresh_priority
from app.core.state_machine import transition_application
from app.models import (
    Application,
    EligibilityCheck,
    EligibilityRule,
    ManualTask,
    SafetyAssessment,
    Scholarship,
)


RECONCILABLE_STATES = {
    "discovered",
    "eligibility_check",
    "ineligible",
    "needs_user_input",
    "needs_review",
    "ready_to_apply",
}


def unresolved_eligibility_action(db: Session, scholarship: Scholarship) -> str:
    requirements = list(
        db.scalars(
            select(EligibilityRule.requirement_text)
            .join(EligibilityCheck, EligibilityCheck.rule_id == EligibilityRule.id)
            .where(
                EligibilityRule.scholarship_id == scholarship.id,
                EligibilityCheck.is_current.is_(True),
                EligibilityCheck.result.in_({"unknown", "needs_verification"}),
            )
            .order_by(EligibilityRule.created_at, EligibilityRule.id)
            .limit(5)
        )
    )
    if not requirements:
        return "Review the unknown eligibility checks and add only verified profile information."
    return "Confirm these unresolved requirements: " + "; ".join(requirements)


def create_application_task(
    db: Session,
    application: Application,
    scholarship: Scholarship,
    *,
    category: str,
    title: str,
    required_action: str,
) -> ManualTask:
    existing = db.scalar(
        select(ManualTask).where(
            ManualTask.application_id == application.id,
            ManualTask.category == category,
            ManualTask.status == "open",
        )
    )
    if existing:
        existing.required_action = required_action
        existing.priority_score = application.priority_score
        return existing
    task = ManualTask(
        application_id=application.id,
        scholarship_id=scholarship.id,
        category=category,
        title=title,
        required_action=required_action,
        status="open",
        direct_url=scholarship.application_url or scholarship.source_url,
        priority_score=application.priority_score,
        deadline=scholarship.deadline,
    )
    db.add(task)
    return task


def resolve_open_tasks(db: Session, application: Application, categories: set[str]) -> None:
    now = datetime.now(UTC)
    for task in db.scalars(
        select(ManualTask).where(
            ManualTask.application_id == application.id,
            ManualTask.category.in_(categories),
            ManualTask.status == "open",
        )
    ):
        task.status = "resolved"
        task.resolved_at = now


def desired_application_status(scholarship: Scholarship, safety: SafetyAssessment) -> str:
    if scholarship.eligibility_status == "ineligible":
        return "ineligible"
    if scholarship.eligibility_status != "eligible":
        return "needs_user_input"
    if safety.status != "approved":
        return "needs_review"
    return "ready_to_apply"


def reconcile_application(
    db: Session,
    application: Application,
    scholarship: Scholarship,
    safety: SafetyAssessment,
) -> None:
    application.safety_status = safety.status
    if application.status not in RECONCILABLE_STATES:
        refresh_priority(db, scholarship, application)
        return

    target = desired_application_status(scholarship, safety)
    if application.status == "discovered":
        transition_application(
            db,
            application,
            "eligibility_check",
            "Evaluating eligibility and application safety",
            enforce_phase_gate=False,
        )
    elif application.status != "eligibility_check" and application.status != target:
        transition_application(
            db,
            application,
            "eligibility_check",
            "Profile or scholarship evidence changed; re-evaluating the workflow",
            enforce_phase_gate=False,
        )

    if application.status == "eligibility_check" and target != "eligibility_check":
        reasons = {
            "ineligible": "At least one deterministic eligibility requirement failed",
            "needs_user_input": "Eligibility contains unknown or unverified requirements",
            "needs_review": "Application safety must be approved before any personal data is entered",
            "ready_to_apply": "Eligibility and application safety checks passed",
        }
        transition_application(
            db,
            application,
            target,
            reasons[target],
            enforce_phase_gate=False,
        )

    refresh_priority(db, scholarship, application)
    if target == "needs_user_input":
        resolve_open_tasks(db, application, {"safety_review"})
        create_application_task(
            db,
            application,
            scholarship,
            category="verify_information",
            title=f"Verify eligibility for {scholarship.canonical_name}",
            required_action=unresolved_eligibility_action(db, scholarship),
        )
    elif target == "needs_review":
        resolve_open_tasks(db, application, {"verify_information"})
        create_application_task(
            db,
            application,
            scholarship,
            category="safety_review",
            title=f"Review {safety.application_domain or 'application destination'}",
            required_action=(
                "Review the provider and application domain, then explicitly approve or block the domain."
            ),
        )
    else:
        resolve_open_tasks(db, application, {"verify_information", "safety_review"})

    for task in db.scalars(select(ManualTask).where(ManualTask.application_id == application.id)):
        task.priority_score = application.priority_score
