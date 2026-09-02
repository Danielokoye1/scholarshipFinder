import re
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.core.profile_intelligence import (
    FIELD_BY_KEY,
    materialize_derived_fields,
    normalize_profile_value,
    profile_review,
)
from app.models import ProfileField
from app.schemas import (
    ProfileBulkWrite,
    ProfileFieldRead,
    ProfileFieldWrite,
    ProfileOverviewRead,
)
from app.services import record_event

router = APIRouter(prefix="/api/profile", tags=["profile"])
FIELD_KEY = re.compile(r"^[a-z][a-z0-9_]*(\.[a-z][a-z0-9_]*)*$")


@router.get("", response_model=list[ProfileFieldRead])
def list_profile_fields(db: Session = Depends(get_db)) -> list[ProfileField]:
    return list(db.scalars(select(ProfileField).order_by(ProfileField.field_key)))


@router.get("/overview", response_model=ProfileOverviewRead)
def get_profile_overview(db: Session = Depends(get_db)) -> dict:
    overview = profile_review(db)
    if db.new or db.dirty:
        db.commit()
    return overview


@router.put("/overview", response_model=ProfileOverviewRead)
def update_profile_overview(payload: ProfileBulkWrite, db: Session = Depends(get_db)) -> dict:
    stored = {
        item.field_key: item
        for item in db.scalars(
            select(ProfileField).where(
                ProfileField.field_key.in_([entry.field_key for entry in payload.items])
            )
        )
    }
    for entry in payload.items:
        if entry.field_key not in FIELD_BY_KEY:
            raise HTTPException(
                status_code=422,
                detail=f"{entry.field_key} is not a supported structured profile field",
            )
        try:
            value = normalize_profile_value(entry.field_key, entry.value)
        except ValueError as error:
            raise HTTPException(status_code=422, detail=f"{entry.field_key}: {error}") from error
        item = stored.get(entry.field_key)
        if item is None:
            item = ProfileField(field_key=entry.field_key)
            db.add(item)
        item.value_json = value
        item.status = entry.status
        item.source = entry.source
        item.last_verified_at = datetime.now(UTC) if entry.status == "verified" else None
    materialize_derived_fields(db)
    record_event(db, "profile.updated", f"{len(payload.items)} structured profile fields were reviewed")
    db.commit()
    return profile_review(db)


@router.put("/{field_key:path}", response_model=ProfileFieldRead)
def upsert_profile_field(
    field_key: str, payload: ProfileFieldWrite, db: Session = Depends(get_db)
) -> ProfileField:
    if not FIELD_KEY.fullmatch(field_key):
        raise HTTPException(status_code=422, detail="Use a dotted lowercase field key, such as education.gpa")
    try:
        value = normalize_profile_value(field_key, payload.value)
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    item = db.scalar(select(ProfileField).where(ProfileField.field_key == field_key))
    if item is None:
        item = ProfileField(field_key=field_key)
        db.add(item)
    item.value_json = value
    item.status = payload.status
    item.source = payload.source
    item.last_verified_at = datetime.now(UTC) if payload.status == "verified" else None
    materialize_derived_fields(db)
    record_event(db, "profile.updated", f"Profile field {field_key} was updated")
    db.commit()
    db.refresh(item)
    return item
