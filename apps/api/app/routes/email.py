from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import settings
from app.db import get_db
from app.gmail_monitor import GMAIL_METADATA_SCOPE
from app.models import EmailMessage
from app.schemas import EmailMessageRead, EmailStatusRead
from app.services import get_or_create_settings

router = APIRouter(prefix="/api/email", tags=["email monitoring"])


@router.get("/status", response_model=EmailStatusRead)
def email_status(db: Session = Depends(get_db)) -> EmailStatusRead:
    system = get_or_create_settings(db)
    indexed = db.scalar(select(func.count()).select_from(EmailMessage)) or 0
    actionable = db.scalar(
        select(func.count()).select_from(EmailMessage).where(EmailMessage.is_actionable.is_(True))
    ) or 0
    last_sync = db.scalar(select(func.max(EmailMessage.last_seen_at)))
    db.commit()
    return EmailStatusRead(
        provider="Gmail",
        client_credentials_present=settings.gmail_client_secret_path.resolve().is_file(),
        authorization_token_present=settings.gmail_token_path.resolve().is_file(),
        monitoring_enabled=system.email_monitoring_enabled,
        scope=GMAIL_METADATA_SCOPE,
        messages_indexed=indexed,
        actionable_messages=actionable,
        last_sync_at=last_sync,
    )


@router.get("/messages", response_model=list[EmailMessageRead])
def email_messages(
    actionable_only: bool = False,
    limit: int = Query(default=50, ge=1, le=250),
    db: Session = Depends(get_db),
) -> list[EmailMessageRead]:
    query = select(EmailMessage)
    if actionable_only:
        query = query.where(EmailMessage.is_actionable.is_(True))
    messages = list(db.scalars(query.order_by(EmailMessage.received_at.desc()).limit(limit)))
    return [
        EmailMessageRead(
            provider_message_id=item.provider_message_id,
            sender=item.sender,
            subject=item.subject,
            received_at=item.received_at,
            category=item.category,
            is_unread=item.is_unread,
            is_actionable=item.is_actionable,
        )
        for item in messages
    ]
