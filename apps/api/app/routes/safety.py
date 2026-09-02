from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.safety import persist_safety_assessment
from app.db import get_db
from app.models import DomainPolicy, SafetyAssessment, Scholarship
from app.routes.applications import safety_read
from app.schemas import DomainPolicyRead, DomainPolicyWrite, SafetyAssessmentRead
from app.services import record_event

router = APIRouter(prefix="/api/safety", tags=["safety"])


def policy_read(policy: DomainPolicy) -> DomainPolicyRead:
    return DomainPolicyRead(
        id=policy.id,
        domain=policy.domain,
        decision=policy.decision,
        notes=policy.notes,
        created_at=policy.created_at,
        updated_at=policy.updated_at,
    )


@router.get("/domains", response_model=list[DomainPolicyRead])
def list_domain_policies(db: Session = Depends(get_db)) -> list[DomainPolicyRead]:
    policies = list(db.scalars(select(DomainPolicy).order_by(DomainPolicy.domain)))
    return [policy_read(policy) for policy in policies]


@router.put("/domains", response_model=DomainPolicyRead)
def set_domain_policy(
    payload: DomainPolicyWrite, db: Session = Depends(get_db)
) -> DomainPolicyRead:
    policy = db.scalar(select(DomainPolicy).where(DomainPolicy.domain == payload.domain))
    if policy is None:
        policy = DomainPolicy(
            domain=payload.domain,
            decision=payload.decision,
            notes=payload.notes,
        )
        db.add(policy)
    else:
        policy.decision = payload.decision
        policy.notes = payload.notes
    record_event(
        db,
        "safety.domain_policy_updated",
        f"Domain {payload.domain} was marked {payload.decision}",
        "warning" if payload.decision == "blocked" else "info",
    )
    db.commit()
    db.refresh(policy)
    return policy_read(policy)


@router.post("/scholarships/{scholarship_id}/assess", response_model=SafetyAssessmentRead)
def assess_scholarship(
    scholarship_id: str, db: Session = Depends(get_db)
) -> SafetyAssessmentRead:
    scholarship = db.get(Scholarship, scholarship_id)
    if scholarship is None:
        raise HTTPException(status_code=404, detail="Scholarship not found")
    assessment = persist_safety_assessment(db, scholarship)
    record_event(db, "safety.assessed", f"Assessed {scholarship.canonical_name}")
    db.commit()
    return safety_read(assessment)


@router.get("/scholarships/{scholarship_id}", response_model=SafetyAssessmentRead | None)
def current_scholarship_assessment(
    scholarship_id: str, db: Session = Depends(get_db)
) -> SafetyAssessmentRead | None:
    if db.get(Scholarship, scholarship_id) is None:
        raise HTTPException(status_code=404, detail="Scholarship not found")
    assessment = db.scalar(
        select(SafetyAssessment)
        .where(
            SafetyAssessment.scholarship_id == scholarship_id,
            SafetyAssessment.application_id.is_(None),
            SafetyAssessment.is_current.is_(True),
        )
        .order_by(SafetyAssessment.assessed_at.desc())
    )
    return safety_read(assessment)

