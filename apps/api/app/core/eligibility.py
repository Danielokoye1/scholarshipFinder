from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Any
import uuid

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.config import settings
from app.core.normalization import clean_text
from app.models import EligibilityCheck, EligibilityRule, ProfileField, Scholarship, now_utc


@dataclass(frozen=True)
class RuleEvaluation:
    result: str
    evidence: str


def normalized_scalar(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    return clean_text(str(value)).casefold()


def as_decimal(value: Any) -> Decimal | None:
    try:
        if isinstance(value, bool) or value is None:
            return None
        return Decimal(str(value))
    except (InvalidOperation, ValueError):
        return None


def as_items(value: Any) -> list[Any]:
    if isinstance(value, list):
        return value
    if isinstance(value, tuple):
        return list(value)
    return [value]


def evaluate_operator(operator: str, profile_value: Any, expected: Any) -> RuleEvaluation:
    if operator == "exists":
        passed = profile_value is not None and profile_value != "" and profile_value != []
    elif operator == "is_true":
        passed = profile_value is True
    elif operator in {"gte", "lte"}:
        actual_number = as_decimal(profile_value)
        expected_number = as_decimal(expected)
        if actual_number is None or expected_number is None:
            return RuleEvaluation("needs_verification", "The rule requires numeric values but one value is not numeric")
        passed = actual_number >= expected_number if operator == "gte" else actual_number <= expected_number
    elif operator in {"equals", "not_equals"}:
        passed = normalized_scalar(profile_value) == normalized_scalar(expected)
        if operator == "not_equals":
            passed = not passed
    elif operator == "in":
        expected_values = {normalized_scalar(item) for item in as_items(expected)}
        actual_values = {normalized_scalar(item) for item in as_items(profile_value)}
        passed = bool(actual_values & expected_values)
    elif operator in {"contains_any", "contains_all"}:
        actual_values = [normalized_scalar(item) for item in as_items(profile_value)]
        expected_values = [normalized_scalar(item) for item in as_items(expected)]

        def matches(expected_item: str) -> bool:
            expected_tokens = set(expected_item.split())
            return any(
                expected_item == actual_item or expected_tokens <= set(actual_item.split())
                for actual_item in actual_values
            )

        passed = (
            any(matches(item) for item in expected_values)
            if operator == "contains_any"
            else all(matches(item) for item in expected_values)
        )
    else:
        return RuleEvaluation("needs_verification", f"Unsupported operator: {operator}")
    return RuleEvaluation("pass" if passed else "fail", "Deterministic comparison completed")


def evaluate_rule(rule: EligibilityRule, profile: ProfileField | None) -> RuleEvaluation:
    if rule.needs_review or rule.confidence < settings.eligibility_rule_confidence_threshold:
        return RuleEvaluation("needs_verification", "The extracted rule requires human verification")
    if not rule.field_key:
        return RuleEvaluation("needs_verification", "The requirement is not mapped to a canonical profile field")
    if profile is None or profile.status == "unknown" or profile.value_json is None:
        return RuleEvaluation("unknown", f"No usable profile value exists for {rule.field_key}")
    if profile.status not in {"verified", "user_entered"}:
        return RuleEvaluation("needs_verification", f"Profile field {rule.field_key} lacks acceptable provenance")
    return evaluate_operator(rule.operator, profile.value_json, rule.expected_value_json)


def evaluate_scholarship(db: Session, scholarship: Scholarship) -> list[EligibilityCheck]:
    rules = list(
        db.scalars(
            select(EligibilityRule)
            .where(EligibilityRule.scholarship_id == scholarship.id)
            .order_by(EligibilityRule.created_at, EligibilityRule.id)
        )
    )
    db.execute(
        update(EligibilityCheck)
        .where(
            EligibilityCheck.scholarship_id == scholarship.id,
            EligibilityCheck.is_current.is_(True),
        )
        .values(is_current=False)
    )
    evaluation_run_id = str(uuid.uuid4())
    checks: list[EligibilityCheck] = []
    for rule in rules:
        profile = (
            db.scalar(select(ProfileField).where(ProfileField.field_key == rule.field_key))
            if rule.field_key
            else None
        )
        result = evaluate_rule(rule, profile)
        check = EligibilityCheck(
            scholarship_id=scholarship.id,
            rule_id=rule.id,
            profile_field_id=profile.id if profile else None,
            profile_value_json=profile.value_json if profile else None,
            result=result.result,
            evidence=result.evidence,
            confidence=rule.confidence,
            evaluation_run_id=evaluation_run_id,
            is_current=True,
            evaluated_at=now_utc(),
        )
        db.add(check)
        checks.append(check)

    results = [check.result for check in checks]
    if "fail" in results:
        scholarship.eligibility_status = "ineligible"
    elif not results or "unknown" in results or "needs_verification" in results:
        scholarship.eligibility_status = "needs_information"
    else:
        scholarship.eligibility_status = "eligible"
    scholarship.eligibility_score = (
        sum(result == "pass" for result in results) / len(results) if results else 0.0
    )
    return checks
