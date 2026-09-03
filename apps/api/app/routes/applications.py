from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.core.application_workflow import create_application_task as create_task
from app.core.application_workflow import reconcile_application
from app.core.priority import refresh_priority
from app.browser.serialization import browser_run_read
from app.browser.fill_serialization import dry_run_fill_read
from app.core.validation_serialization import validation_snapshot_read
from app.core.safety import persist_safety_assessment
from app.core.state_machine import (
    InvalidTransition,
    record_initial_state,
    transition_application,
)
from app.db import get_db
from app.models import (
    Application,
    ApplicationEvent,
    BrowserRun,
    DryRunFill,
    ManualTask,
    SafetyAssessment,
    Scholarship,
    ValidationSnapshot,
)
from app.schemas import (
    ApplicationCreate,
    ApplicationDetail,
    ApplicationEventRead,
    ApplicationList,
    ApplicationStatus,
    ApplicationSummary,
    ApplicationTransitionWrite,
    ManualTaskRead,
    SafetyAssessmentRead,
)
from app.services import record_event

router = APIRouter(prefix="/api/applications", tags=["applications"])


def task_read(task: ManualTask) -> ManualTaskRead:
    return ManualTaskRead(
        id=task.id,
        application_id=task.application_id,
        scholarship_id=task.scholarship_id,
        category=task.category,
        title=task.title,
        required_action=task.required_action,
        status=task.status,
        direct_url=task.direct_url,
        priority_score=task.priority_score,
        deadline=task.deadline,
        resolved_at=task.resolved_at,
        created_at=task.created_at,
    )


def safety_read(item: SafetyAssessment | None) -> SafetyAssessmentRead | None:
    if item is None:
        return None
    return SafetyAssessmentRead(
        id=item.id,
        scholarship_id=item.scholarship_id,
        application_id=item.application_id,
        application_domain=item.application_domain,
        status=item.status,
        score=item.score,
        reasons=item.reasons_json,
        is_current=item.is_current,
        assessed_at=item.assessed_at,
    )


def application_summary(application: Application, scholarship: Scholarship) -> ApplicationSummary:
    return ApplicationSummary(
        id=application.id,
        scholarship_id=application.scholarship_id,
        scholarship_name=scholarship.canonical_name,
        provider=scholarship.provider,
        award_max_cents=scholarship.award_max_cents,
        deadline=scholarship.deadline,
        application_url=scholarship.application_url,
        status=application.status,
        safety_status=application.safety_status,
        automation_level=application.automation_level,
        completion_percent=application.completion_percent,
        priority_score=application.priority_score,
        manual_effort_score=application.manual_effort_score,
        submitted_at=application.submitted_at,
        version=application.version,
        updated_at=application.updated_at,
    )


def get_application_and_scholarship(
    db: Session, application_id: str
) -> tuple[Application, Scholarship]:
    application = db.get(Application, application_id)
    if application is None:
        raise HTTPException(status_code=404, detail="Application not found")
    scholarship = db.get(Scholarship, application.scholarship_id)
    if scholarship is None:
        raise HTTPException(status_code=409, detail="Application scholarship record is missing")
    return application, scholarship


def detail(db: Session, application: Application, scholarship: Scholarship) -> ApplicationDetail:
    current_safety = db.scalar(
        select(SafetyAssessment)
        .where(
            SafetyAssessment.application_id == application.id,
            SafetyAssessment.is_current.is_(True),
        )
        .order_by(SafetyAssessment.assessed_at.desc())
    )
    events = list(
        db.scalars(
            select(ApplicationEvent)
            .where(ApplicationEvent.application_id == application.id)
            .order_by(ApplicationEvent.created_at, ApplicationEvent.id)
        )
    )
    tasks = list(
        db.scalars(
            select(ManualTask)
            .where(ManualTask.application_id == application.id)
            .order_by(ManualTask.created_at, ManualTask.id)
        )
    )
    latest_inspection = db.scalar(
        select(BrowserRun)
        .where(BrowserRun.application_id == application.id)
        .order_by(BrowserRun.started_at.desc(), BrowserRun.id.desc())
    )
    latest_fill = db.scalar(
        select(DryRunFill)
        .where(DryRunFill.application_id == application.id)
        .order_by(DryRunFill.started_at.desc(), DryRunFill.id.desc())
    )
    latest_validation = db.scalar(
        select(ValidationSnapshot)
        .where(ValidationSnapshot.application_id == application.id)
        .order_by(ValidationSnapshot.created_at.desc(), ValidationSnapshot.id.desc())
    )
    base = application_summary(application, scholarship).model_dump()
    return ApplicationDetail(
        **base,
        eligibility_status=scholarship.eligibility_status,
        current_safety_assessment=safety_read(current_safety),
        latest_inspection=browser_run_read(db, latest_inspection) if latest_inspection else None,
        latest_fill=dry_run_fill_read(db, latest_fill) if latest_fill else None,
        latest_validation=(
            validation_snapshot_read(latest_validation) if latest_validation else None
        ),
        events=[
            ApplicationEventRead(
                id=event.id,
                from_status=event.from_status,
                to_status=event.to_status,
                reason=event.reason,
                actor=event.actor,
                metadata=event.metadata_json,
                created_at=event.created_at,
            )
            for event in events
        ],
        tasks=[task_read(task) for task in tasks],
    )


@router.post("", response_model=ApplicationDetail, status_code=status.HTTP_201_CREATED)
def create_application(
    payload: ApplicationCreate, response: Response, db: Session = Depends(get_db)
) -> ApplicationDetail:
    scholarship = db.get(Scholarship, payload.scholarship_id)
    if scholarship is None:
        raise HTTPException(status_code=404, detail="Scholarship not found")
    existing = db.scalar(
        select(Application).where(Application.scholarship_id == scholarship.id)
    )
    if existing:
        response.status_code = status.HTTP_200_OK
        return detail(db, existing, scholarship)

    application = Application(
        scholarship_id=scholarship.id,
        status="discovered",
        safety_status="review_required",
        automation_level=0,
        completion_percent=0,
        manual_effort_score=payload.manual_effort_score,
    )
    db.add(application)
    db.flush()
    record_initial_state(db, application, "Application record created from an opportunity")
    transition_application(
        db,
        application,
        "eligibility_check",
        "Evaluating eligibility and application safety",
        enforce_phase_gate=False,
    )
    safety = persist_safety_assessment(db, scholarship, application.id)
    reconcile_application(db, application, scholarship, safety)
    record_event(db, "application.created", f"Created workflow for {scholarship.canonical_name}")
    db.commit()
    return detail(db, application, scholarship)


@router.get("", response_model=ApplicationList)
def list_applications(
    q: str | None = Query(default=None, max_length=200),
    application_status: ApplicationStatus | None = Query(default=None),
    safety_status: str | None = Query(default=None, max_length=40),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
) -> ApplicationList:
    filters = []
    if q:
        term = f"%{q.strip()}%"
        filters.append(
            or_(Scholarship.canonical_name.ilike(term), Scholarship.provider.ilike(term))
        )
    if application_status:
        filters.append(Application.status == application_status)
    if safety_status:
        filters.append(Application.safety_status == safety_status)
    base = select(Application, Scholarship).join(
        Scholarship, Scholarship.id == Application.scholarship_id
    )
    total = db.scalar(
        select(func.count())
        .select_from(Application)
        .join(Scholarship, Scholarship.id == Application.scholarship_id)
        .where(*filters)
    ) or 0
    rows = db.execute(
        base.where(*filters)
        .order_by(Application.priority_score.desc(), Application.updated_at.desc())
        .offset(offset)
        .limit(limit)
    ).all()
    return ApplicationList(
        items=[application_summary(application, scholarship) for application, scholarship in rows],
        total=total,
        offset=offset,
        limit=limit,
    )


@router.get("/{application_id}", response_model=ApplicationDetail)
def application_detail(application_id: str, db: Session = Depends(get_db)) -> ApplicationDetail:
    application, scholarship = get_application_and_scholarship(db, application_id)
    return detail(db, application, scholarship)


@router.post("/{application_id}/transition", response_model=ApplicationDetail)
def transition(
    application_id: str,
    payload: ApplicationTransitionWrite,
    db: Session = Depends(get_db),
) -> ApplicationDetail:
    application, scholarship = get_application_and_scholarship(db, application_id)
    if application.version != payload.expected_version:
        raise HTTPException(
            status_code=409,
            detail="Application changed since it was loaded; refresh before trying again",
        )
    try:
        transition_application(
            db,
            application,
            payload.to_status,
            payload.reason,
            actor="user",
        )
    except InvalidTransition as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    refresh_priority(db, scholarship, application)
    record_event(db, "application.transitioned", f"Updated {scholarship.canonical_name}")
    db.commit()
    return detail(db, application, scholarship)


@router.post("/{application_id}/reassess-safety", response_model=ApplicationDetail)
def reassess_safety(
    application_id: str, db: Session = Depends(get_db)
) -> ApplicationDetail:
    application, scholarship = get_application_and_scholarship(db, application_id)
    assessment = persist_safety_assessment(db, scholarship, application.id)
    application.safety_status = assessment.status
    if (
        application.status == "needs_review"
        and assessment.status == "approved"
        and scholarship.eligibility_status == "eligible"
    ):
        transition_application(
            db,
            application,
            "ready_to_apply",
            "Application domain was manually approved and safety checks passed",
            enforce_phase_gate=False,
        )
        for task in db.scalars(
            select(ManualTask).where(
                ManualTask.application_id == application.id,
                ManualTask.category == "safety_review",
                ManualTask.status == "open",
            )
        ):
            task.status = "resolved"
            task.resolved_at = assessment.assessed_at
    elif application.status == "ready_to_apply" and assessment.status != "approved":
        transition_application(
            db,
            application,
            "needs_review",
            "Application safety approval is no longer valid",
            enforce_phase_gate=False,
        )
    refresh_priority(db, scholarship, application)
    record_event(db, "safety.reassessed", f"Reassessed {scholarship.canonical_name}")
    db.commit()
    return detail(db, application, scholarship)
