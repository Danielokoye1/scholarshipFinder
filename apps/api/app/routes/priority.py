from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.priority import get_or_create_priority_settings, refresh_priority
from app.db import get_db
from app.models import Application, ManualTask, PrioritySettings, Scholarship
from app.schemas import PrioritySettingsRead, PrioritySettingsWrite
from app.services import record_event

router = APIRouter(prefix="/api/priority", tags=["priority"])


def priority_read(item: PrioritySettings) -> PrioritySettingsRead:
    return PrioritySettingsRead.model_validate(item, from_attributes=True)


@router.get("/settings", response_model=PrioritySettingsRead)
def read_priority_settings(db: Session = Depends(get_db)) -> PrioritySettingsRead:
    settings = get_or_create_priority_settings(db)
    db.commit()
    return priority_read(settings)


@router.put("/settings", response_model=PrioritySettingsRead)
def update_priority_settings(
    payload: PrioritySettingsWrite, db: Session = Depends(get_db)
) -> PrioritySettingsRead:
    settings = get_or_create_priority_settings(db)
    for key, value in payload.model_dump().items():
        setattr(settings, key, value)
    recalculate_records(db)
    record_event(db, "priority.settings_updated", "Application priority settings were updated")
    db.commit()
    db.refresh(settings)
    return priority_read(settings)


def recalculate_records(db: Session) -> int:
    applications = {
        application.scholarship_id: application
        for application in db.scalars(select(Application))
    }
    count = 0
    for scholarship in db.scalars(select(Scholarship)):
        application = applications.get(scholarship.id)
        refresh_priority(db, scholarship, application)
        if application:
            for task in db.scalars(
                select(ManualTask).where(
                    ManualTask.application_id == application.id,
                    ManualTask.status == "open",
                )
            ):
                task.priority_score = application.priority_score
        count += 1
    db.flush()
    return count


@router.post("/recalculate", response_model=dict[str, int])
def recalculate(db: Session = Depends(get_db)) -> dict[str, int]:
    count = recalculate_records(db)
    record_event(db, "priority.recalculated", f"Recalculated {count} scholarship priorities")
    db.commit()
    return {"recalculated": count}
