import re
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import ProfileField
from app.schemas import ProfileFieldRead, ProfileFieldWrite
from app.services import record_event

router = APIRouter(prefix="/api/profile", tags=["profile"])
FIELD_KEY = re.compile(r"^[a-z][a-z0-9_]*(\.[a-z][a-z0-9_]*)*$")


@router.get("", response_model=list[ProfileFieldRead])
def list_profile_fields(db: Session = Depends(get_db)) -> list[ProfileField]:
    return list(db.scalars(select(ProfileField).order_by(ProfileField.field_key)))


@router.put("/{field_key:path}", response_model=ProfileFieldRead)
def upsert_profile_field(
    field_key: str, payload: ProfileFieldWrite, db: Session = Depends(get_db)
) -> ProfileField:
    if not FIELD_KEY.fullmatch(field_key):
        raise HTTPException(status_code=422, detail="Use a dotted lowercase field key, such as education.gpa")
    item = db.scalar(select(ProfileField).where(ProfileField.field_key == field_key))
    if item is None:
        item = ProfileField(field_key=field_key)
        db.add(item)
    item.value_json = payload.value
    item.status = payload.status
    item.source = payload.source
    item.last_verified_at = datetime.now(UTC) if payload.status == "verified" else None
    record_event(db, "profile.updated", f"Profile field {field_key} was updated")
    db.commit()
    db.refresh(item)
    return item

