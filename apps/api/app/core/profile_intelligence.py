import re
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from pypdf import PdfReader
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.models import Document, ProfileField


@dataclass(frozen=True)
class FieldDefinition:
    field_key: str
    label: str
    section: str
    input_type: str = "text"
    options: tuple[str, ...] = ()
    important: bool = False
    sensitive: bool = False
    help_text: str = ""


FIELD_DEFINITIONS = (
    FieldDefinition("identity.first_name", "First name", "identity", important=True),
    FieldDefinition("identity.middle_name", "Middle name", "identity"),
    FieldDefinition("identity.last_name", "Last name", "identity", important=True),
    FieldDefinition("identity.preferred_name", "Preferred name", "identity"),
    FieldDefinition("identity.date_of_birth", "Date of birth", "identity", "date", sensitive=True),
    FieldDefinition("identity.citizenship", "Citizenship", "identity", important=True),
    FieldDefinition(
        "identity.residency",
        "Residency status (not your address)",
        "identity",
        important=True,
        help_text="For example: U.S. resident, permanent resident, or international student.",
    ),
    FieldDefinition("contact.email", "Email", "contact", "email", important=True),
    FieldDefinition("contact.phone", "Phone", "contact", "tel", important=True),
    FieldDefinition("address.street", "Street address", "address", important=True, sensitive=True),
    FieldDefinition("address.line_2", "Apartment / unit", "address", sensitive=True),
    FieldDefinition("address.city", "City", "address", important=True),
    FieldDefinition("address.state", "State", "address", important=True),
    FieldDefinition("address.postal_code", "ZIP code", "address", important=True, sensitive=True),
    FieldDefinition("address.country", "Country", "address", important=True),
    FieldDefinition("education.institution", "University / institution", "education", important=True),
    FieldDefinition("education.degree", "Degree", "education", important=True),
    FieldDefinition("education.major", "Major", "education", important=True),
    FieldDefinition("education.minor", "Minor", "education"),
    FieldDefinition("education.gpa", "Cumulative GPA", "education", "number", important=True),
    FieldDefinition("education.gpa_scale", "GPA scale", "education", "number", important=True),
    FieldDefinition(
        "education.graduation_date",
        "Expected graduation",
        "education",
        important=True,
        help_text="Use a term and year (for example, Fall 2028) or an exact date.",
    ),
    FieldDefinition(
        "education.class_year",
        "Current class standing",
        "education",
        options=("Freshman", "Sophomore", "Junior", "Senior", "Graduate", "Other"),
        important=True,
    ),
    FieldDefinition(
        "education.enrollment_status",
        "Enrollment status",
        "education",
        options=("Full-time", "Part-time", "Not currently enrolled"),
        important=True,
    ),
)

SECTION_TITLES = {
    "identity": "Identity",
    "contact": "Contact",
    "address": "Mailing address",
    "education": "Education",
}

US_STATES = {
    "AL", "AK", "AZ", "AR", "CA", "CO", "CT", "DE", "FL", "GA", "HI", "ID",
    "IL", "IN", "IA", "KS", "KY", "LA", "ME", "MD", "MA", "MI", "MN", "MS",
    "MO", "MT", "NE", "NV", "NH", "NJ", "NM", "NY", "NC", "ND", "OH", "OK",
    "OR", "PA", "RI", "SC", "SD", "TN", "TX", "UT", "VT", "VA", "WA", "WV",
    "WI", "WY", "DC",
}

STATE_NAMES = {
    "alabama": "AL", "alaska": "AK", "arizona": "AZ", "arkansas": "AR",
    "california": "CA", "colorado": "CO", "connecticut": "CT", "delaware": "DE",
    "florida": "FL", "georgia": "GA", "hawaii": "HI", "idaho": "ID",
    "illinois": "IL", "indiana": "IN", "iowa": "IA", "kansas": "KS",
    "kentucky": "KY", "louisiana": "LA", "maine": "ME", "maryland": "MD",
    "massachusetts": "MA", "michigan": "MI", "minnesota": "MN", "mississippi": "MS",
    "missouri": "MO", "montana": "MT", "nebraska": "NE", "nevada": "NV",
    "new hampshire": "NH", "new jersey": "NJ", "new mexico": "NM", "new york": "NY",
    "north carolina": "NC", "north dakota": "ND", "ohio": "OH", "oklahoma": "OK",
    "oregon": "OR", "pennsylvania": "PA", "rhode island": "RI",
    "south carolina": "SC", "south dakota": "SD", "tennessee": "TN", "texas": "TX",
    "utah": "UT", "vermont": "VT", "virginia": "VA", "washington": "WA",
    "west virginia": "WV", "wisconsin": "WI", "wyoming": "WY",
    "district of columbia": "DC",
}


def clean_string(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def normalize_profile_value(field_key: str, value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, str):
        value = clean_string(value)
    if value == "":
        return None
    if field_key in {"education.gpa", "education.gpa_scale"}:
        try:
            number = float(value)
        except (TypeError, ValueError) as error:
            raise ValueError("GPA values must be numeric") from error
        if number < 0 or number > 5:
            raise ValueError("GPA values must be between 0 and 5")
        return number
    if field_key == "contact.email":
        normalized = str(value).casefold()
        if not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", normalized):
            raise ValueError("Enter a complete email address")
        return normalized
    if field_key == "contact.phone":
        digits = re.sub(r"\D", "", str(value))
        if len(digits) == 11 and digits.startswith("1"):
            digits = digits[1:]
        if len(digits) != 10:
            raise ValueError("Enter a 10-digit US phone number")
        return f"({digits[:3]}) {digits[3:6]}-{digits[6:]}"
    if field_key == "address.state":
        state = str(value).strip()
        normalized = STATE_NAMES.get(state.casefold(), state.upper())
        if normalized not in US_STATES:
            raise ValueError("Enter a valid US state name or two-letter abbreviation")
        return normalized
    if field_key == "address.postal_code":
        postal_code = str(value).strip()
        if not re.fullmatch(r"\d{5}(-\d{4})?", postal_code):
            raise ValueError("Enter a five-digit ZIP code or ZIP+4")
        return postal_code
    if field_key == "education.class_year":
        options = {item.casefold(): item for item in FIELD_BY_KEY[field_key].options}
        if str(value).casefold() not in options:
            raise ValueError("Choose a supported class standing")
        return options[str(value).casefold()]
    if field_key == "education.enrollment_status":
        options = {item.casefold(): item for item in FIELD_BY_KEY[field_key].options}
        aliases = {"full time": "Full-time", "part time": "Part-time"}
        normalized = aliases.get(str(value).casefold(), options.get(str(value).casefold()))
        if normalized is None:
            raise ValueError("Choose Full-time, Part-time, or Not currently enrolled")
        return normalized
    if field_key == "education.graduation_date":
        text = str(value)
        if not re.search(r"\b20\d{2}\b", text):
            raise ValueError("Expected graduation must include a four-digit year")
        return text
    return value


FIELD_BY_KEY = {item.field_key: item for item in FIELD_DEFINITIONS}


def parse_graduation(value: Any) -> tuple[str | None, int | None]:
    text = str(value or "")
    year_match = re.search(r"\b(20\d{2})\b", text)
    term_match = re.search(r"\b(fall|spring|winter|summer)\b", text, re.IGNORECASE)
    return (
        term_match.group(1).title() if term_match else None,
        int(year_match.group(1)) if year_match else None,
    )


def materialize_derived_fields(db: Session) -> bool:
    fields = {item.field_key: item for item in db.scalars(select(ProfileField))}
    derived: dict[str, tuple[Any | None, str, list[ProfileField]]] = {}
    names = [
        fields.get("identity.first_name"),
        fields.get("identity.middle_name"),
        fields.get("identity.last_name"),
    ]
    required_names = [fields.get("identity.first_name"), fields.get("identity.last_name")]
    if all(item and item.status == "verified" and item.value_json for item in required_names):
        parts = [str(item.value_json).strip() for item in names if item and item.value_json]
        sources = [item for item in names if item and item.value_json]
        derived["identity.full_name"] = (
            " ".join(parts),
            "Derived by profile intelligence from verified name components",
            sources,
        )
    graduation = fields.get("education.graduation_date")
    if graduation and graduation.status == "verified" and graduation.value_json:
        _, year = parse_graduation(graduation.value_json)
        if year:
            derived["education.graduation_year"] = (
                year,
                "Derived by profile intelligence from verified expected graduation",
                [graduation],
            )

    changed = False
    managed_keys = {"identity.full_name", "education.graduation_year"}
    for field_key, (value, source, inputs) in derived.items():
        item = fields.get(field_key)
        if item is not None and not (item.source or "").startswith("Derived by profile intelligence"):
            continue
        if item is None:
            item = ProfileField(field_key=field_key)
            db.add(item)
        status = "verified" if all(source_item.status == "verified" for source_item in inputs) else "user_entered"
        if item.value_json != value or item.status != status or item.source != source:
            item.value_json = value
            item.status = status
            item.source = source
            item.last_verified_at = datetime.now(UTC) if status == "verified" else None
            changed = True

    for field_key in managed_keys - derived.keys():
        item = fields.get(field_key)
        if item is None or not (item.source or "").startswith("Derived by profile intelligence"):
            continue
        if item.value_json is not None or item.status != "unknown":
            item.value_json = None
            item.status = "unknown"
            item.source = "Derived value unavailable because its source fields are incomplete or unverified"
            item.last_verified_at = None
            changed = True
    return changed


@dataclass(frozen=True)
class LocalDocumentText:
    document: Document
    status: str
    text: str
    page_count: int | None


def read_local_document(document: Document) -> LocalDocumentText:
    storage = settings.document_storage_path.resolve()
    path = (storage / document.stored_filename).resolve()
    if storage not in path.parents or not path.is_file():
        return LocalDocumentText(document, "missing", "", None)
    if path.suffix.casefold() != ".pdf":
        return LocalDocumentText(document, "unsupported", "", None)
    if document.size_bytes > settings.max_document_bytes:
        return LocalDocumentText(document, "too_large", "", None)
    try:
        reader = PdfReader(path)
        if reader.is_encrypted:
            return LocalDocumentText(document, "locked", "", None)
        pages = [reader.pages[index] for index in range(min(len(reader.pages), 50))]
        text = "\n".join((page.extract_text() or "") for page in pages)[:300_000]
        return LocalDocumentText(document, "readable" if text.strip() else "no_text", text, len(reader.pages))
    except Exception:
        return LocalDocumentText(document, "unreadable", "", None)


def normalized_document_text(value: str) -> str:
    return clean_string(value).casefold().replace("–", "-").replace("—", "-")


def make_issue(
    code: str,
    severity: str,
    title: str,
    message: str,
    field_keys: list[str],
    *,
    evidence_sources: list[str] | None = None,
    suggested_value: Any | None = None,
) -> dict[str, Any]:
    return {
        "code": code,
        "severity": severity,
        "title": title,
        "message": message,
        "field_keys": field_keys,
        "evidence_sources": evidence_sources or [],
        "suggested_value": suggested_value,
        "requires_confirmation": suggested_value is not None,
    }


def profile_review(db: Session) -> dict[str, Any]:
    materialize_derived_fields(db)
    db.flush()
    fields = {item.field_key: item for item in db.scalars(select(ProfileField))}
    documents = list(db.scalars(select(Document).order_by(Document.created_at, Document.id)))
    document_texts = [read_local_document(document) for document in documents]
    latest_by_type: dict[str, str] = {}
    for document in documents:
        latest_by_type[document.document_type] = document.id
    latest_resume = next(
        (
            item
            for item in reversed(document_texts)
            if item.document.document_type == "resume"
        ),
        None,
    )
    resume_text = latest_resume.text if latest_resume and latest_resume.status == "readable" else ""
    normalized_resume = normalized_document_text(resume_text)
    issues: list[dict[str, Any]] = []

    important = [item for item in FIELD_DEFINITIONS if item.important]

    enrollment = fields.get("education.enrollment_status")
    if enrollment and str(enrollment.value_json).casefold() not in {
        "full-time", "part-time", "not currently enrolled"
    }:
        issues.append(
            make_issue(
                "invalid_enrollment_status",
                "error",
                "Enrollment status needs a specific value",
                "Scholarships usually require Full-time, Part-time, or Not currently enrolled—not a yes/no value.",
                ["education.enrollment_status"],
            )
        )

    residency = fields.get("identity.residency")
    if residency and isinstance(residency.value_json, str) and re.search(
        r"\b\d{1,6}\s+.+\b(street|st|road|rd|avenue|ave|drive|dr|lane|ln|square|sq|boulevard|blvd|court|ct|way)\b",
        residency.value_json,
        re.IGNORECASE,
    ):
        issues.append(
            make_issue(
                "misplaced_address_in_residency",
                "error",
                "A mailing address may be in the wrong field",
                "Residency status should describe your legal or student residency—not a street address. Review this value and place mailing details in the address section.",
                ["identity.residency"],
            )
        )

    gpa = fields.get("education.gpa")
    gpa_scale = fields.get("education.gpa_scale")
    scale_match = re.search(r"\b(?:cumulative\s+)?gpa\s*:\s*[0-5](?:\.\d+)?\s*/\s*([0-5](?:\.\d+)?)", resume_text, re.IGNORECASE)
    if gpa and not gpa_scale and scale_match:
        issues.append(
            make_issue(
                "gpa_scale_suggestion",
                "warning",
                "GPA scale is missing",
                "Your readable resume states a GPA scale. Confirm it before the system uses GPA-dependent scholarships.",
                ["education.gpa_scale"],
                evidence_sources=["resume"],
                suggested_value=float(scale_match.group(1)),
            )
        )

    degree = fields.get("education.degree")
    degree_match = re.search(
        r"\bBachelor\s+of\s+Science\s+in\s+Engineering\b",
        resume_text,
        re.IGNORECASE,
    )
    if (not degree or not degree.value_json) and degree_match:
        issues.append(
            make_issue(
                "degree_suggestion",
                "warning",
                "Degree is available from your resume",
                "A degree name appears in the readable resume. Confirm it before it becomes a profile fact.",
                ["education.degree"],
                evidence_sources=["resume"],
                suggested_value="Bachelor of Science in Engineering",
            )
        )
    if gpa and str(gpa.value_json).casefold() in normalized_resume:
        issues.append(
            make_issue(
                "gpa_corroborated",
                "success",
                "GPA appears in a readable document",
                "The stored GPA was found in the locally read resume.",
                ["education.gpa"],
                evidence_sources=["resume"],
            )
        )

    graduation = fields.get("education.graduation_date")
    document_graduation = re.search(
        r"expected\s+graduation\s*[-:]?\s*(fall|spring|winter|summer)?\s*(20\d{2})",
        resume_text,
        re.IGNORECASE,
    )
    if graduation and document_graduation:
        profile_term, profile_year = parse_graduation(graduation.value_json)
        document_term = document_graduation.group(1).title() if document_graduation.group(1) else None
        document_year = int(document_graduation.group(2))
        if profile_year != document_year or (
            profile_term and document_term and profile_term != document_term
        ):
            suggested = f"{document_term} {document_year}" if document_term else str(document_year)
            issues.append(
                make_issue(
                    "graduation_conflict",
                    "error",
                    "Graduation information conflicts",
                    "The profile and readable resume do not state the same expected graduation term. Confirm the correct value; nothing was overwritten.",
                    ["education.graduation_date"],
                    evidence_sources=["resume"],
                    suggested_value=suggested,
                )
            )
        else:
            issues.append(
                make_issue(
                    "graduation_corroborated",
                    "success",
                    "Graduation timing is corroborated",
                    "The profile graduation timing agrees with the readable resume.",
                    ["education.graduation_date"],
                    evidence_sources=["resume"],
                )
            )

    class_year = fields.get("education.class_year")
    _, graduation_year = parse_graduation(graduation.value_json if graduation else None)
    if graduation_year:
        current = datetime.now(UTC)
        academic_year = current.year if current.month >= 7 else current.year - 1
        years_until_graduation = graduation_year - academic_year
        expected = {4: "Freshman", 3: "Sophomore", 2: "Junior", 1: "Senior"}.get(years_until_graduation)
        if class_year and expected and str(class_year.value_json).casefold() == expected.casefold():
            issues.append(
                make_issue(
                    "class_year_consistent",
                    "success",
                    "Class standing is consistent",
                    f"{class_year.value_json} is consistent with the recorded {graduation_year} graduation year for the current academic cycle.",
                    ["education.class_year", "education.graduation_date"],
                )
            )
        elif class_year and expected:
            issues.append(
                make_issue(
                    "class_year_review",
                    "warning",
                    "Class standing may need review",
                    f"A typical schedule suggests {expected}, but nontraditional and part-time programs can differ. Confirm rather than automatically changing it.",
                    ["education.class_year", "education.graduation_date"],
                    suggested_value=expected,
                )
            )
        elif not class_year:
            issues.append(
                make_issue(
                    "class_year_missing",
                    "warning",
                    "Current class standing is missing",
                    "Add your current standing so class-year eligibility can be evaluated independently of graduation year.",
                    ["education.class_year"],
                    suggested_value=expected,
                )
            )

    address_keys = ["address.street", "address.city", "address.state", "address.postal_code", "address.country"]
    missing_address = [key for key in address_keys if not fields.get(key) or not fields[key].value_json]
    if missing_address:
        issues.append(
            make_issue(
                "address_incomplete",
                "warning",
                "Mailing address is incomplete",
                "Local validation can check formatting only after all address components are present. No address has been sent to an external verifier.",
                missing_address,
            )
        )
    else:
        issues.append(
            make_issue(
                "address_structural_only",
                "info",
                "Address is structurally complete",
                "The address has all expected components, but physical deliverability has not been externally verified.",
                address_keys,
            )
        )

    for field_key in ("identity.first_name", "identity.last_name", "education.institution", "education.major"):
        field = fields.get(field_key)
        if not field or not isinstance(field.value_json, str) or not normalized_resume:
            continue
        candidate = normalized_document_text(field.value_json)
        core_candidate = candidate.split(" - ")[0]
        if candidate in normalized_resume or (len(core_candidate) >= 5 and core_candidate in normalized_resume):
            issues.append(
                make_issue(
                    f"{field_key.replace('.', '_')}_corroborated",
                    "success",
                    f"{FIELD_BY_KEY[field_key].label} is corroborated",
                    "The stored value appears in the locally readable resume.",
                    [field_key],
                    evidence_sources=["resume"],
                )
            )

    for document_text in document_texts:
        if document_text.status != "readable":
            issues.append(
                make_issue(
                    f"document_{document_text.document.id}_{document_text.status}",
                    "warning",
                    f"{document_text.document.document_type.title()} could not be corroborated",
                    "The file remains available locally, but its text could not be read without bypassing document restrictions or adding unsupported extraction.",
                    [],
                    evidence_sources=[document_text.document.document_type],
                )
            )

    sections = []
    for section_key, title in SECTION_TITLES.items():
        section_fields = []
        for definition in (item for item in FIELD_DEFINITIONS if item.section == section_key):
            stored = fields.get(definition.field_key)
            section_fields.append(
                {
                    "field_key": definition.field_key,
                    "label": definition.label,
                    "value": stored.value_json if stored else None,
                    "status": stored.status if stored else "unknown",
                    "source": stored.source if stored else None,
                    "last_verified_at": stored.last_verified_at if stored else None,
                    "input_type": definition.input_type,
                    "options": list(definition.options),
                    "important": definition.important,
                    "sensitive": definition.sensitive,
                    "help_text": definition.help_text,
                }
            )
        sections.append({"key": section_key, "title": title, "fields": section_fields})

    document_checks = [
        {
            "document_id": item.document.id,
            "document_type": item.document.document_type,
            "version": item.document.version,
            "is_latest": latest_by_type.get(item.document.document_type) == item.document.id,
            "status": item.status,
            "page_count": item.page_count,
        }
        for item in document_texts
    ]
    invalid_keys = {
        field_key
        for issue in issues
        if issue["severity"] == "error"
        for field_key in issue["field_keys"]
    }
    completed = sum(
        bool(
            item.field_key not in invalid_keys
            and fields.get(item.field_key)
            and fields[item.field_key].value_json is not None
            and fields[item.field_key].value_json != ""
        )
        for item in important
    )
    return {
        "completeness_percent": round(100 * completed / len(important), 1),
        "important_fields_complete": completed,
        "important_fields_total": len(important),
        "sections": sections,
        "issues": issues,
        "document_checks": document_checks,
        "external_address_verification": "not_performed",
        "generated_at": datetime.now(UTC),
    }
