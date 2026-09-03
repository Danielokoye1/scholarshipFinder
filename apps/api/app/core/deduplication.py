from dataclasses import dataclass

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.config import settings
from app.core.normalization import normalized_label, token_similarity
from app.models import Scholarship


@dataclass(frozen=True)
class DuplicateMatch:
    scholarship: Scholarship
    reason: str
    confidence: float


def find_duplicate(
    db: Session,
    *,
    source_url: str,
    application_url: str | None,
    fingerprint: str,
    name: str,
    provider: str | None,
    deadline,
    award_max_cents: int | None,
) -> DuplicateMatch | None:
    # A single provider portal can host many distinct awards. Treating its shared
    # start URL as a globally unique scholarship identifier collapses an entire
    # catalog into one record. Exact source identity and the scholarship
    # fingerprint remain safe deterministic duplicate keys; provider/title
    # similarity below handles routed application links conservatively.
    exact_conditions = [Scholarship.source_url == source_url, Scholarship.fingerprint == fingerprint]
    exact = db.scalar(select(Scholarship).where(or_(*exact_conditions)).limit(1))
    if exact:
        reason = "canonical_url" if exact.source_url == source_url else "identity_fingerprint"
        return DuplicateMatch(exact, reason, 1.0)

    normalized_provider = normalized_label(provider)
    if not normalized_provider:
        return None
    candidates = list(
        db.scalars(
            select(Scholarship)
            .where(Scholarship.normalized_provider == normalized_provider)
            .order_by(Scholarship.created_at.desc())
            .limit(100)
        )
    )
    for candidate in candidates:
        same_deadline = (
            candidate.deadline.date() == deadline.date()
            if candidate.deadline is not None and deadline is not None
            else candidate.deadline is None or deadline is None
        )
        same_award = (
            candidate.award_max_cents == award_max_cents
            or candidate.award_max_cents is None
            or award_max_cents is None
        )
        similarity = token_similarity(candidate.canonical_name, name)
        if same_deadline and same_award and similarity >= settings.duplicate_title_similarity_threshold:
            return DuplicateMatch(candidate, "provider_and_title_similarity", similarity)
    return None
