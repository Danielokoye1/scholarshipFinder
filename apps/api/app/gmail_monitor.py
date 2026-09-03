import argparse
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from sqlalchemy import func, select

from app.config import settings
from app.db import SessionLocal
from app.models import EmailMessage, ProfileField
from app.services import get_or_create_settings, record_event


GMAIL_METADATA_SCOPE = "https://www.googleapis.com/auth/gmail.metadata"
SCOPES = [GMAIL_METADATA_SCOPE]

CATEGORY_TERMS = (
    (
        "awarded",
        ("congratulations", "scholarship recipient", "selected for an award", "award notification"),
        True,
    ),
    ("finalist", ("finalist", "interview invitation", "advance to the next round"), True),
    (
        "rejected",
        ("not selected", "unable to offer", "regret to inform", "not chosen"),
        False,
    ),
    (
        "action_required",
        (
            "action required",
            "missing information",
            "application incomplete",
            "verification required",
            "deadline reminder",
            "recommendation request",
        ),
        True,
    ),
    (
        "acknowledged",
        (
            "application received",
            "submission received",
            "thank you for applying",
            "application confirmation",
        ),
        False,
    ),
)


class GmailMonitorError(RuntimeError):
    pass


def classify_subject(subject: str) -> tuple[str, bool]:
    normalized = " ".join(subject.casefold().split())
    for category, terms, actionable in CATEGORY_TERMS:
        if any(term in normalized for term in terms):
            return category, actionable
    return "update", False


def header_value(message: dict[str, Any], name: str) -> str:
    headers = message.get("payload", {}).get("headers", [])
    for header in headers:
        if str(header.get("name", "")).casefold() == name.casefold():
            return " ".join(str(header.get("value", "")).split())[:1000]
    return ""


def secure_write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    os.chmod(path.parent, 0o700)
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
        handle.write(content)
    os.chmod(path, 0o600)


def expected_profile_email() -> str:
    with SessionLocal() as db:
        field = db.scalar(select(ProfileField).where(ProfileField.field_key == "contact.email"))
        if field is None or not field.value_json or field.status == "unknown":
            raise GmailMonitorError("Add and review the scholarship email in the local profile first")
        return str(field.value_json).strip().casefold()


def gmail_service(*, interactive: bool) -> Any:
    client_path = settings.gmail_client_secret_path.resolve()
    token_path = settings.gmail_token_path.resolve()
    if not client_path.is_file():
        raise GmailMonitorError(f"Gmail OAuth client file is missing at {client_path}")

    credentials: Credentials | None = None
    if token_path.is_file():
        credentials = Credentials.from_authorized_user_file(str(token_path), SCOPES)
    if credentials and credentials.expired and credentials.refresh_token:
        credentials.refresh(Request())
        secure_write(token_path, credentials.to_json())
    if not credentials or not credentials.valid:
        if not interactive:
            raise GmailMonitorError("Gmail is not authorized; run npm run gmail:connect first")
        flow = InstalledAppFlow.from_client_secrets_file(str(client_path), SCOPES)
        credentials = flow.run_local_server(
            port=0,
            authorization_prompt_message="Authorize the scholarship Gmail account here: {url}",
            success_message="Gmail authorization completed. You may close this tab.",
        )

    service = build("gmail", "v1", credentials=credentials, cache_discovery=False)
    authorized_email = str(service.users().getProfile(userId="me").execute()["emailAddress"])
    if authorized_email.casefold() != expected_profile_email():
        raise GmailMonitorError(
            "The authorized Google account does not match the scholarship email stored in the profile"
        )
    if interactive or not token_path.is_file():
        secure_write(token_path, credentials.to_json())
    return service


def iter_message_ids(service: Any, limit: int) -> list[dict[str, str]]:
    messages: list[dict[str, str]] = []
    page_token: str | None = None
    while len(messages) < limit:
        response = (
            service.users()
            .messages()
            .list(
                userId="me",
                labelIds=["INBOX"],
                maxResults=min(100, limit - len(messages)),
                pageToken=page_token,
            )
            .execute()
        )
        messages.extend(response.get("messages", []))
        page_token = response.get("nextPageToken")
        if not page_token:
            break
    return messages[:limit]


def sync_messages(service: Any, limit: int = 250) -> dict[str, int]:
    now = datetime.now(UTC)
    references = iter_message_ids(service, limit)
    created = 0
    updated = 0
    actionable = 0
    with SessionLocal() as db:
        for reference in references:
            raw = (
                service.users()
                .messages()
                .get(
                    userId="me",
                    id=reference["id"],
                    format="metadata",
                    metadataHeaders=["From", "Subject"],
                )
                .execute()
            )
            subject = header_value(raw, "Subject") or "(no subject)"
            sender = header_value(raw, "From") or "(sender unavailable)"
            category, is_actionable = classify_subject(subject)
            received_at = datetime.fromtimestamp(int(raw.get("internalDate", "0")) / 1000, UTC)
            item = db.get(EmailMessage, raw["id"])
            if item is None:
                item = EmailMessage(provider_message_id=raw["id"], first_seen_at=now)
                db.add(item)
                created += 1
            else:
                updated += 1
            item.thread_id = raw.get("threadId")
            item.sender = sender[:500]
            item.subject = subject[:1000]
            item.received_at = received_at
            item.category = category
            item.is_unread = "UNREAD" in raw.get("labelIds", [])
            item.is_actionable = is_actionable
            item.last_seen_at = now
            actionable += int(is_actionable)

        system = get_or_create_settings(db)
        system.email_monitoring_enabled = True
        record_event(
            db,
            "email.synced",
            f"Gmail metadata sync indexed {len(references)} messages; {actionable} need attention",
        )
        db.commit()
    return {
        "scanned": len(references),
        "created": created,
        "updated": updated,
        "actionable": actionable,
    }


def status() -> dict[str, Any]:
    with SessionLocal() as db:
        system = get_or_create_settings(db)
        indexed = db.scalar(select(func.count()).select_from(EmailMessage)) or 0
        actionable = db.scalar(
            select(func.count()).select_from(EmailMessage).where(EmailMessage.is_actionable.is_(True))
        ) or 0
        last_sync = db.scalar(select(func.max(EmailMessage.last_seen_at)))
        db.commit()
        monitoring_enabled = system.email_monitoring_enabled
    return {
        "provider": "Gmail",
        "client_credentials_present": settings.gmail_client_secret_path.resolve().is_file(),
        "authorization_token_present": settings.gmail_token_path.resolve().is_file(),
        "monitoring_enabled": monitoring_enabled,
        "scope": GMAIL_METADATA_SCOPE,
        "messages_indexed": indexed,
        "actionable_messages": actionable,
        "last_sync_at": last_sync.isoformat() if last_sync else None,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Local metadata-only Gmail monitor")
    parser.add_argument("command", choices=("connect", "sync", "status"))
    parser.add_argument("--limit", type=int, default=250)
    args = parser.parse_args()
    if args.limit < 1 or args.limit > 1000:
        parser.error("--limit must be between 1 and 1000")
    if args.command == "status":
        print(status())
        return
    service = gmail_service(interactive=args.command == "connect")
    if args.command == "connect":
        print("Gmail metadata-only authorization verified and stored locally.")
        return
    print(sync_messages(service, args.limit))


if __name__ == "__main__":
    main()
