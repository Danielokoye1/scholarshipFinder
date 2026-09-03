import re
from dataclasses import dataclass

from app.browser.inspector import RawFormField
from app.models import ProfileField


@dataclass(frozen=True)
class MappingCandidate:
    profile_key: str
    confidence: float


@dataclass(frozen=True)
class PlannedField:
    field: RawFormField
    profile_field_key: str | None
    mapping_confidence: float
    profile_status: str | None
    disposition: str
    reason: str


AUTOCOMPLETE_MAP = {
    "given-name": "identity.first_name",
    "additional-name": "identity.middle_name",
    "family-name": "identity.last_name",
    "name": "identity.full_name",
    "email": "contact.email",
    "tel": "contact.phone",
    "street-address": "address.street",
    "address-line1": "address.street",
    "address-line2": "address.line_2",
    "address-level2": "address.city",
    "address-level1": "address.state",
    "postal-code": "address.postal_code",
    "country": "address.country",
    "bday": "identity.date_of_birth",
}

LABEL_RULES: list[tuple[re.Pattern[str], str, float]] = [
    (re.compile(r"\b(first|given) name\b"), "identity.first_name", 0.98),
    (re.compile(r"\b(middle|additional) name\b"), "identity.middle_name", 0.98),
    (re.compile(r"\b(last|family|surname)\b"), "identity.last_name", 0.98),
    (re.compile(r"\b(full|legal) name\b|\bapplicant name\b"), "identity.full_name", 0.96),
    (re.compile(r"\be-?mail( address)?\b"), "contact.email", 0.99),
    (re.compile(r"\b(phone|mobile|telephone)( number)?\b"), "contact.phone", 0.97),
    (re.compile(r"\bstreet( address)?\b|\baddress line 1\b"), "address.street", 0.96),
    (re.compile(r"\baddress line 2\b|\bapt\.?|\bunit\b"), "address.line_2", 0.94),
    (re.compile(r"\bcity\b"), "address.city", 0.96),
    (re.compile(r"\b(state|province)\b"), "address.state", 0.94),
    (re.compile(r"\b(zip|postal) code\b"), "address.postal_code", 0.98),
    (re.compile(r"\bcountry\b"), "address.country", 0.94),
    (re.compile(r"\b(date of birth|birth date|birthday)\b"), "identity.date_of_birth", 0.96),
    (re.compile(r"\b(cumulative )?gpa\b|grade point average"), "education.gpa", 0.99),
    (re.compile(r"\b(major|field of study)\b"), "education.major", 0.97),
    (re.compile(r"\bminor\b"), "education.minor", 0.96),
    (re.compile(r"\b(college|university|school|institution)( name)?\b"), "education.institution", 0.93),
    (re.compile(r"\bgraduation (date|year)\b|\bexpected graduation\b"), "education.graduation_date", 0.96),
    (re.compile(r"\b(class year|year in school|academic level)\b"), "education.class_year", 0.94),
    (re.compile(r"\b(enrollment status|student status)\b"), "education.enrollment_status", 0.94),
    (re.compile(r"\bcitizenship( status)?\b"), "identity.citizenship", 0.96),
    (
        re.compile(r"\b(national origin|cultural heritage|ancestry)\b"),
        "identity.national_origin",
        0.94,
    ),
    (
        re.compile(r"\b(race|racial identity|ethnicity|ethnic identity)\b"),
        "identity.race_ethnicity",
        0.94,
    ),
    (re.compile(r"\b(residency|resident state)\b"), "identity.residency", 0.94),
    (
        re.compile(r"\bnsbe (paid )?(membership|member status)\b"),
        "affiliations.nsbe_membership",
        0.97,
    ),
    (re.compile(r"\bnsbe region\b"), "affiliations.nsbe_region", 0.98),
]

SENSITIVE_PATTERN = re.compile(
    r"\b(ssn|social security|bank|routing|credit card|debit card|passport|driver'?s license|government id|tax id)\b"
)
ESSAY_PATTERN = re.compile(r"\b(essay|personal statement|short answer|describe|explain|why (do|should|are)|tell us)\b")
SIGNATURE_PATTERN = re.compile(r"\b(signature|sign here|i certify|i attest|penalty of perjury)\b")
RECOMMENDATION_PATTERN = re.compile(r"\b(recommendation|recommender|reference email)\b")


def normalize_label(field: RawFormField) -> str:
    return re.sub(
        r"\s+",
        " ",
        f"{field.label} {field.autocomplete or ''}".casefold().replace("_", " ").replace("-", " "),
    ).strip()


def mapping_candidate(field: RawFormField) -> MappingCandidate | None:
    autocomplete = (field.autocomplete or "").casefold().split()
    for token in reversed(autocomplete):
        if token in AUTOCOMPLETE_MAP:
            return MappingCandidate(AUTOCOMPLETE_MAP[token], 1.0)
    label = normalize_label(field)
    for pattern, key, confidence in LABEL_RULES:
        if pattern.search(label):
            return MappingCandidate(key, confidence)
    if field.input_type == "email":
        return MappingCandidate("contact.email", 0.95)
    if field.input_type == "tel":
        return MappingCandidate("contact.phone", 0.93)
    return None


def plan_field(
    field: RawFormField,
    profile_by_key: dict[str, ProfileField],
    confidence_threshold: float,
) -> PlannedField:
    label = normalize_label(field)
    if field.disabled:
        return PlannedField(field, None, 0.0, None, "not_applicable", "The field is disabled")
    if field.input_type == "password":
        return PlannedField(field, None, 0.0, None, "blocked_sensitive", "Password fields require a future credential workflow")
    if SENSITIVE_PATTERN.search(label):
        return PlannedField(field, None, 0.0, None, "blocked_sensitive", "Sensitive identity or financial field requires manual review")
    if field.input_type == "file":
        return PlannedField(field, None, 0.0, None, "manual_review", "Document selection is never inferred during inspection")
    if field.tag_name == "textarea" or ESSAY_PATTERN.search(label):
        return PlannedField(field, None, 0.0, None, "manual_review", "Narrative response requires user review")
    if SIGNATURE_PATTERN.search(label):
        return PlannedField(field, None, 0.0, None, "manual_review", "Signature or attestation requires user review")
    if RECOMMENDATION_PATTERN.search(label):
        return PlannedField(field, None, 0.0, None, "manual_review", "Recommendation handling requires user review")

    candidate = mapping_candidate(field)
    if candidate is None:
        return PlannedField(field, None, 0.0, None, "manual_review", "No deterministic profile mapping was found")
    profile = profile_by_key.get(candidate.profile_key)
    if candidate.confidence < confidence_threshold:
        return PlannedField(
            field,
            candidate.profile_key,
            candidate.confidence,
            profile.status if profile else None,
            "manual_review",
            "Field mapping confidence is below the configured threshold",
        )
    if profile is None or profile.status == "unknown" or profile.value_json is None:
        return PlannedField(
            field,
            candidate.profile_key,
            candidate.confidence,
            profile.status if profile else "unknown",
            "missing_profile_data",
            "The canonical profile does not contain a verified value",
        )
    if profile.status != "verified":
        return PlannedField(
            field,
            candidate.profile_key,
            candidate.confidence,
            profile.status,
            "manual_review",
            "The mapped profile value has not been verified",
        )
    return PlannedField(
        field,
        candidate.profile_key,
        candidate.confidence,
        profile.status,
        "auto_answerable",
        "Deterministic mapping points to a verified canonical profile field",
    )


def build_field_plan(
    fields: list[RawFormField],
    profile_fields: list[ProfileField],
    confidence_threshold: float,
) -> list[PlannedField]:
    profile_by_key = {item.field_key: item for item in profile_fields}
    return [plan_field(field, profile_by_key, confidence_threshold) for field in fields]
