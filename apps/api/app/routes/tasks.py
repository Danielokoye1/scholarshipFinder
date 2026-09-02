from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import ManualTask
from app.routes.applications import task_read
from app.schemas import ManualTaskRead, ManualTaskUpdate
from app.services import record_event

router = APIRouter(prefix="/api/tasks", tags=["action queue"])


@router.get("", response_model=list[ManualTaskRead])
def list_tasks(
    task_status: str = Query(default="open", pattern="^(open|resolved|dismissed|all)$"),
    category: str | None = Query(default=None, max_length=60),
    limit: int = Query(default=100, ge=1, le=500),
    db: Session = Depends(get_db),
) -> list[ManualTaskRead]:
    filters = []
    if task_status != "all":
        filters.append(ManualTask.status == task_status)
    if category:
        filters.append(ManualTask.category == category)
    tasks = list(
        db.scalars(
            select(ManualTask)
            .where(*filters)
            .order_by(
                ManualTask.priority_score.desc(),
                ManualTask.deadline.is_(None),
                ManualTask.deadline.asc(),
            )
            .limit(limit)
        )
    )
    return [task_read(task) for task in tasks]


@router.patch("/{task_id}", response_model=ManualTaskRead)
def update_task(
    task_id: str, payload: ManualTaskUpdate, db: Session = Depends(get_db)
) -> ManualTaskRead:
    task = db.get(ManualTask, task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")
    task.status = payload.status
    task.resolved_at = datetime.now(UTC)
    record_event(db, "task.updated", f"Action queue item marked {payload.status}")
    db.commit()
    db.refresh(task)
    return task_read(task)

