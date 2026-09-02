from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import ManualTask, Scholarship, SystemEvent
from app.schemas import DashboardResponse
from app.services import dashboard_metrics, get_or_create_settings

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])


@router.get("", response_model=DashboardResponse)
def dashboard(db: Session = Depends(get_db)) -> DashboardResponse:
    settings = get_or_create_settings(db)
    activity = list(db.scalars(select(SystemEvent).order_by(SystemEvent.created_at.desc()).limit(8)))
    tasks = list(
        db.scalars(
            select(ManualTask)
            .where(ManualTask.status == "open")
            .order_by(ManualTask.deadline.asc(), ManualTask.created_at.asc())
            .limit(6)
        )
    )
    deadline_limit = datetime.now(UTC) + timedelta(days=30)
    deadlines = list(
        db.scalars(
            select(Scholarship)
            .where(Scholarship.deadline.is_not(None), Scholarship.deadline <= deadline_limit)
            .order_by(Scholarship.deadline.asc())
            .limit(6)
        )
    )
    return DashboardResponse(
        metrics=dashboard_metrics(db),
        settings=settings,
        activity=activity,
        attention=[
            {
                "id": task.id,
                "category": task.category,
                "title": task.title,
                "required_action": task.required_action,
                "deadline": task.deadline,
            }
            for task in tasks
        ],
        upcoming_deadlines=[
            {
                "id": scholarship.id,
                "name": scholarship.canonical_name,
                "provider": scholarship.provider,
                "deadline": scholarship.deadline,
                "award_max_cents": scholarship.award_max_cents,
            }
            for scholarship in deadlines
        ],
    )

