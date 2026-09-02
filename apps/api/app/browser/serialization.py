from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import BrowserRun, FormFieldPlan
from app.schemas import BrowserRunRead, FormFieldPlanRead


def browser_run_read(db: Session, run: BrowserRun) -> BrowserRunRead:
    fields = list(
        db.scalars(
            select(FormFieldPlan)
            .where(FormFieldPlan.browser_run_id == run.id)
            .order_by(FormFieldPlan.ordinal)
        )
    )
    return BrowserRunRead(
        id=run.id,
        application_id=run.application_id,
        status=run.status,
        adapter=run.adapter,
        start_url=run.start_url,
        final_url=run.final_url,
        initial_domain=run.initial_domain,
        final_domain=run.final_domain,
        redirect_chain=run.redirect_chain_json,
        page_title=run.page_title,
        response_status=run.response_status,
        page_content_hash=run.page_content_hash,
        field_count=run.field_count,
        required_field_count=run.required_field_count,
        automatable_field_count=run.automatable_field_count,
        automatable_percent=run.automatable_percent,
        detected_barriers=run.detected_barriers_json,
        blocked_requests=run.blocked_requests_json,
        error_category=run.error_category,
        error_message=run.error_message,
        started_at=run.started_at,
        finished_at=run.finished_at,
        fields=[
            FormFieldPlanRead(
                id=field.id,
                ordinal=field.ordinal,
                form_index=field.form_index,
                tag_name=field.tag_name,
                input_type=field.input_type,
                label=field.label,
                required=field.required,
                disabled=field.disabled,
                autocomplete=field.autocomplete,
                profile_field_key=field.profile_field_key,
                mapping_confidence=field.mapping_confidence,
                profile_status=field.profile_status,
                disposition=field.disposition,
                reason=field.reason,
            )
            for field in fields
        ],
    )
