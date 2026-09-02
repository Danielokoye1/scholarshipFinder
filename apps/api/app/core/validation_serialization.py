from app.models import ValidationSnapshot
from app.schemas import ValidationSnapshotRead


def validation_snapshot_read(snapshot: ValidationSnapshot) -> ValidationSnapshotRead:
    return ValidationSnapshotRead(
        id=snapshot.id,
        application_id=snapshot.application_id,
        browser_run_id=snapshot.browser_run_id,
        dry_run_fill_id=snapshot.dry_run_fill_id,
        safety_assessment_id=snapshot.safety_assessment_id,
        status=snapshot.status,
        operating_mode=snapshot.operating_mode,
        source_page_hash=snapshot.source_page_hash,
        fill_manifest_hash=snapshot.fill_manifest_hash,
        validation_manifest_hash=snapshot.validation_manifest_hash,
        eligibility_run_id=snapshot.eligibility_run_id,
        checks=snapshot.checks_json,
        blockers=snapshot.blockers_json,
        profile_manifest=snapshot.profile_manifest_json,
        document_manifest=snapshot.document_manifest_json,
        created_at=snapshot.created_at,
    )
