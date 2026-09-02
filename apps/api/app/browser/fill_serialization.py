from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import DryRunFill, FillFieldEvidence
from app.schemas import DryRunFillRead, FillFieldEvidenceRead


def dry_run_fill_read(db: Session, run: DryRunFill) -> DryRunFillRead:
    fields = list(
        db.scalars(
            select(FillFieldEvidence)
            .where(FillFieldEvidence.fill_run_id == run.id)
            .order_by(FillFieldEvidence.ordinal, FillFieldEvidence.id)
        )
    )
    return DryRunFillRead(
        id=run.id,
        application_id=run.application_id,
        browser_run_id=run.browser_run_id,
        status=run.status,
        execution_scope=run.execution_scope,
        source_page_hash=run.source_page_hash,
        manifest_hash=run.manifest_hash,
        field_count=run.field_count,
        filled_field_count=run.filled_field_count,
        skipped_field_count=run.skipped_field_count,
        errors=run.errors_json,
        started_at=run.started_at,
        finished_at=run.finished_at,
        fields=[
            FillFieldEvidenceRead(
                id=item.id,
                ordinal=item.ordinal,
                label=item.label,
                profile_field_key=item.profile_field_key,
                profile_status=item.profile_status,
                source_reference=item.source_reference,
                profile_updated_at=item.profile_updated_at,
                value_type=item.value_type,
                value_hash=item.value_hash,
                result=item.result,
                reason=item.reason,
            )
            for item in fields
        ],
    )
