from datetime import UTC, datetime
from urllib.parse import urlsplit

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.core.deduplication import find_duplicate
from app.core.eligibility import evaluate_scholarship
from app.core.legitimacy import assess_legitimacy
from app.core.normalization import (
    canonicalize_url,
    clean_text,
    content_hash,
    normalized_label,
    scholarship_fingerprint,
)
from app.core.priority import refresh_priority
from app.core.safety import persist_safety_assessment
from app.db import get_db
from app.config import settings
from app.models import (
    EligibilityCheck,
    EligibilityRule,
    Scholarship,
    ScholarshipSource,
    SourceEvidence,
)
from app.schemas import (
    EligibilityCheckRead,
    EligibilityRuleRead,
    EligibilityStatus,
    EvaluationBatchResult,
    IngestResult,
    ScholarshipDetail,
    ScholarshipIngest,
    ScholarshipList,
    ScholarshipSummary,
    LegitimacyStatus,
)
from app.services import record_event

router = APIRouter(prefix="/api/scholarships", tags=["scholarships"])


def source_is_trusted(source_url: str) -> bool:
    hostname = urlsplit(source_url).hostname or ""
    trusted_domains = {
        domain.strip().casefold().removeprefix("www.")
        for domain in settings.trusted_source_domains.split(",")
        if domain.strip()
    }
    return any(hostname == domain or hostname.endswith(f".{domain}") for domain in trusted_domains)


def timezone_offset(value: datetime | None) -> str | None:
    if value is None:
        return None
    offset = value.strftime("%z")
    return f"{offset[:3]}:{offset[3:]}" if offset else None


def normalize_urls(payload: ScholarshipIngest) -> tuple[str, str | None]:
    try:
        source_url = canonicalize_url(payload.source_url)
        application_url = canonicalize_url(payload.application_url) if payload.application_url else None
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    return source_url, application_url


def summary(item: Scholarship) -> ScholarshipSummary:
    return ScholarshipSummary(
        id=item.id,
        canonical_name=item.canonical_name,
        provider=item.provider,
        source_url=item.source_url,
        application_url=item.application_url,
        award_min_cents=item.award_min_cents,
        award_max_cents=item.award_max_cents,
        deadline=item.deadline,
        deadline_timezone=item.deadline_timezone,
        deadline_type=item.deadline_type,
        legitimacy_status=item.legitimacy_status,
        legitimacy_score=item.legitimacy_score,
        eligibility_status=item.eligibility_status,
        eligibility_score=item.eligibility_score,
        safety_status=item.safety_status,
        priority_score=item.priority_score,
        automation_level=item.automation_level,
        last_verified_at=item.last_verified_at,
        created_at=item.created_at,
    )


def check_read(
    check: EligibilityCheck, rules_by_id: dict[str, EligibilityRule]
) -> EligibilityCheckRead | None:
    rule = rules_by_id.get(check.rule_id)
    if rule is None:
        return None
    return EligibilityCheckRead(
        id=check.id,
        rule_id=check.rule_id,
        requirement=rule.requirement_text,
        field_key=rule.field_key,
        profile_value=check.profile_value_json,
        result=check.result,
        evidence=check.evidence,
        confidence=check.confidence,
        evaluation_run_id=check.evaluation_run_id,
        is_current=check.is_current,
        evaluated_at=check.evaluated_at,
    )


def add_source_evidence(
    db: Session,
    scholarship: Scholarship,
    source_url: str,
    raw_text: str,
    evidence_type: str,
) -> SourceEvidence:
    digest = content_hash(raw_text)
    existing = db.scalar(
        select(SourceEvidence).where(
            SourceEvidence.scholarship_id == scholarship.id,
            SourceEvidence.content_hash == digest,
            SourceEvidence.evidence_type == evidence_type,
        )
    )
    if existing:
        return existing
    evidence = SourceEvidence(
        scholarship_id=scholarship.id,
        source_url=source_url,
        evidence_type=evidence_type,
        raw_text=raw_text,
        content_hash=digest,
    )
    db.add(evidence)
    db.flush()
    return evidence


def attach_source(
    db: Session,
    scholarship: Scholarship,
    source_url: str,
    adapter: str,
    source_text: str,
) -> None:
    now = datetime.now(UTC)
    digest = content_hash(source_text)
    existing = db.scalar(select(ScholarshipSource).where(ScholarshipSource.source_url == source_url))
    if existing:
        if existing.content_hash != digest:
            existing.last_changed_at = now
        existing.content_hash = digest
        existing.last_crawled_at = now
        return
    db.add(
        ScholarshipSource(
            scholarship_id=scholarship.id,
            source_url=source_url,
            adapter=adapter,
            content_hash=digest,
            last_crawled_at=now,
            last_changed_at=now,
        )
    )


@router.post("/ingest", response_model=IngestResult, status_code=status.HTTP_201_CREATED)
def ingest_scholarship(
    payload: ScholarshipIngest, response: Response, db: Session = Depends(get_db)
) -> IngestResult:
    source_url, application_url = normalize_urls(payload)
    name = clean_text(payload.name)
    provider = clean_text(payload.provider) if payload.provider else None
    normalized_deadline = payload.deadline.astimezone(UTC) if payload.deadline else None
    fingerprint = scholarship_fingerprint(
        name, provider, normalized_deadline, payload.award_max_cents
    )
    normalized_source = clean_text(payload.source_text).casefold()
    for rule in payload.rules:
        if clean_text(rule.source_quote).casefold() not in normalized_source:
            raise HTTPException(
                status_code=422,
                detail=f"The source quote for requirement '{rule.requirement}' was not found in source_text",
            )
    duplicate = find_duplicate(
        db,
        source_url=source_url,
        application_url=application_url,
        fingerprint=fingerprint,
        name=name,
        provider=provider,
        deadline=normalized_deadline,
        award_max_cents=payload.award_max_cents,
    )
    if duplicate:
        response.status_code = status.HTTP_200_OK
        attach_source(db, duplicate.scholarship, source_url, payload.source_adapter, payload.source_text)
        add_source_evidence(
            db, duplicate.scholarship, source_url, payload.source_text, "discovery_source"
        )
        duplicate.scholarship.last_verified_at = datetime.now(UTC)
        persist_safety_assessment(db, duplicate.scholarship)
        refresh_priority(db, duplicate.scholarship)
        record_event(
            db,
            "scholarship.duplicate_detected",
            f"Duplicate source linked to {duplicate.scholarship.canonical_name}",
        )
        db.commit()
        return IngestResult(
            scholarship_id=duplicate.scholarship.id,
            created=False,
            duplicate_reason=duplicate.reason,
            duplicate_confidence=duplicate.confidence,
            legitimacy_status=duplicate.scholarship.legitimacy_status,
            eligibility_status=duplicate.scholarship.eligibility_status,
        )

    legitimacy = assess_legitimacy(
        source_url,
        " ".join(filter(None, [name, provider, payload.description, payload.source_text])),
        source_is_trusted(source_url),
    )
    scholarship = Scholarship(
        canonical_name=name,
        normalized_name=normalized_label(name) or "",
        provider=provider,
        normalized_provider=normalized_label(provider),
        source_url=source_url,
        application_url=application_url,
        description=clean_text(payload.description) if payload.description else None,
        award_min_cents=payload.award_min_cents,
        award_max_cents=payload.award_max_cents,
        award_description=clean_text(payload.award_description) if payload.award_description else None,
        raw_deadline_text=clean_text(payload.raw_deadline_text) if payload.raw_deadline_text else None,
        deadline=normalized_deadline,
        deadline_timezone=timezone_offset(payload.deadline),
        deadline_type=payload.deadline_type,
        requirements_json=payload.requirements,
        fingerprint=fingerprint,
        legitimacy_status=legitimacy.status,
        legitimacy_score=legitimacy.score,
        legitimacy_signals_json=legitimacy.signals,
        eligibility_status="needs_information",
        eligibility_score=0.0,
        automation_level=0,
        last_verified_at=datetime.now(UTC),
    )
    db.add(scholarship)
    db.flush()
    attach_source(db, scholarship, source_url, payload.source_adapter, payload.source_text)
    add_source_evidence(db, scholarship, source_url, payload.source_text, "discovery_source")

    for rule_payload in payload.rules:
        quote = add_source_evidence(
            db, scholarship, source_url, rule_payload.source_quote, "eligibility_quote"
        )
        db.add(
            EligibilityRule(
                scholarship_id=scholarship.id,
                evidence_id=quote.id,
                requirement_text=clean_text(rule_payload.requirement),
                field_key=rule_payload.field_key,
                operator=rule_payload.operator,
                expected_value_json=rule_payload.expected_value,
                confidence=rule_payload.confidence,
                needs_review=rule_payload.needs_review,
            )
        )
    db.flush()
    evaluate_scholarship(db, scholarship)
    persist_safety_assessment(db, scholarship)
    refresh_priority(db, scholarship)
    record_event(db, "scholarship.ingested", f"Added {scholarship.canonical_name}")
    db.commit()
    return IngestResult(
        scholarship_id=scholarship.id,
        created=True,
        legitimacy_status=scholarship.legitimacy_status,
        eligibility_status=scholarship.eligibility_status,
    )


@router.get("", response_model=ScholarshipList)
def list_scholarships(
    q: str | None = Query(default=None, max_length=200),
    eligibility_status: EligibilityStatus | None = Query(default=None),
    legitimacy_status: LegitimacyStatus | None = Query(default=None),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
) -> ScholarshipList:
    filters = []
    if q:
        term = f"%{normalized_label(q)}%"
        filters.append(
            or_(Scholarship.normalized_name.like(term), Scholarship.normalized_provider.like(term))
        )
    if eligibility_status:
        filters.append(Scholarship.eligibility_status == eligibility_status)
    if legitimacy_status:
        filters.append(Scholarship.legitimacy_status == legitimacy_status)
    total = db.scalar(select(func.count()).select_from(Scholarship).where(*filters)) or 0
    items = list(
        db.scalars(
            select(Scholarship)
            .where(*filters)
            .order_by(
                Scholarship.deadline.is_(None),
                Scholarship.deadline.asc(),
                Scholarship.created_at.desc(),
            )
            .offset(offset)
            .limit(limit)
        )
    )
    return ScholarshipList(
        items=[summary(item) for item in items], total=total, offset=offset, limit=limit
    )


@router.post("/evaluate-all", response_model=EvaluationBatchResult)
def reevaluate_all(
    limit: int = Query(default=500, ge=1, le=2000), db: Session = Depends(get_db)
) -> EvaluationBatchResult:
    scholarships = list(
        db.scalars(select(Scholarship).order_by(Scholarship.created_at).limit(limit))
    )
    counts = {"eligible": 0, "ineligible": 0, "needs_information": 0}
    for scholarship in scholarships:
        evaluate_scholarship(db, scholarship)
        persist_safety_assessment(db, scholarship)
        refresh_priority(db, scholarship)
        counts[scholarship.eligibility_status] += 1
    record_event(db, "eligibility.batch_evaluated", f"Evaluated {len(scholarships)} scholarships")
    db.commit()
    return EvaluationBatchResult(evaluated=len(scholarships), **counts)


@router.get("/{scholarship_id}", response_model=ScholarshipDetail)
def scholarship_detail(scholarship_id: str, db: Session = Depends(get_db)) -> ScholarshipDetail:
    scholarship = db.get(Scholarship, scholarship_id)
    if scholarship is None:
        raise HTTPException(status_code=404, detail="Scholarship not found")
    rules = list(
        db.scalars(
            select(EligibilityRule)
            .where(EligibilityRule.scholarship_id == scholarship_id)
            .order_by(EligibilityRule.created_at, EligibilityRule.id)
        )
    )
    checks = list(
        db.scalars(
            select(EligibilityCheck)
            .where(
                EligibilityCheck.scholarship_id == scholarship_id,
                EligibilityCheck.is_current.is_(True),
            )
            .order_by(EligibilityCheck.evaluated_at, EligibilityCheck.id)
        )
    )
    evidence_by_id = {
        item.id: item
        for item in db.scalars(
            select(SourceEvidence).where(SourceEvidence.scholarship_id == scholarship_id)
        )
    }
    rules_by_id = {rule.id: rule for rule in rules}
    base = summary(scholarship).model_dump()
    return ScholarshipDetail(
        **base,
        description=scholarship.description,
        award_description=scholarship.award_description,
        raw_deadline_text=scholarship.raw_deadline_text,
        requirements=scholarship.requirements_json,
        legitimacy_signals=scholarship.legitimacy_signals_json,
        rules=[
            EligibilityRuleRead(
                id=rule.id,
                requirement=rule.requirement_text,
                field_key=rule.field_key,
                operator=rule.operator,
                expected_value=rule.expected_value_json,
                confidence=rule.confidence,
                needs_review=rule.needs_review,
                source_quote=evidence_by_id[rule.evidence_id].raw_text
                if rule.evidence_id in evidence_by_id
                else None,
            )
            for rule in rules
        ],
        checks=[item for check in checks if (item := check_read(check, rules_by_id)) is not None],
    )


@router.get("/{scholarship_id}/eligibility-history", response_model=list[EligibilityCheckRead])
def eligibility_history(
    scholarship_id: str, db: Session = Depends(get_db)
) -> list[EligibilityCheckRead]:
    if db.get(Scholarship, scholarship_id) is None:
        raise HTTPException(status_code=404, detail="Scholarship not found")
    rules = {
        rule.id: rule
        for rule in db.scalars(
            select(EligibilityRule).where(EligibilityRule.scholarship_id == scholarship_id)
        )
    }
    checks = list(
        db.scalars(
            select(EligibilityCheck)
            .where(EligibilityCheck.scholarship_id == scholarship_id)
            .order_by(EligibilityCheck.evaluated_at.desc(), EligibilityCheck.id)
        )
    )
    return [item for check in checks if (item := check_read(check, rules)) is not None]


@router.post("/{scholarship_id}/evaluate", response_model=ScholarshipDetail)
def reevaluate_scholarship(
    scholarship_id: str, db: Session = Depends(get_db)
) -> ScholarshipDetail:
    scholarship = db.get(Scholarship, scholarship_id)
    if scholarship is None:
        raise HTTPException(status_code=404, detail="Scholarship not found")
    evaluate_scholarship(db, scholarship)
    persist_safety_assessment(db, scholarship)
    refresh_priority(db, scholarship)
    record_event(db, "eligibility.evaluated", f"Evaluated {scholarship.canonical_name}")
    db.commit()
    return scholarship_detail(scholarship_id, db)
