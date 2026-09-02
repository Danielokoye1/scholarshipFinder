from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.browser.inspector import BrowserInspectionError, InspectionResult, inspect_application_page
from app.browser.mapping import PlannedField, build_field_plan
from app.browser.network import redact_url
from app.browser.serialization import browser_run_read
from app.config import settings
from app.core.priority import refresh_priority
from app.core.safety import application_domain, persist_safety_assessment
from app.core.state_machine import transition_application
from app.db import get_db
from app.models import (
    ApplicationEvent,
    BrowserRun,
    FormFieldPlan,
    ProfileField,
    Scholarship,
)
from app.routes.applications import create_task, get_application_and_scholarship
from app.schemas import BrowserRunRead
from app.services import get_or_create_settings, record_event

router = APIRouter(prefix="/api/applications", tags=["browser inspection"])

BARRIER_TASKS = {
    "captcha": (
        "needs_captcha",
        "captcha",
        "CAPTCHA detected",
        "Complete the CAPTCHA manually in a future preserved browser session.",
    ),
    "two_factor_authentication": (
        "needs_2fa",
        "two_factor_authentication",
        "Two-factor authentication detected",
        "A future guarded browser session will require you to enter the verification code.",
    ),
    "essay": (
        "needs_essay",
        "essay",
        "Essay or narrative response detected",
        "Review the prompt and provide or approve a factual response before filling begins.",
    ),
    "recommendation": (
        "needs_recommendation",
        "recommendation",
        "Recommendation requirement detected",
        "Review the recommender requirement and handle the request manually.",
    ),
    "signature": (
        "needs_signature",
        "signature",
        "Signature requirement detected",
        "Review and sign the application manually when a later phase reaches this step.",
    ),
    "attestation": (
        "needs_review",
        "attestation",
        "Certification or attestation detected",
        "Read and explicitly approve the certification before any form filling.",
    ),
    "file_upload": (
        "needs_review",
        "document_review",
        "Document upload detected",
        "Select and approve the exact document category before a later phase can upload anything.",
    ),
}

STATUS_PRIORITY = {
    "needs_review": 7,
    "needs_captcha": 6,
    "needs_2fa": 5,
    "needs_signature": 4,
    "needs_recommendation": 3,
    "needs_essay": 2,
    "needs_user_input": 1,
}


def save_fields(db: Session, run: BrowserRun, planned: list[PlannedField]) -> None:
    for item in planned:
        db.add(
            FormFieldPlan(
                browser_run_id=run.id,
                application_id=run.application_id,
                ordinal=item.field.ordinal,
                form_index=item.field.form_index,
                tag_name=item.field.tag_name,
                input_type=item.field.input_type,
                label=item.field.label,
                required=item.field.required,
                disabled=item.field.disabled,
                autocomplete=item.field.autocomplete,
                profile_field_key=item.profile_field_key,
                mapping_confidence=item.mapping_confidence,
                profile_status=item.profile_status,
                disposition=item.disposition,
                reason=item.reason,
            )
        )


def queue_plan_tasks(
    db: Session,
    application,
    scholarship: Scholarship,
    result: InspectionResult,
    planned: list[PlannedField],
) -> str | None:
    target_statuses: list[str] = []
    for barrier in result.barriers:
        task_spec = BARRIER_TASKS.get(barrier)
        if not task_spec:
            continue
        target, category, title, required_action = task_spec
        target_statuses.append(target)
        create_task(
            db,
            application,
            scholarship,
            category=category,
            title=title,
            required_action=required_action,
        )

    required_missing = [
        item for item in planned if item.field.required and item.disposition == "missing_profile_data"
    ]
    required_unknown = [
        item
        for item in planned
        if item.field.required
        and item.disposition == "manual_review"
        and item.reason
        in {
            "No deterministic profile mapping was found",
            "Field mapping confidence is below the configured threshold",
            "The mapped profile value has not been verified",
        }
    ]
    required_sensitive = [
        item for item in planned if item.field.required and item.disposition == "blocked_sensitive"
    ]
    if required_missing:
        target_statuses.append("needs_user_input")
        labels = ", ".join(item.field.label for item in required_missing[:5])
        create_task(
            db,
            application,
            scholarship,
            category="verify_information",
            title="Verified profile information is missing",
            required_action=f"Add and verify canonical profile values for: {labels}.",
        )
    if required_unknown:
        target_statuses.append("needs_review")
        labels = ", ".join(item.field.label for item in required_unknown[:5])
        create_task(
            db,
            application,
            scholarship,
            category="field_mapping_review",
            title="Required fields need mapping review",
            required_action=f"Review ambiguous required fields: {labels}.",
        )
    if required_sensitive:
        target_statuses.append("needs_review")
        labels = ", ".join(item.field.label for item in required_sensitive[:5])
        create_task(
            db,
            application,
            scholarship,
            category="sensitive_field_review",
            title="Sensitive fields detected",
            required_action=f"Do not provide data automatically. Review these fields manually: {labels}.",
        )
    return max(target_statuses, key=lambda value: STATUS_PRIORITY[value]) if target_statuses else None


def finish_failed_run(
    db: Session,
    run: BrowserRun,
    application,
    scholarship: Scholarship,
    error: BrowserInspectionError,
) -> BrowserRunRead:
    run.status = "blocked" if error.category in {
        "private_network",
        "direct_ip",
        "cross_domain_redirect",
        "insecure_scheme",
        "unsafe_method",
        "unusual_port",
        "embedded_credentials",
    } else "failed"
    run.blocked_requests_json = error.blocked_requests
    run.error_category = error.category
    run.error_message = str(error)[:1000]
    run.finished_at = datetime.now(UTC)
    if application.status == "ready_to_apply":
        transition_application(
            db,
            application,
            "needs_review",
            f"Read-only application inspection stopped: {error.category.replace('_', ' ')}",
            enforce_phase_gate=False,
        )
    create_task(
        db,
        application,
        scholarship,
        category="application_error",
        title="Application inspection stopped safely",
        required_action=str(error),
    )
    refresh_priority(db, scholarship, application)
    record_event(db, "inspection.blocked", f"Inspection stopped for {scholarship.canonical_name}", "warning")
    db.commit()
    return browser_run_read(db, run)


@router.post("/{application_id}/inspect", response_model=BrowserRunRead)
def inspect_application(application_id: str, db: Session = Depends(get_db)) -> BrowserRunRead:
    application, scholarship = get_application_and_scholarship(db, application_id)
    system = get_or_create_settings(db)
    if system.emergency_stop:
        raise HTTPException(status_code=409, detail="Emergency stop blocks all browser actions")
    if application.status != "ready_to_apply":
        raise HTTPException(status_code=409, detail="Application must be ready to apply before inspection")
    if scholarship.eligibility_status != "eligible":
        raise HTTPException(status_code=409, detail="Verified eligibility is required before inspection")
    if not scholarship.application_url:
        raise HTTPException(status_code=409, detail="A distinct application URL is required")

    assessment = persist_safety_assessment(db, scholarship, application.id)
    application.safety_status = assessment.status
    if assessment.status != "approved":
        db.commit()
        raise HTTPException(status_code=409, detail="Fresh destination safety approval is required")
    domain = application_domain(scholarship)
    if not domain:
        raise HTTPException(status_code=409, detail="The application domain could not be determined")

    cutoff = datetime.now(UTC) - timedelta(seconds=settings.inspection_min_interval_seconds)
    recent = db.scalar(
        select(BrowserRun).where(
            BrowserRun.application_id == application.id,
            BrowserRun.started_at >= cutoff,
        )
    )
    if recent:
        raise HTTPException(status_code=429, detail="Wait briefly before inspecting this application again")

    run = BrowserRun(
        application_id=application.id,
        status="running",
        adapter="generic_form",
        start_url=redact_url(scholarship.application_url),
        initial_domain=domain,
        redirect_chain_json=[],
        detected_barriers_json=[],
        blocked_requests_json=[],
        started_at=datetime.now(UTC),
    )
    db.add(run)
    record_event(db, "inspection.started", f"Started read-only inspection for {scholarship.canonical_name}")
    db.commit()
    db.refresh(run)

    try:
        result = inspect_application_page(scholarship.application_url)
    except BrowserInspectionError as error:
        return finish_failed_run(db, run, application, scholarship, error)

    profile_fields = list(db.scalars(select(ProfileField)))
    planned = build_field_plan(
        result.fields,
        profile_fields,
        settings.field_mapping_confidence_threshold,
    )
    save_fields(db, run, planned)
    active_required = [item for item in planned if item.field.required and not item.field.disabled]
    denominator = len(active_required) or len([item for item in planned if not item.field.disabled])
    automatable = [
        item
        for item in (active_required or planned)
        if not item.field.disabled and item.disposition == "auto_answerable"
    ]
    run.status = "completed"
    run.final_url = result.final_url
    run.final_domain = result.final_domain
    run.redirect_chain_json = result.redirect_chain
    run.page_title = result.page_title
    run.response_status = result.response_status
    run.page_content_hash = result.page_content_hash
    run.field_count = len(planned)
    run.required_field_count = len(active_required)
    run.automatable_field_count = len(automatable)
    run.automatable_percent = round(100 * len(automatable) / denominator, 1) if denominator else 0.0
    run.detected_barriers_json = result.barriers
    run.blocked_requests_json = result.blocked_requests
    run.finished_at = datetime.now(UTC)

    target_status = queue_plan_tasks(db, application, scholarship, result, planned)
    if target_status:
        transition_application(
            db,
            application,
            target_status,
            "Read-only inspection found a required manual checkpoint",
            enforce_phase_gate=False,
        )
    else:
        application.version += 1
        db.add(
            ApplicationEvent(
                application_id=application.id,
                from_status=application.status,
                to_status=application.status,
                reason="Read-only application inspection completed; no form data was entered",
                actor="system",
                metadata_json={"browser_run_id": run.id},
            )
        )
    refresh_priority(db, scholarship, application)
    record_event(db, "inspection.completed", f"Inspected {scholarship.canonical_name} without entering data")
    db.commit()
    return browser_run_read(db, run)


@router.get("/{application_id}/inspections", response_model=list[BrowserRunRead])
def inspection_history(application_id: str, db: Session = Depends(get_db)) -> list[BrowserRunRead]:
    application, _ = get_application_and_scholarship(db, application_id)
    runs = list(
        db.scalars(
            select(BrowserRun)
            .where(BrowserRun.application_id == application.id)
            .order_by(BrowserRun.started_at.desc())
        )
    )
    return [browser_run_read(db, run) for run in runs]
