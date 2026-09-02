import hashlib
import json
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from typing import Any

from app.core.safety import truthy_requirement_keys


MANUAL_BARRIERS = {
    "captcha": "CAPTCHA requires manual completion",
    "two_factor_authentication": "Two-factor authentication requires manual completion",
    "essay": "Essay or narrative content requires user review",
    "recommendation": "Recommendation handling requires user review",
    "signature": "A signature requires explicit user action",
    "attestation": "An attestation requires explicit user review",
    "file_upload": "A document upload requires deterministic document selection",
}

DOCUMENT_REQUIREMENTS = {
    "resume": "resume",
    "cv": "cv",
    "transcript": "transcript",
    "official_transcript": "official_transcript",
    "unofficial_transcript": "unofficial_transcript",
    "proof_of_enrollment": "enrollment_verification",
    "enrollment_verification": "enrollment_verification",
    "proof_of_residency": "proof_of_residency",
    "fafsa": "fafsa",
    "portfolio": "portfolio",
}


@dataclass(frozen=True)
class ValidationCheck:
    code: str
    status: str
    message: str


def passed(code: str, message: str) -> ValidationCheck:
    return ValidationCheck(code=code, status="passed", message=message)


def blocked(code: str, message: str) -> ValidationCheck:
    return ValidationCheck(code=code, status="blocked", message=message)


def barrier_checks(barriers: list[str]) -> list[ValidationCheck]:
    if not barriers:
        return [passed("manual_barriers", "No manual browser checkpoint was detected")]
    return [
        blocked(f"barrier_{barrier}", MANUAL_BARRIERS.get(barrier, "An unknown manual checkpoint remains"))
        for barrier in sorted(set(barriers))
    ]


def deadline_check(
    deadline: datetime | None,
    deadline_type: str,
    *,
    now: datetime | None = None,
) -> ValidationCheck:
    current = now or datetime.now(UTC)
    if deadline is not None and deadline.tzinfo is None:
        deadline = deadline.replace(tzinfo=UTC)
    if deadline is not None and deadline <= current:
        return blocked("deadline_expired", "The recorded scholarship deadline has passed")
    if deadline_type == "fixed" and deadline is None:
        return blocked("deadline_missing", "A fixed deadline has not been normalized")
    if deadline_type == "unknown":
        return blocked("deadline_ambiguous", "The scholarship deadline type is still unknown")
    return passed("deadline", "The normalized deadline permits continued preparation")


def required_document_types(requirements: Any) -> list[str]:
    keys = truthy_requirement_keys(requirements)
    return sorted({DOCUMENT_REQUIREMENTS[key] for key in DOCUMENT_REQUIREMENTS.keys() & keys})


def canonical_manifest_hash(payload: dict[str, Any]) -> str:
    encoded = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def check_dicts(checks: list[ValidationCheck]) -> list[dict[str, str]]:
    return [asdict(check) for check in checks]
