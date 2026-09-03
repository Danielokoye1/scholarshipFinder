from app.catalogs.nsbe_fall_2026 import CANDIDATES
from app.schemas import ScholarshipIngest


def test_nsbe_catalog_candidates_have_grounded_rules_and_unique_sources():
    validated = [ScholarshipIngest.model_validate(item) for item in CANDIDATES]

    assert len(validated) == 8
    assert len({item.source_url for item in validated}) == len(validated)
    for item in validated:
        assert item.application_url.startswith("https://app.smarterselect.com/")
        assert item.requirements["cycle_status"] == "opens_soon"
        assert item.rules
        assert all(rule.source_quote in item.source_text for rule in item.rules)
