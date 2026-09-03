import ipaddress
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any
from urllib.parse import urlsplit

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.models import DomainPolicy, SafetyAssessment, Scholarship


@dataclass(frozen=True)
class SafetyDecision:
    status: str
    score: float
    domain: str | None
    reasons: list[str]
    policy: DomainPolicy | None


BLOCKED_REQUIREMENT_KEYS = {
    "application_fee",
    "bank_credentials",
    "bank_login",
    "crypto_payment",
    "gift_card",
    "payment_required",
}
REVIEW_REQUIREMENT_KEYS = {
    "attestation",
    "bank_account",
    "background_check",
    "employment_commitment",
    "financial_information",
    "government_id",
    "household_income",
    "passport",
    "security_clearance",
    "service_commitment",
    "signature",
    "social_security_number",
    "ssn",
}


def truthy_requirement_keys(value: Any, prefix: str = "") -> set[str]:
    found: set[str] = set()
    if isinstance(value, dict):
        for key, item in value.items():
            normalized = str(key).strip().casefold().replace("-", "_").replace(" ", "_")
            full_key = f"{prefix}.{normalized}" if prefix else normalized
            if item is not False and item is not None and item != "" and item != 0:
                found.add(normalized)
                found.add(full_key)
            found.update(truthy_requirement_keys(item, full_key))
    elif isinstance(value, list):
        for item in value:
            found.update(truthy_requirement_keys(item, prefix))
            if isinstance(item, str):
                found.add(item.strip().casefold().replace("-", "_").replace(" ", "_"))
    return found


def application_domain(scholarship: Scholarship) -> str | None:
    target = scholarship.application_url
    if not target:
        return None
    return (urlsplit(target).hostname or "").casefold().removeprefix("www.") or None


def assess_application_safety(db: Session, scholarship: Scholarship) -> SafetyDecision:
    target = scholarship.application_url or ""
    parsed = urlsplit(target)
    domain = application_domain(scholarship)
    reasons: list[str] = []
    blocking: list[str] = []
    review: list[str] = []

    if not scholarship.application_url:
        review.append("No distinct application URL has been verified")
    elif parsed.scheme != "https":
        blocking.append("The application endpoint does not use HTTPS")
    if scholarship.application_url and not domain:
        blocking.append("The application endpoint has no valid domain")
    elif domain and (domain.startswith("xn--") or ".xn--" in domain):
        review.append("The application domain uses internationalized punycode and needs review")
    else:
        try:
            ipaddress.ip_address(domain)
        except ValueError:
            pass
        else:
            blocking.append("Direct IP-address application endpoints are not allowed")
    if scholarship.application_url and parsed.port and parsed.port not in {80, 443}:
        review.append("The application endpoint uses a non-standard network port")

    if scholarship.legitimacy_status == "blocked":
        blocking.append("Scholarship legitimacy screening is blocked")
    elif scholarship.legitimacy_status == "review_required":
        review.append("Scholarship legitimacy screening requires review")

    requirement_keys = truthy_requirement_keys(scholarship.requirements_json)
    for key in sorted(BLOCKED_REQUIREMENT_KEYS & requirement_keys):
        blocking.append(f"Blocked sensitive requirement detected: {key}")
    for key in sorted(REVIEW_REQUIREMENT_KEYS & requirement_keys):
        review.append(f"Sensitive requirement needs individual review: {key}")

    policy = db.scalar(select(DomainPolicy).where(DomainPolicy.domain == domain)) if domain else None
    if policy and policy.decision == "blocked":
        blocking.append("The application domain is on your local blocklist")
    elif not policy:
        review.append("The application domain has not been manually approved")

    reasons.extend(blocking)
    reasons.extend(review)
    if blocking:
        return SafetyDecision("blocked", 0.0, domain, reasons, policy)
    if review:
        return SafetyDecision("review_required", 0.45, domain, reasons, policy)
    if policy and policy.decision == "approved":
        return SafetyDecision(
            "approved",
            0.95,
            domain,
            ["HTTPS checks passed", "Application domain is manually approved"],
            policy,
        )
    return SafetyDecision("review_required", 0.45, domain, reasons, policy)


def persist_safety_assessment(
    db: Session, scholarship: Scholarship, application_id: str | None = None
) -> SafetyAssessment:
    decision = assess_application_safety(db, scholarship)
    db.execute(
        update(SafetyAssessment)
        .where(
            SafetyAssessment.scholarship_id == scholarship.id,
            SafetyAssessment.application_id == application_id,
            SafetyAssessment.is_current.is_(True),
        )
        .values(is_current=False)
    )
    assessment = SafetyAssessment(
        id=str(uuid.uuid4()),
        scholarship_id=scholarship.id,
        application_id=application_id,
        policy_id=decision.policy.id if decision.policy else None,
        application_domain=decision.domain,
        status=decision.status,
        score=decision.score,
        reasons_json=decision.reasons,
        is_current=True,
        assessed_at=datetime.now(UTC),
    )
    scholarship.safety_status = decision.status
    db.add(assessment)
    return assessment
