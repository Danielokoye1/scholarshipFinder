import hashlib
import os
import re
import uuid
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.db import get_db
from app.models import Document
from app.schemas import DocumentApprovalWrite, DocumentRead
from app.services import record_event

router = APIRouter(prefix="/api/documents", tags=["documents"])
ALLOWED_EXTENSIONS = {".pdf", ".doc", ".docx", ".txt", ".png", ".jpg", ".jpeg"}
SINGLE_CURRENT_DOCUMENT_TYPES = {"resume"}


def safe_extension(filename: str) -> str:
    extension = Path(filename).suffix.lower()
    if extension not in ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=415, detail="Unsupported document type")
    return extension


@router.get("", response_model=list[DocumentRead])
def list_documents(db: Session = Depends(get_db)) -> list[Document]:
    return list(db.scalars(select(Document).order_by(Document.created_at.desc())))


@router.post("", response_model=DocumentRead, status_code=status.HTTP_201_CREATED)
async def upload_document(
    file: UploadFile = File(...),
    document_type: str = Form(..., min_length=2, max_length=80),
    version: str = Form("1", max_length=40),
    expires_at: datetime | None = Form(None),
    db: Session = Depends(get_db),
) -> Document:
    original_name = Path(file.filename or "document").name
    extension = safe_extension(original_name)
    clean_type = re.sub(r"[^a-z0-9_-]", "-", document_type.lower()).strip("-")
    document_id = str(uuid.uuid4())
    stored_name = f"{document_id}-{clean_type}{extension}"
    storage = settings.document_storage_path.resolve()
    storage.mkdir(parents=True, exist_ok=True, mode=0o700)
    os.chmod(storage, 0o700)
    target = storage / stored_name
    digest = hashlib.sha256()
    size = 0
    try:
        with target.open("xb") as output:
            os.chmod(target, 0o600)
            while chunk := await file.read(1024 * 1024):
                size += len(chunk)
                if size > settings.max_document_bytes:
                    raise HTTPException(status_code=413, detail="Document exceeds the 25 MB limit")
                digest.update(chunk)
                output.write(chunk)
    except Exception:
        target.unlink(missing_ok=True)
        raise
    finally:
        await file.close()

    item = Document(
        id=document_id,
        original_filename=original_name,
        stored_filename=stored_name,
        document_type=clean_type,
        version=version,
        content_type=file.content_type,
        size_bytes=size,
        sha256=digest.hexdigest(),
        auto_upload_allowed=False,
        expires_at=expires_at,
    )
    previous_approved = (
        list(
            db.scalars(
                select(Document).where(
                    Document.document_type == clean_type,
                    Document.auto_upload_allowed.is_(True),
                )
            )
        )
        if clean_type in SINGLE_CURRENT_DOCUMENT_TYPES
        else []
    )
    for previous in previous_approved:
        previous.auto_upload_allowed = False
    db.add(item)
    record_event(db, "document.added", f"Document metadata added for {original_name}")
    if previous_approved:
        record_event(
            db,
            "document.approval_changed",
            f"Automated upload was revoked for {len(previous_approved)} older {clean_type} document(s)",
            "warning",
        )
    db.commit()
    db.refresh(item)
    return item


@router.patch("/{document_id}/approval", response_model=DocumentRead)
def update_approval(
    document_id: str, payload: DocumentApprovalWrite, db: Session = Depends(get_db)
) -> Document:
    item = db.get(Document, document_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Document not found")
    item.auto_upload_allowed = payload.auto_upload_allowed
    record_event(
        db,
        "document.approval_changed",
        f"Automated upload {'approved' if payload.auto_upload_allowed else 'revoked'} for {item.original_filename}",
    )
    db.commit()
    db.refresh(item)
    return item
