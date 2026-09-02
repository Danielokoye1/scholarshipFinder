from dataclasses import dataclass
import re
from urllib.parse import urlsplit

from app.core.normalization import clean_text


@dataclass(frozen=True)
class LegitimacyAssessment:
    status: str
    score: float
    signals: list[str]


BLOCKING_PATTERNS = {
    r"\b(?:pay|submit|require(?:d|s)?|charg(?:e|ed)|nonrefundable)\b.{0,40}\bapplication fee\b": "Application fee required",
    r"\b(?:pay|submit|require(?:d|s)?|charg(?:e|ed)|nonrefundable)\b.{0,40}\bprocessing fee\b": "Processing fee required",
    r"\b(?:send|buy|purchase)\b.{0,30}\bgift card\b": "Gift card payment requested",
    r"\bpay\b.{0,30}\b(?:crypto|cryptocurrency|bitcoin)\b": "Cryptocurrency payment requested",
    r"\b(?:provide|enter|share|send)\b.{0,30}\bbank login\b": "Banking credentials requested",
}
REVIEW_PHRASES = {
    "social security number": "Social Security number requested",
    "ssn": "SSN requested",
    "bank account": "Bank account information requested",
    "guaranteed winner": "Guaranteed award language detected",
}


def assess_legitimacy(source_url: str, text: str, trusted_source: bool = False) -> LegitimacyAssessment:
    normalized = clean_text(text).casefold()
    signals: list[str] = []
    blocked = [message for pattern, message in BLOCKING_PATTERNS.items() if re.search(pattern, normalized)]
    review = [message for phrase, message in REVIEW_PHRASES.items() if phrase in normalized]
    signals.extend(blocked)
    signals.extend(review)

    parsed = urlsplit(source_url)
    if parsed.scheme != "https":
        review.append("Source does not use HTTPS")
        signals.append("Source does not use HTTPS")

    if blocked:
        return LegitimacyAssessment("blocked", 0.0, signals)
    if review:
        return LegitimacyAssessment("review_required", 0.35, signals)
    if trusted_source:
        return LegitimacyAssessment("verified", 1.0, ["Source explicitly marked as trusted"])
    return LegitimacyAssessment(
        "likely_legitimate",
        0.75,
        ["No deterministic scam signals detected; provider is not independently verified"],
    )
