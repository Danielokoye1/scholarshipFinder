from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.config import settings
from app.db import get_db
from app.schemas import SystemSettingsRead, SystemSettingsWrite
from app.services import get_or_create_settings, record_event

router = APIRouter(prefix="/api/system", tags=["system"])


@router.get("/settings", response_model=SystemSettingsRead)
def read_settings(db: Session = Depends(get_db)):
    return get_or_create_settings(db)


@router.patch("/settings", response_model=SystemSettingsRead)
def update_settings(payload: SystemSettingsWrite, db: Session = Depends(get_db)):
    current = get_or_create_settings(db)
    updates = payload.model_dump(exclude_none=True)
    if updates.get("automatic_submission_enabled"):
        raise HTTPException(status_code=409, detail="Automatic submission is unavailable until the live-mode safety gate is implemented")
    if updates.get("operating_mode") == "autonomous":
        raise HTTPException(status_code=409, detail="Autonomous mode is unavailable until the live-mode safety gate is implemented")
    if updates.get("email_monitoring_enabled") and not settings.gmail_token_path.resolve().is_file():
        raise HTTPException(
            status_code=409,
            detail="Connect the scholarship Gmail account before enabling email monitoring",
        )
    for key, value in updates.items():
        setattr(current, key, value)
    record_event(db, "settings.updated", "Automation settings were updated")
    db.commit()
    db.refresh(current)
    return current


@router.post("/pause", response_model=SystemSettingsRead)
def pause(db: Session = Depends(get_db)):
    current = get_or_create_settings(db)
    current.automation_status = "paused"
    record_event(db, "automation.paused", "Automation was paused")
    db.commit()
    db.refresh(current)
    return current


@router.post("/resume", response_model=SystemSettingsRead)
def resume(db: Session = Depends(get_db)):
    current = get_or_create_settings(db)
    if current.emergency_stop:
        raise HTTPException(status_code=409, detail="Clear the emergency stop before resuming")
    current.automation_status = "running"
    record_event(db, "automation.resumed", "Automation was resumed")
    db.commit()
    db.refresh(current)
    return current


@router.post("/emergency-stop", response_model=SystemSettingsRead)
def emergency_stop(db: Session = Depends(get_db)):
    current = get_or_create_settings(db)
    current.emergency_stop = True
    current.automation_status = "stopped"
    current.discovery_enabled = False
    current.eligibility_enabled = False
    current.preparation_enabled = False
    current.automatic_submission_enabled = False
    current.email_monitoring_enabled = False
    record_event(db, "automation.emergency_stop", "Emergency stop activated", "warning")
    db.commit()
    db.refresh(current)
    return current


@router.post("/clear-emergency-stop", response_model=SystemSettingsRead)
def clear_emergency_stop(db: Session = Depends(get_db)):
    current = get_or_create_settings(db)
    current.emergency_stop = False
    current.automation_status = "paused"
    record_event(db, "automation.emergency_stop_cleared", "Emergency stop cleared; automation remains paused")
    db.commit()
    db.refresh(current)
    return current
