from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.browser.dry_run import DryRunFillError, FillCandidate, execute_offline_dry_run
from app.browser.fill_serialization import dry_run_fill_read
from app.core.priority import refresh_priority
from app.core.state_machine import transition_application
from app.db import get_db
from app.models import (
    ApplicationEvent,
    BrowserRun,
    DryRunFill,
    FillFieldEvidence,
    FormFieldPlan,
    ProfileField,
)
from app.routes.applications import create_task, get_application_and_scholarship
from app.schemas import DryRunFillRead
from app.services import get_or_create_settings, record_event

router = APIRouter(prefix="/api/applications", tags=["offline dry-run filling"])

SUPPORTED_INPUT_TYPES = {"text", "email", "tel", "number", "date", "url", "search"}


def latest_completed_inspection(db: Session, application_id: str) -> BrowserRun | None:
    return db.scalar(
        select(BrowserRun)
        .where(
            BrowserRun.application_id == application_id,
            BrowserRun.status == "completed",
        )
        .order_by(BrowserRun.started_at.desc(), BrowserRun.id.desc())
    )


def block_fill(
    db: Session,
    run: DryRunFill,
    application,
    scholarship,
    category: str,
    message: str,
) -> DryRunFillRead:
    run.status = "blocked"
    run.errors_json = [{"category": category, "message": message}]
    run.finished_at = datetime.now(UTC)
    if application.status == "ready_to_apply":
        transition_application(
            db,
            application,
            "needs_review",
            f"Offline dry run stopped: {category.replace('_', ' ')}",
            enforce_phase_gate=False,
        )
    create_task(
        db,
        application,
        scholarship,
        category="field_mapping_review",
        title="Dry-run filling needs review",
        required_action=message,
    )
    refresh_priority(db, scholarship, application)
    record_event(db, "fill.blocked", f"Offline dry run stopped for {scholarship.canonical_name}", "warning")
    db.commit()
    return dry_run_fill_read(db, run)


@router.post("/{application_id}/dry-run-fill", response_model=DryRunFillRead)
def dry_run_fill(application_id: str, db: Session = Depends(get_db)) -> DryRunFillRead:
    application, scholarship = get_application_and_scholarship(db, application_id)
    system = get_or_create_settings(db)
    if system.emergency_stop:
        raise HTTPException(status_code=409, detail="Emergency stop blocks all browser actions")
    if system.operating_mode != "dry_run":
        raise HTTPException(status_code=409, detail="Set operating mode to Dry Run before filling")
    if not system.preparation_enabled:
        raise HTTPException(status_code=409, detail="Enable application preparation before filling")
    if application.status != "ready_to_apply":
        raise HTTPException(status_code=409, detail="Application must be ready to apply")
    if application.safety_status != "approved" or scholarship.eligibility_status != "eligible":
        raise HTTPException(status_code=409, detail="Approved safety and verified eligibility are required")

    inspection = latest_completed_inspection(db, application.id)
    if inspection is None or not inspection.page_content_hash:
        raise HTTPException(status_code=409, detail="A completed read-only inspection is required")
    if inspection.detected_barriers_json:
        raise HTTPException(status_code=409, detail="Manual checkpoints prevent dry-run filling")

    existing = db.scalar(
        select(DryRunFill)
        .where(
            DryRunFill.application_id == application.id,
            DryRunFill.browser_run_id == inspection.id,
            DryRunFill.status == "completed",
        )
        .order_by(DryRunFill.started_at.desc())
    )
    if existing:
        return dry_run_fill_read(db, existing)

    plans = list(
        db.scalars(
            select(FormFieldPlan)
            .where(FormFieldPlan.browser_run_id == inspection.id)
            .order_by(FormFieldPlan.ordinal)
        )
    )
    run = DryRunFill(
        application_id=application.id,
        browser_run_id=inspection.id,
        status="running",
        execution_scope="offline_synthetic",
        source_page_hash=inspection.page_content_hash,
        field_count=len(plans),
        started_at=datetime.now(UTC),
    )
    db.add(run)
    record_event(db, "fill.started", f"Started offline dry run for {scholarship.canonical_name}")
    db.commit()
    db.refresh(run)

    required_blockers = [
        plan
        for plan in plans
        if plan.required
        and not plan.disabled
        and (plan.disposition != "auto_answerable" or plan.input_type not in SUPPORTED_INPUT_TYPES)
    ]
    if required_blockers:
        labels = ", ".join(plan.label for plan in required_blockers[:5])
        return block_fill(
            db,
            run,
            application,
            scholarship,
            "unresolved_required_fields",
            f"Required fields are not deterministically fillable: {labels}.",
        )

    fillable = [
        plan
        for plan in plans
        if not plan.disabled
        and plan.disposition == "auto_answerable"
        and plan.input_type in SUPPORTED_INPUT_TYPES
        and plan.profile_field_key
    ]
    profile_keys = {plan.profile_field_key for plan in fillable if plan.profile_field_key}
    profiles = list(db.scalars(select(ProfileField).where(ProfileField.field_key.in_(profile_keys))))
    by_key = {profile.field_key: profile for profile in profiles}
    candidates: list[FillCandidate] = []
    for plan in fillable:
        profile = by_key.get(plan.profile_field_key or "")
        if profile is None or profile.status != "verified" or profile.value_json is None:
            return block_fill(
                db,
                run,
                application,
                scholarship,
                "profile_changed",
                f"The verified profile source for '{plan.label}' changed after inspection.",
            )
        candidates.append(FillCandidate(plan=plan, profile=profile))

    try:
        result = execute_offline_dry_run(candidates)
    except DryRunFillError as error:
        return block_fill(db, run, application, scholarship, error.category, str(error))

    for item in result.fields:
        db.add(
            FillFieldEvidence(
                fill_run_id=run.id,
                application_id=application.id,
                field_plan_id=item.field_plan_id,
                profile_field_id=item.profile_field_id,
                ordinal=item.ordinal,
                label=item.label,
                profile_field_key=item.profile_field_key,
                profile_status=item.profile_status,
                source_reference=item.source_reference,
                profile_updated_at=item.profile_updated_at,
                value_type=item.value_type,
                value_hash=item.value_hash,
                result="filled",
                reason="Offline control matched the hashed value from the verified canonical profile",
            )
        )
    run.status = "completed"
    run.manifest_hash = result.manifest_hash
    run.filled_field_count = len(result.fields)
    run.skipped_field_count = len(plans) - len(result.fields)
    run.finished_at = datetime.now(UTC)
    required_count = len([plan for plan in plans if plan.required and not plan.disabled])
    required_filled = len(
        [item for item in result.fields if next(plan for plan in plans if plan.id == item.field_plan_id).required]
    )
    application.completion_percent = (
        round(100 * required_filled / required_count, 1) if required_count else 100.0
    )
    application.version += 1
    db.add(
        ApplicationEvent(
            application_id=application.id,
            from_status=application.status,
            to_status=application.status,
            reason="Offline dry-run filling completed; no value was entered on an external site",
            actor="system",
            metadata_json={"fill_run_id": run.id, "manifest_hash": result.manifest_hash},
        )
    )
    refresh_priority(db, scholarship, application)
    record_event(db, "fill.completed", f"Completed offline dry run for {scholarship.canonical_name}")
    db.commit()
    return dry_run_fill_read(db, run)


@router.get("/{application_id}/dry-run-fills", response_model=list[DryRunFillRead])
def dry_run_history(application_id: str, db: Session = Depends(get_db)) -> list[DryRunFillRead]:
    application, _ = get_application_and_scholarship(db, application_id)
    runs = list(
        db.scalars(
            select(DryRunFill)
            .where(DryRunFill.application_id == application.id)
            .order_by(DryRunFill.started_at.desc(), DryRunFill.id.desc())
        )
    )
    return [dry_run_fill_read(db, run) for run in runs]
