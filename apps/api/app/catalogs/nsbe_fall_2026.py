from typing import Any

from fastapi import Response

from app.db import SessionLocal
from app.routes.scholarships import ingest_scholarship
from app.schemas import ScholarshipIngest


SOURCE_URL = "https://nsbe.org/scholarships/"
APPLICATION_URL = "https://app.smarterselect.com/matching/1812/start_page"
COMMON_TEXT = (
    "The Fall 2026 Scholarship Cycle will open soon. "
    "Membership Status: Must be a registered, paid NSBE member. "
    "Field of Study: Must be pursuing a degree in Engineering, Computer Science, "
    "Mathematics, or a related STEM field. "
    "After the GPA is submitted, it must be confirmed by the registered advisor or "
    "University official through their MyNSBE portal."
)


def rule(
    requirement: str,
    field_key: str,
    operator: str,
    source_quote: str,
    expected_value: Any | None = None,
) -> dict[str, Any]:
    item: dict[str, Any] = {
        "requirement": requirement,
        "field_key": field_key,
        "operator": operator,
        "confidence": 0.99,
        "needs_review": False,
        "source_quote": source_quote,
    }
    if operator not in {"exists", "is_true"}:
        item["expected_value"] = expected_value
    return item


def candidate(
    *,
    slug: str,
    name: str,
    amount_min: int,
    amount_max: int,
    regions: str,
    majors: str,
    classifications: str,
    minimum_gpa: float,
    residency: str,
) -> dict[str, Any]:
    scholarship_text = (
        f"{name}. regions {regions}. majors {majors}. classification: {classifications}. "
        f"minimum gpa {minimum_gpa:g}. residency status {residency}. "
        f"amount ${amount_min:,}" + (f"-${amount_max:,}" if amount_max != amount_min else "") + "."
    )
    source_text = f"{COMMON_TEXT} {scholarship_text}"
    common_rules = [
        rule(
            "Applicant must be a registered paid NSBE member",
            "affiliations.nsbe_membership",
            "equals",
            "Membership Status: Must be a registered, paid NSBE member.",
            "Paid active member",
        ),
        rule(
            "GPA must be verified in MyNSBE for the current window",
            "affiliations.nsbe_gpa_verification",
            "equals",
            (
                "After the GPA is submitted, it must be confirmed by the registered advisor "
                "or University official through their MyNSBE portal."
            ),
            "Verified for current window",
        ),
        rule(
            "Applicant must be in Region 4",
            "affiliations.nsbe_region",
            "equals",
            f"regions {regions}.",
            "Region 4",
        ),
        rule(
            "Applicant to be a junior is permitted",
            "education.class_year",
            "equals",
            f"classification: {classifications}.",
            "Junior",
        ),
        rule(
            f"Cumulative GPA must be at least {minimum_gpa:g}",
            "education.gpa",
            "gte",
            f"minimum gpa {minimum_gpa:g}.",
            minimum_gpa,
        ),
    ]
    common_rules.append(
        rule(
            "Applicant's major must be accepted by the scholarship",
            "education.major",
            "exists" if majors == "ALL NSBE Majors" else "contains_any",
            f"majors {majors}.",
            None if majors == "ALL NSBE Majors" else ["Electrical Engineering"],
        )
    )
    common_rules.append(
        rule(
            "Applicant's citizenship or residency must be accepted",
            "identity.citizenship",
            "exists" if "Non U.S Citizen" in residency else "in",
            f"residency status {residency}.",
            None if "Non U.S Citizen" in residency else ["U.S. Citizen", "Permanent Resident"],
        )
    )
    return {
        "name": name,
        "provider": "National Society of Black Engineers",
        "source_url": f"{SOURCE_URL}?catalog=fall-2026&scholarship={slug}",
        "application_url": APPLICATION_URL,
        "description": (
            "Official NSBE catalog match for a paid collegiate Region 4 member. "
            "The Fall 2026 application cycle is listed as opening soon."
        ),
        "award_min_cents": amount_min * 100,
        "award_max_cents": amount_max * 100,
        "award_description": (
            f"${amount_min:,}" if amount_min == amount_max else f"${amount_min:,}-${amount_max:,}"
        ),
        "raw_deadline_text": "Fall 2026 cycle will open soon; deadline not yet posted",
        "deadline_type": "unknown",
        "requirements": {
            "application_form": True,
            "my_nsbe_account": True,
            "current_gpa_verification": True,
            "cycle_status": "opens_soon",
        },
        "source_text": source_text,
        "source_adapter": "nsbe_official_catalog_2026",
        "rules": common_rules,
    }


CANDIDATES = (
    candidate(
        slug="academic-improvement",
        name="NSBE Academic Improvement Scholarship",
        amount_min=1_000,
        amount_max=1_000,
        regions="1, 2, 3, 4, 5, 6",
        majors="ALL NSBE Majors",
        classifications=(
            "Undergraduate Freshman (1st Year), Undergraduate Sophomore (2nd Year), "
            "Undergraduate Junior (3rd Year), Undergraduate Senior (4th Year)"
        ),
        minimum_gpa=2.0,
        residency="U.S. Citizen, Permanent Resident, Non U.S Citizen",
    ),
    candidate(
        slug="cargill",
        name="Cargill Scholarship",
        amount_min=5_000,
        amount_max=5_000,
        regions="4, 5",
        majors=(
            "Agricultural Engineering, Chemical Engineering, Computer Engineering, Computer "
            "Science, Electrical Engineering, Industrial/Systems Engineering, Manufacturing "
            "Engineering, Materials Engineering, Mechanical Engineering"
        ),
        classifications=(
            "Undergraduate Freshman (1st Year), Undergraduate Sophomore (2nd Year), "
            "Undergraduate Junior (3rd Year), Undergraduate Senior (4th Year)"
        ),
        minimum_gpa=2.7,
        residency="U.S. Citizen, Permanent Resident",
    ),
    candidate(
        slug="intel",
        name="Intel Scholarship",
        amount_min=5_000,
        amount_max=5_000,
        regions="1, 2, 3, 4, 5, 6",
        majors=(
            "Aerospace Engineering, Agricultural Engineering, Biomedical Engineering, Chemical "
            "Engineering, Chemistry, Civil Engineering, Computer Engineering, Computer Science, "
            "Electrical Engineering, Environmental Engineering, Industrial/Systems Engineering, "
            "Information Technology, Manufacturing Engineering, Marine Engineering, Materials "
            "Engineering, Math, Mechanical Engineering, Mining Engineering, Petroleum Engineering, "
            "Physics, Software Management, Technology"
        ),
        classifications=(
            "Undergraduate Freshman (1st Year), Undergraduate Sophomore (2nd Year), "
            "Undergraduate Junior (3rd Year)"
        ),
        minimum_gpa=3.0,
        residency="U.S. Citizen, Permanent Resident, Non U.S Citizen",
    ),
    candidate(
        slug="honeywell-technologies",
        name="Honeywell Technologies Scholarship",
        amount_min=5_000,
        amount_max=5_000,
        regions="1, 2, 3, 4, 5, 6",
        majors=(
            "Chemical Engineering, Computer Engineering, Computer Science, Electrical Engineering, "
            "Industrial/Systems Engineering, Information Technology, Manufacturing Engineering, "
            "Mechanical Engineering, Software Management, Technology"
        ),
        classifications=(
            "Undergraduate Sophomore (2nd Year), Undergraduate Junior (3rd Year), "
            "Undergraduate Senior (4th Year)"
        ),
        minimum_gpa=3.0,
        residency="U.S. Citizen, Permanent Resident",
    ),
    candidate(
        slug="honeywell-aerospace",
        name="Honeywell Aerospace Scholarship",
        amount_min=5_000,
        amount_max=5_000,
        regions="1, 2, 3, 4, 5, 6",
        majors=(
            "Aerospace Engineering, Computer Engineering, Computer Science, Electrical Engineering, "
            "Industrial/Systems Engineering, Information Technology, Manufacturing Engineering, "
            "Mechanical Engineering, Software Management, Technology"
        ),
        classifications=(
            "Undergraduate Freshman (1st Year), Undergraduate Sophomore (2nd Year), "
            "Undergraduate Junior (3rd Year), Undergraduate Senior (4th Year), Graduate Student"
        ),
        minimum_gpa=3.0,
        residency="U.S. Citizen, Permanent Resident",
    ),
    candidate(
        slug="cummins",
        name="Cummins Inc. Scholarship",
        amount_min=10_000,
        amount_max=10_000,
        regions="2, 4, Howard University, North Carolina A&T State",
        majors=(
            "Aerospace Engineering, Chemical Engineering, Computer Engineering, Computer Science, "
            "Electrical Engineering, Environmental Engineering, Industrial/Systems Engineering, "
            "Manufacturing Engineering, Materials Engineering, Mechanical Engineering"
        ),
        classifications="Undergraduate Sophomore (2nd Year), Undergraduate Junior (3rd Year)",
        minimum_gpa=3.0,
        residency="U.S. Citizen, Permanent Resident, Non U.S Citizen",
    ),
    candidate(
        slug="fulfilling-the-legacy",
        name="NSBE Fulfilling the Legacy Scholarship",
        amount_min=500,
        amount_max=500,
        regions="1, 2, 3, 4, 5, 6",
        majors="ALL NSBE Majors",
        classifications=(
            "High School Senior (12th Grade), Undergraduate Freshman (1st Year), "
            "Undergraduate Junior (3rd Year), Undergraduate Sophomore (2nd Year), "
            "Undergraduate Senior (4th Year), Graduate Student"
        ),
        minimum_gpa=3.0,
        residency="U.S. Citizen, Permanent Resident, Non U.S Citizen",
    ),
    candidate(
        slug="csp-cgp-fellows",
        name="NSBE CSP/CGP/Fellows Scholarship",
        amount_min=1_000,
        amount_max=1_500,
        regions="1, 2, 3, 4, 5, 6",
        majors="ALL NSBE Majors",
        classifications=(
            "Undergraduate Freshman (1st Year), Undergraduate Sophomore (2nd Year), "
            "Undergraduate Junior (3rd Year), Undergraduate Senior (4th Year), Graduate Student"
        ),
        minimum_gpa=2.5,
        residency="U.S. Citizen, Permanent Resident, Non U.S Citizen",
    ),
)


def main() -> None:
    results = []
    with SessionLocal() as db:
        for payload in CANDIDATES:
            response = Response()
            result = ingest_scholarship(ScholarshipIngest.model_validate(payload), response, db)
            results.append(
                {
                    "name": payload["name"],
                    "created": result.created,
                    "eligibility": result.eligibility_status,
                    "legitimacy": result.legitimacy_status,
                }
            )
    for result in results:
        print(result)


if __name__ == "__main__":
    main()
