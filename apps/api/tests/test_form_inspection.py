from contextlib import contextmanager
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Thread

import pytest

from app.browser.inspector import (
    BrowserInspectionError,
    InspectionResult,
    RawFormField,
    inspect_application_page,
)
from app.browser.mapping import build_field_plan
from app.browser.network import UnsafeBrowserTarget, redact_url, validate_browser_url
from app.models import ProfileField


FIXTURES = Path(__file__).parent / "fixtures"


class QuietHandler(SimpleHTTPRequestHandler):
    def log_message(self, format, *args):
        return


@contextmanager
def fixture_server():
    handler = partial(QuietHandler, directory=str(FIXTURES))
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}"
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


def raw_field(**overrides):
    values = {
        "ordinal": 0,
        "form_index": 0,
        "tag_name": "input",
        "input_type": "text",
        "label": "Cumulative GPA",
        "required": True,
        "disabled": False,
        "autocomplete": None,
    }
    values.update(overrides)
    return RawFormField(**values)


def test_network_guard_rejects_unsafe_targets(monkeypatch):
    with pytest.raises(UnsafeBrowserTarget, match="requires HTTPS"):
        validate_browser_url("http://example.org/apply")
    with pytest.raises(UnsafeBrowserTarget, match="credentials"):
        validate_browser_url("https://user:secret@example.org/apply")
    with pytest.raises(UnsafeBrowserTarget, match="Direct IP"):
        validate_browser_url("https://203.0.113.10/apply")
    with pytest.raises(UnsafeBrowserTarget, match="not been approved"):
        validate_browser_url(
            "https://redirected.example.net/apply",
            navigation_domain="approved.example.org",
        )
    monkeypatch.setattr("app.browser.network.resolve_addresses", lambda hostname, port: ("127.0.0.1",))
    with pytest.raises(UnsafeBrowserTarget, match="private, local"):
        validate_browser_url("https://internal.example.org/apply")


def test_url_redaction_removes_credentials_query_fragment_and_token_like_paths():
    assert redact_url("https://user:secret@example.org/apply?token=private#step") == "https://example.org/apply"
    assert (
        redact_url("https://example.org/applications/AbCDef1234567890GhijkLMN/review")
        == "https://example.org/applications/[redacted]/review"
    )


def test_field_plan_never_copies_profile_values_and_requires_verified_status():
    fields = [
        raw_field(label="Cumulative GPA"),
        raw_field(ordinal=1, label="Email address", input_type="email", autocomplete="email"),
        raw_field(ordinal=2, label="Social Security Number"),
        raw_field(ordinal=3, tag_name="textarea", input_type="textarea", label="Personal statement"),
    ]
    profile = [
        ProfileField(field_key="education.gpa", value_json=3.42, status="verified", source="Transcript"),
        ProfileField(field_key="contact.email", value_json="private@example.com", status="user_entered", source="User"),
    ]
    plan = build_field_plan(fields, profile, 0.9)
    assert plan[0].disposition == "auto_answerable"
    assert plan[0].profile_field_key == "education.gpa"
    assert plan[1].disposition == "manual_review"
    assert plan[2].disposition == "blocked_sensitive"
    assert plan[3].disposition == "manual_review"
    serialized = repr(plan)
    assert "3.42" not in serialized
    assert "private@example.com" not in serialized


def test_demographic_labels_map_to_distinct_user_confirmed_profile_fields():
    fields = [
        raw_field(label="National origin"),
        raw_field(ordinal=1, label="Race or ethnicity"),
    ]
    profile = [
        ProfileField(
            field_key="identity.national_origin",
            value_json="Example heritage",
            status="user_entered",
            source="User confirmed",
        ),
        ProfileField(
            field_key="identity.race_ethnicity",
            value_json="Example identity",
            status="user_entered",
            source="User confirmed",
        ),
    ]

    plan = build_field_plan(fields, profile, 0.9)

    assert [item.profile_field_key for item in plan] == [
        "identity.national_origin",
        "identity.race_ethnicity",
    ]
    assert all(item.disposition == "manual_review" for item in plan)


def test_nsbe_eligibility_fields_have_deterministic_profile_mappings():
    fields = [
        raw_field(label="NSBE paid membership"),
        raw_field(ordinal=1, label="NSBE Region"),
    ]

    plan = build_field_plan(fields, [], 0.9)

    assert [item.profile_field_key for item in plan] == [
        "affiliations.nsbe_membership",
        "affiliations.nsbe_region",
    ]
    assert all(item.disposition == "missing_profile_data" for item in plan)


def test_playwright_inspection_uses_fixture_without_collecting_values():
    with fixture_server() as origin:
        result = inspect_application_page(
            f"{origin}/simple_application.html",
            allow_private_network=True,
            allow_http=True,
        )
    assert result.response_status == 200
    assert result.page_title == "Fixture Scholarship Application"
    assert len(result.fields) == 6
    assert "essay" in result.barriers
    assert all("must-never-be-stored" not in repr(field) for field in result.fields)
    assert len(result.page_content_hash) == 64
    assert {item["category"] for item in result.blocked_requests} >= {
        "cross_domain_redirect",
        "unsafe_method",
    }


def scholarship_payload():
    return {
        "name": "Inspected Scholarship",
        "provider": "Safe Foundation",
        "source_url": "https://directory.example.org/inspected",
        "application_url": "https://apply.safe-foundation.org/start",
        "requirements": {"application_form": True},
        "source_text": "Applicants must have a cumulative GPA of 3.0 or higher.",
        "rules": [
            {
                "requirement": "Cumulative GPA must be at least 3.0",
                "field_key": "education.gpa",
                "operator": "gte",
                "expected_value": 3.0,
                "confidence": 0.99,
                "needs_review": False,
                "source_quote": "Applicants must have a cumulative GPA of 3.0 or higher.",
            }
        ],
    }


def create_ready_application(client):
    client.put(
        "/api/profile/education.gpa",
        json={"value": 3.42, "status": "verified", "source": "User-reviewed transcript"},
    )
    client.put(
        "/api/safety/domains",
        json={
            "domain": "apply.safe-foundation.org",
            "decision": "approved",
            "notes": "Independently reviewed official provider destination.",
        },
    )
    scholarship = client.post("/api/scholarships/ingest", json=scholarship_payload()).json()
    return client.post(
        "/api/applications", json={"scholarship_id": scholarship["scholarship_id"]}
    ).json()


def test_inspection_endpoint_persists_redacted_plan_and_queues_essay(client, monkeypatch):
    application = create_ready_application(client)
    fake_result = InspectionResult(
        final_url="https://apply.safe-foundation.org/start",
        final_domain="apply.safe-foundation.org",
        redirect_chain=["https://apply.safe-foundation.org/start"],
        page_title="Safe Foundation Application",
        response_status=200,
        page_content_hash="a" * 64,
        fields=[
            raw_field(label="Cumulative GPA"),
            raw_field(
                ordinal=1,
                tag_name="textarea",
                input_type="textarea",
                label="Personal statement",
            ),
        ],
        barriers=["essay"],
        blocked_requests=[],
    )
    monkeypatch.setattr(
        "app.routes.inspections.inspect_application_page", lambda url: fake_result
    )
    response = client.post(f"/api/applications/{application['id']}/inspect")
    assert response.status_code == 200
    run = response.json()
    assert run["status"] == "completed"
    assert run["automatable_field_count"] == 1
    assert run["automatable_percent"] == 50.0
    assert run["detected_barriers"] == ["essay"]
    assert all("value" not in field for field in run["fields"])

    detail = client.get(f"/api/applications/{application['id']}").json()
    assert detail["status"] == "needs_essay"
    assert detail["latest_inspection"]["id"] == run["id"]
    assert any(task["category"] == "essay" for task in detail["tasks"])


def test_emergency_stop_prevents_browser_launch(client, monkeypatch):
    application = create_ready_application(client)
    called = False

    def should_not_run(url):
        nonlocal called
        called = True
        raise AssertionError("browser should not launch")

    monkeypatch.setattr("app.routes.inspections.inspect_application_page", should_not_run)
    client.post("/api/system/emergency-stop")
    response = client.post(f"/api/applications/{application['id']}/inspect")
    assert response.status_code == 409
    assert "Emergency stop" in response.json()["detail"]
    assert called is False


def test_blocked_inspection_is_audited_and_queued(client, monkeypatch):
    application = create_ready_application(client)

    def blocked(url):
        raise BrowserInspectionError(
            "cross_domain_redirect",
            "The application requested a hostname that has not been approved",
            [
                {
                    "url": "https://different.example.net/apply",
                    "category": "cross_domain_redirect",
                    "reason": "The application requested a hostname that has not been approved",
                }
            ],
        )

    monkeypatch.setattr("app.routes.inspections.inspect_application_page", blocked)
    response = client.post(f"/api/applications/{application['id']}/inspect")
    assert response.status_code == 200
    run = response.json()
    assert run["status"] == "blocked"
    assert run["error_category"] == "cross_domain_redirect"
    assert run["blocked_requests"][0]["url"] == "https://different.example.net/apply"

    detail = client.get(f"/api/applications/{application['id']}").json()
    assert detail["status"] == "needs_review"
    assert any(task["category"] == "application_error" for task in detail["tasks"])
