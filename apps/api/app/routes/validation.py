from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.browser.dry_run import DryRunFillError, scalar_value, value_hash
from app.core.eligibility import evaluate_scholarship
from app.core.priority import refresh_priority
from app.core.safety import assess_application_safety, persist_safety_assessment
from app.core.state_machine import transition_application
from app.core.submission_validation import (
    ValidationCheck,
    barrier_checks,
    blocked,
    canonical_manifest_hash,
    check_dicts,
    deadline_check,
    passed,
    required_document_types,
)
from app.core.validation_serialization import validation_snapshot_read
from app.db import get_db
from app.models import (
    ApplicationEvent,
    BrowserRun,
    Document,
    DomainPolicy,
    DryRunFill,
    FillFieldEvidence,
    FormFieldPlan,
    ManualTask,
    ProfileField,
    SafetyAssessment,
    ValidationSnapshot,
)
from app.routes.applications import create_task, get_application_and_scholarship
from app.schemas import ValidationSnapshotRead
from app.services import get_or_create_settings, record_event

router = APIRouter(prefix="/api/applications", tags=["pre-submission validation"])


def comparable_timestamp(value: datetime) -> str:
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return value.astimezone(UTC).isoformat()


def current_safety_assessment(db: Session, application, scholarship) -> SafetyAssessment:
    decision = assess_application_safety(db, scholarship)
    current = db.scalar(
        select(SafetyAssessment)
        .where(
            SafetyAssessment.application_id == application.id,
            SafetyAssessment.is_current.is_(True),
        )
        .order_by(SafetyAssessment.assessed_at.desc())
    )
    policy = (
        db.scalar(select(DomainPolicy).where(DomainPolicy.domain == decision.domain))
        if decision.domain
        else None
    )
    if (
        current is None
        or current.status != decision.status
        or current.application_domain != decision.domain
        or current.policy_id != (policy.id if policy else None)
    ):
        current = persist_safety_assessment(db, scholarship, application.id)
        db.flush()
    application.safety_status = decision.status
    return current


def document_type_matches(required_type: str, document_type: str) -> bool:
    normalized = document_type.casefold().replace("-", "_").replace(" ", "_")
    if required_type == "transcript":
        return normalized in {"transcript", "official_transcript", "unofficial_transcript"}
    return normalized == required_type


def selected_document_manifest(
    documents: list[Document],
    requirements,
    checks: list[ValidationCheck],
) -> list[dict[str, str | None]]:
    manifest: list[dict[str, str | None]] = []
    now = datetime.now(UTC)
    for required_type in required_document_types(requirements):
        candidates = []
        for document in documents:
            expires_at = document.expires_at
            if expires_at is not None and expires_at.tzinfo is None:
                expires_at = expires_at.replace(tzinfo=UTC)
            if (
                document_type_matches(required_type, document.document_type)
                and document.auto_upload_allowed
                and (expires_at is None or expires_at > now)
            ):
                candidates.append(document)
        if not candidates:
            checks.append(
                blocked(
                    f"document_{required_type}_missing",
                    f"No current auto-upload-approved {required_type.replace('_', ' ')} is available",
                )
            )
        elif len(candidates) > 1:
            checks.append(
                blocked(
                    f"document_{required_type}_ambiguous",
                    f"Multiple approved {required_type.replace('_', ' ')} documents require an explicit choice",
                )
            )
        else:
            document = candidates[0]
            checks.append(
                passed(
                    f"document_{required_type}",
                    f"Exactly one approved {required_type.replace('_', ' ')} is available",
                )
            )
            manifest.append(
                {
                    "document_id": document.id,
                    "document_type": document.document_type,
                    "version": document.version,
                    "sha256": document.sha256,
                    "expires_at": document.expires_at.isoformat() if document.expires_at else None,
                }
            )
    if not required_document_types(requirements):
        checks.append(passed("documents", "No document upload is required by the recorded requirements"))
    return manifest


@router.post("/{application_id}/validate-submission", response_model=ValidationSnapshotRead)
def validate_submission(application_id: str, db: Session = Depends(get_db)) -> ValidationSnapshotRead:
    application, scholarship = get_application_and_scholarship(db, application_id)
    system = get_or_create_settings(db)
    if system.emergency_stop:
        raise HTTPException(status_code=409, detail="Emergency stop blocks validation and browser actions")
    if system.operating_mode != "dry_run":
        raise HTTPException(status_code=409, detail="Pre-submission validation is restricted to Dry Run mode")
    if not system.preparation_enabled:
        raise HTTPException(status_code=409, detail="Enable application preparation before validation")
    if application.status != "ready_to_apply":
        raise HTTPException(status_code=409, detail="Application must be ready to apply")

    latest_inspection = db.scalar(
        select(BrowserRun)
        .where(BrowserRun.application_id == application.id)
        .order_by(BrowserRun.started_at.desc(), BrowserRun.id.desc())
    )
    fill = db.scalar(
        select(DryRunFill)
        .where(DryRunFill.application_id == application.id)
        .order_by(DryRunFill.started_at.desc(), DryRunFill.id.desc())
    )
    if latest_inspection is None or fill is None or not fill.manifest_hash:
        raise HTTPException(status_code=409, detail="A completed inspection and offline fill are required")

    checks: list[ValidationCheck] = []
    checks.append(
        passed("live_submission_lock", "Live submission remains disabled at the API state-machine boundary")
        if not system.automatic_submission_enabled
        else blocked("live_submission_enabled", "Automatic submission must remain disabled during dry-run validation")
    )
    checks.append(
        passed("prior_submission", "No prior submission is recorded")
        if application.submitted_at is None
        else blocked("duplicate_submission", "A prior submission timestamp already exists")
    )
    checks.append(
        passed("legitimacy", "Legitimacy screening permits preparation")
        if scholarship.legitimacy_status in {"verified", "likely_legitimate"}
        else blocked("legitimacy", "Scholarship legitimacy is blocked or still requires review")
    )
    checks.append(deadline_check(scholarship.deadline, scholarship.deadline_type))

    evaluation_checks = evaluate_scholarship(db, scholarship)
    db.flush()
    eligibility_run_id = evaluation_checks[0].evaluation_run_id if evaluation_checks else None
    checks.append(
        passed("eligibility", "All current deterministic eligibility checks pass")
        if evaluation_checks
        and scholarship.eligibility_status == "eligible"
        and all(item.result == "pass" for item in evaluation_checks)
        else blocked("eligibility", "Eligibility is not fully verified by current deterministic checks")
    )

    safety = current_safety_assessment(db, application, scholarship)
    checks.append(
        passed("destination_safety", "The exact application destination remains approved")
        if safety.status == "approved"
        else blocked("destination_safety", "The exact application destination no longer passes safety review")
    )

    checks.append(
        passed("inspection_current", "The fill references the latest completed inspection")
        if latest_inspection.id == fill.browser_run_id and latest_inspection.status == "completed"
        else blocked("inspection_changed", "A newer or incomplete inspection supersedes the fill evidence")
    )
    checks.append(
        passed("page_hash", "Inspection and fill evidence use the same page hash")
        if latest_inspection.page_content_hash
        and latest_inspection.page_content_hash == fill.source_page_hash
        else blocked("page_changed", "The inspected page hash does not match the fill evidence")
    )
    checks.extend(barrier_checks(list(latest_inspection.detected_barriers_json)))
    checks.append(
        passed("offline_fill", "The offline fill completed with an immutable manifest hash")
        if fill.status == "completed"
        else blocked("offline_fill", "The latest offline fill did not complete")
    )

    plans = list(
        db.scalars(
            select(FormFieldPlan)
            .where(FormFieldPlan.browser_run_id == latest_inspection.id)
            .order_by(FormFieldPlan.ordinal)
        )
    )
    evidence = list(
        db.scalars(
            select(FillFieldEvidence)
            .where(FillFieldEvidence.fill_run_id == fill.id)
            .order_by(FillFieldEvidence.ordinal)
        )
    )
    evidence_by_plan = {item.field_plan_id: item for item in evidence}
    missing_required = [
        plan.label
        for plan in plans
        if plan.required and not plan.disabled and plan.id not in evidence_by_plan
    ]
    checks.append(
        blocked(
            "required_field_coverage",
            f"Required fields lack verified fill evidence: {', '.join(missing_required[:5])}",
        )
        if missing_required
        else passed("required_field_coverage", "Every active required field has fill evidence")
    )

    profile_manifest: list[dict[str, str | int]] = []
    profile_by_id = {
        profile.id: profile
        for profile in db.scalars(
            select(ProfileField).where(
                ProfileField.id.in_({item.profile_field_id for item in evidence})
            )
        )
    }
    for item in evidence:
        profile = profile_by_id.get(item.profile_field_id)
        current_hash = None
        if profile and profile.status == "verified" and profile.value_json is not None:
            try:
                value_type, serialized = scalar_value(profile.value_json)
                current_hash = value_hash(value_type, serialized)
            except DryRunFillError:
                current_hash = None
        unchanged = bool(
            profile
            and profile.status == "verified"
            and profile.field_key == item.profile_field_key
            and profile.source == item.source_reference
            and comparable_timestamp(profile.updated_at) == comparable_timestamp(item.profile_updated_at)
            and current_hash == item.value_hash
        )
        checks.append(
            passed(f"profile_{item.ordinal}", f"Verified profile provenance is current for '{item.label}'")
            if unchanged
            else blocked(f"profile_{item.ordinal}", f"Profile evidence changed for '{item.label}'")
        )
        profile_manifest.append(
            {
                "field_plan_id": item.field_plan_id,
                "profile_field_id": item.profile_field_id,
                "profile_field_key": item.profile_field_key,
                "profile_status": profile.status if profile else "missing",
                "profile_updated_at": (
                    comparable_timestamp(profile.updated_at) if profile else "missing"
                ),
                "value_hash": current_hash or "unavailable",
            }
        )

    documents = list(db.scalars(select(Document).order_by(Document.created_at, Document.id)))
    document_manifest = selected_document_manifest(
        documents,
        scholarship.requirements_json,
        checks,
    )
    open_tasks = list(
        db.scalars(
            select(ManualTask).where(
                ManualTask.application_id == application.id,
                ManualTask.status == "open",
            )
        )
    )
    checks.append(
        blocked("open_tasks", f"{len(open_tasks)} unresolved action queue item(s) remain")
        if open_tasks
        else passed("open_tasks", "No unresolved action queue item remains")
    )

    check_rows = check_dicts(checks)
    blockers = [item for item in check_rows if item["status"] == "blocked"]
    manifest_payload = {
        "application_id": application.id,
        "scholarship_id": scholarship.id,
        "browser_run_id": latest_inspection.id,
        "dry_run_fill_id": fill.id,
        "safety_assessment_id": safety.id,
        "source_page_hash": latest_inspection.page_content_hash,
        "fill_manifest_hash": fill.manifest_hash,
        "eligibility_run_id": eligibility_run_id,
        "deadline": scholarship.deadline.isoformat() if scholarship.deadline else None,
        "deadline_type": scholarship.deadline_type,
        "checks": check_rows,
        "profile_manifest": profile_manifest,
        "document_manifest": document_manifest,
    }
    validation_hash = canonical_manifest_hash(manifest_payload)
    snapshot = ValidationSnapshot(
        application_id=application.id,
        browser_run_id=latest_inspection.id,
        dry_run_fill_id=fill.id,
        safety_assessment_id=safety.id,
        status="blocked" if blockers else "passed",
        operating_mode="dry_run",
        source_page_hash=latest_inspection.page_content_hash or fill.source_page_hash,
        fill_manifest_hash=fill.manifest_hash,
        validation_manifest_hash=validation_hash,
        eligibility_run_id=eligibility_run_id,
        checks_json=check_rows,
        blockers_json=blockers,
        profile_manifest_json=profile_manifest,
        document_manifest_json=document_manifest,
    )
    db.add(snapshot)
    db.flush()
    if blockers:
        transition_application(
            db,
            application,
            "needs_review",
            "Dry-run pre-submission validation found blocking conditions",
            metadata={"validation_snapshot_id": snapshot.id},
            enforce_phase_gate=False,
        )
        create_task(
            db,
            application,
            scholarship,
            category="submission_validation",
            title="Pre-submission validation needs review",
            required_action="; ".join(item["message"] for item in blockers[:5]),
        )
        record_event(db, "validation.blocked", f"Validation blocked for {scholarship.canonical_name}", "warning")
    else:
        application.version += 1
        db.add(
            ApplicationEvent(
                application_id=application.id,
                from_status=application.status,
                to_status=application.status,
                reason="Dry-run pre-submission validation passed; live submission remains disabled",
                actor="system",
                metadata_json={"validation_snapshot_id": snapshot.id},
            )
        )
        record_event(db, "validation.passed", f"Dry-run validation passed for {scholarship.canonical_name}")
    refresh_priority(db, scholarship, application)
    db.commit()
    return validation_snapshot_read(snapshot)


@router.get("/{application_id}/validations", response_model=list[ValidationSnapshotRead])
def validation_history(
    application_id: str,
    db: Session = Depends(get_db),
) -> list[ValidationSnapshotRead]:
    application, _ = get_application_and_scholarship(db, application_id)
    snapshots = list(
        db.scalars(
            select(ValidationSnapshot)
            .where(ValidationSnapshot.application_id == application.id)
            .order_by(ValidationSnapshot.created_at.desc(), ValidationSnapshot.id.desc())
        )
    )
    return [validation_snapshot_read(snapshot) for snapshot in snapshots]
