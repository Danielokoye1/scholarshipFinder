import hashlib
import html
import json
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from playwright.sync_api import Error as PlaywrightError
from playwright.sync_api import sync_playwright

from app.config import settings
from app.models import FormFieldPlan, ProfileField


SUPPORTED_INPUT_TYPES = {"text", "email", "tel", "number", "date", "url", "search"}


class DryRunFillError(RuntimeError):
    def __init__(self, category: str, message: str):
        self.category = category
        super().__init__(message)


@dataclass(frozen=True)
class FillCandidate:
    plan: FormFieldPlan
    profile: ProfileField


@dataclass(frozen=True)
class FilledField:
    field_plan_id: str
    profile_field_id: int
    ordinal: int
    label: str
    profile_field_key: str
    profile_status: str
    source_reference: str
    profile_updated_at: datetime
    value_type: str
    value_hash: str


@dataclass(frozen=True)
class DryRunResult:
    manifest_hash: str
    fields: list[FilledField]


def scalar_value(value: Any) -> tuple[str, str]:
    if isinstance(value, bool) or value is None or isinstance(value, (dict, list, tuple)):
        raise DryRunFillError(
            "unsupported_value",
            "A mapped profile value cannot be represented safely by this form control",
        )
    if isinstance(value, str):
        return "string", value
    if isinstance(value, int):
        return "integer", str(value)
    if isinstance(value, float):
        return "number", format(value, ".15g")
    raise DryRunFillError(
        "unsupported_value",
        "A mapped profile value uses an unsupported data type",
    )


def value_hash(value_type: str, serialized: str) -> str:
    payload = json.dumps(
        {"type": value_type, "value": serialized},
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def offline_form(candidates: list[FillCandidate]) -> str:
    controls = []
    for index, candidate in enumerate(candidates):
        input_type = html.escape(candidate.plan.input_type, quote=True)
        label = html.escape(candidate.plan.label)
        controls.append(
            f'<label for="field-{index}">{label}</label>'
            f'<input id="field-{index}" type="{input_type}" autocomplete="off">'
        )
    return "<!doctype html><html><body><form>" + "".join(controls) + "</form></body></html>"


def execute_offline_dry_run(candidates: list[FillCandidate]) -> DryRunResult:
    if not candidates:
        raise DryRunFillError("no_fields", "No verified, supported fields are available for dry-run filling")
    for candidate in candidates:
        if candidate.plan.input_type not in SUPPORTED_INPUT_TYPES:
            raise DryRunFillError(
                "unsupported_control",
                f"The field '{candidate.plan.label}' uses a control that requires manual review",
            )
        if candidate.profile.status != "verified" or candidate.profile.value_json is None:
            raise DryRunFillError(
                "unverified_profile",
                f"The field '{candidate.plan.label}' no longer has a verified profile source",
            )

    filled: list[FilledField] = []
    manifest: list[dict[str, Any]] = []
    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(channel=settings.browser_channel, headless=True)
            context = browser.new_context(
                accept_downloads=False,
                java_script_enabled=False,
                service_workers="block",
            )
            context.route("**/*", lambda route: route.abort("blockedbyclient"))
            page = context.new_page()
            try:
                page.set_content(offline_form(candidates), wait_until="domcontentloaded")
                for index, candidate in enumerate(candidates):
                    value_type, serialized = scalar_value(candidate.profile.value_json)
                    locator = page.locator(f"#field-{index}")
                    locator.fill(serialized)
                    if locator.input_value() != serialized:
                        raise DryRunFillError(
                            "fill_verification_failed",
                            f"The field '{candidate.plan.label}' did not retain the intended value",
                        )
                    digest = value_hash(value_type, serialized)
                    evidence = FilledField(
                        field_plan_id=candidate.plan.id,
                        profile_field_id=candidate.profile.id,
                        ordinal=candidate.plan.ordinal,
                        label=candidate.plan.label,
                        profile_field_key=candidate.profile.field_key,
                        profile_status=candidate.profile.status,
                        source_reference=candidate.profile.source or "Verified canonical profile",
                        profile_updated_at=candidate.profile.updated_at,
                        value_type=value_type,
                        value_hash=digest,
                    )
                    filled.append(evidence)
                    manifest.append(
                        {
                            "field_plan_id": evidence.field_plan_id,
                            "ordinal": evidence.ordinal,
                            "profile_field_id": evidence.profile_field_id,
                            "profile_field_key": evidence.profile_field_key,
                            "profile_status": evidence.profile_status,
                            "profile_updated_at": evidence.profile_updated_at.isoformat(),
                            "source_reference": evidence.source_reference,
                            "value_type": evidence.value_type,
                            "value_hash": evidence.value_hash,
                        }
                    )
            finally:
                context.close()
                browser.close()
    except DryRunFillError:
        raise
    except PlaywrightError as error:
        raise DryRunFillError(
            "browser_error",
            "The isolated offline browser could not complete the dry run",
        ) from error

    manifest_bytes = json.dumps(
        manifest,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return DryRunResult(
        manifest_hash=hashlib.sha256(manifest_bytes).hexdigest(),
        fields=filled,
    )
