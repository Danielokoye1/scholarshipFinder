from datetime import UTC, datetime

from app.browser.dry_run import FillCandidate, execute_offline_dry_run
from app.browser.inspector import InspectionResult, RawFormField
from app.models import FormFieldPlan, ProfileField


def ready_application(client):
    client.put(
        "/api/profile/education.gpa",
        json={"value": 3.42, "status": "verified", "source": "User-reviewed transcript"},
    )
    client.put(
        "/api/safety/domains",
        json={
            "domain": "apply.phase-five.example",
            "decision": "approved",
            "notes": "Exact provider destination reviewed for the local dry-run test.",
        },
    )
    scholarship = client.post(
        "/api/scholarships/ingest",
        json={
            "name": "Phase Five Scholarship",
            "provider": "Fixture Foundation",
            "source_url": "https://directory.example/phase-five",
            "application_url": "https://apply.phase-five.example/start",
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
        },
    ).json()
    application = client.post(
        "/api/applications", json={"scholarship_id": scholarship["scholarship_id"]}
    ).json()
    client.patch(
        "/api/system/settings",
        json={"operating_mode": "dry_run", "preparation_enabled": True},
    )
    return application


def inspection_result(input_type="number"):
    return InspectionResult(
        final_url="https://apply.phase-five.example/start",
        final_domain="apply.phase-five.example",
        redirect_chain=["https://apply.phase-five.example/start"],
        page_title="Phase Five Application",
        response_status=200,
        page_content_hash="b" * 64,
        fields=[
            RawFormField(
                ordinal=0,
                form_index=0,
                tag_name="input" if input_type != "select" else "select",
                input_type=input_type,
                label="Cumulative GPA",
                required=True,
                disabled=False,
                autocomplete=None,
            )
        ],
        barriers=[],
        blocked_requests=[],
    )


def test_offline_engine_returns_hashes_without_profile_value():
    plan = FormFieldPlan(
        id="plan-1",
        browser_run_id="run-1",
        application_id="application-1",
        ordinal=0,
        form_index=0,
        tag_name="input",
        input_type="text",
        label="Secret verified answer",
        required=True,
        disabled=False,
        profile_field_key="identity.first_name",
        mapping_confidence=1.0,
        profile_status="verified",
        disposition="auto_answerable",
        reason="test",
    )
    profile = ProfileField(
        id=10,
        field_key="identity.first_name",
        value_json="NeverStoreThisValue",
        status="verified",
        source="User-reviewed profile",
        updated_at=datetime.now(UTC),
    )
    result = execute_offline_dry_run([FillCandidate(plan=plan, profile=profile)])
    assert len(result.manifest_hash) == 64
    assert len(result.fields[0].value_hash) == 64
    assert "NeverStoreThisValue" not in repr(result)


def test_dry_run_endpoint_is_offline_redacted_and_idempotent(client, monkeypatch):
    application = ready_application(client)
    monkeypatch.setattr(
        "app.routes.inspections.inspect_application_page",
        lambda url: inspection_result(),
    )
    inspection = client.post(f"/api/applications/{application['id']}/inspect")
    assert inspection.status_code == 200

    response = client.post(f"/api/applications/{application['id']}/dry-run-fill")
    assert response.status_code == 200
    run = response.json()
    assert run["status"] == "completed"
    assert run["execution_scope"] == "offline_synthetic"
    assert run["filled_field_count"] == 1
    assert run["fields"][0]["profile_field_key"] == "education.gpa"
    assert run["fields"][0]["profile_status"] == "verified"
    assert "value" not in run["fields"][0]
    assert "3.42" not in response.text

    repeated = client.post(f"/api/applications/{application['id']}/dry-run-fill")
    assert repeated.status_code == 200
    assert repeated.json()["id"] == run["id"]
    detail = client.get(f"/api/applications/{application['id']}").json()
    assert detail["latest_fill"]["id"] == run["id"]
    assert detail["completion_percent"] == 100.0


def test_dry_run_requires_explicit_mode_and_permission(client, monkeypatch):
    application = ready_application(client)
    monkeypatch.setattr(
        "app.routes.inspections.inspect_application_page",
        lambda url: inspection_result(),
    )
    client.post(f"/api/applications/{application['id']}/inspect")
    client.patch(
        "/api/system/settings",
        json={"operating_mode": "discovery_only", "preparation_enabled": False},
    )
    response = client.post(f"/api/applications/{application['id']}/dry-run-fill")
    assert response.status_code == 409
    assert "Dry Run" in response.json()["detail"]


def test_unsupported_required_control_is_blocked_and_queued(client, monkeypatch):
    application = ready_application(client)
    monkeypatch.setattr(
        "app.routes.inspections.inspect_application_page",
        lambda url: inspection_result("select"),
    )
    client.post(f"/api/applications/{application['id']}/inspect")
    response = client.post(f"/api/applications/{application['id']}/dry-run-fill")
    assert response.status_code == 200
    assert response.json()["status"] == "blocked"
    assert response.json()["errors"][0]["category"] == "unresolved_required_fields"
    detail = client.get(f"/api/applications/{application['id']}").json()
    assert detail["status"] == "needs_review"
    assert any(task["category"] == "field_mapping_review" for task in detail["tasks"])


def test_emergency_stop_blocks_offline_browser(client, monkeypatch):
    application = ready_application(client)
    monkeypatch.setattr(
        "app.routes.inspections.inspect_application_page",
        lambda url: inspection_result(),
    )
    client.post(f"/api/applications/{application['id']}/inspect")
    client.post("/api/system/emergency-stop")
    response = client.post(f"/api/applications/{application['id']}/dry-run-fill")
    assert response.status_code == 409
    assert "Emergency stop" in response.json()["detail"]
