from datetime import UTC, datetime, timedelta

import pytest

from app.browser.inspector import InspectionResult, RawFormField
from app.core.submission_validation import barrier_checks, deadline_check


def inspection_result():
    return InspectionResult(
        final_url="https://apply.phase-six.example/start",
        final_domain="apply.phase-six.example",
        redirect_chain=["https://apply.phase-six.example/start"],
        page_title="Phase Six Application",
        response_status=200,
        page_content_hash="c" * 64,
        fields=[
            RawFormField(
                ordinal=0,
                form_index=0,
                tag_name="input",
                input_type="number",
                label="Cumulative GPA",
                required=True,
                disabled=False,
                autocomplete=None,
            )
        ],
        barriers=[],
        blocked_requests=[],
    )


def prepared_candidate(client, monkeypatch, *, deadline=None, requirements=None):
    client.put(
        "/api/profile/education.gpa",
        json={"value": 3.42, "status": "verified", "source": "User-reviewed transcript"},
    )
    client.put(
        "/api/safety/domains",
        json={
            "domain": "apply.phase-six.example",
            "decision": "approved",
            "notes": "Exact provider destination independently reviewed for validation tests.",
        },
    )
    deadline = deadline or datetime.now(UTC) + timedelta(days=30)
    scholarship = client.post(
        "/api/scholarships/ingest",
        json={
            "name": "Phase Six Scholarship",
            "provider": "Fixture Foundation",
            "source_url": "https://directory.example/phase-six",
            "application_url": "https://apply.phase-six.example/start",
            "raw_deadline_text": deadline.strftime("%B %d, %Y"),
            "deadline": deadline.isoformat(),
            "deadline_type": "fixed",
            "requirements": requirements or {"application_form": True},
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
    monkeypatch.setattr(
        "app.routes.inspections.inspect_application_page",
        lambda url: inspection_result(),
    )
    assert client.post(f"/api/applications/{application['id']}/inspect").status_code == 200
    assert client.post(f"/api/applications/{application['id']}/dry-run-fill").status_code == 200
    return application


def upload_approved_document(client, name: str, content: bytes):
    uploaded = client.post(
        "/api/documents",
        files={"file": (name, content, "application/pdf")},
        data={"document_type": "transcript", "version": "1"},
    )
    assert uploaded.status_code == 201
    item = uploaded.json()
    assert client.patch(
        f"/api/documents/{item['id']}/approval",
        json={"auto_upload_allowed": True},
    ).status_code == 200
    return item


def test_pre_submission_validation_passes_without_enabling_submission(client, monkeypatch):
    application = prepared_candidate(client, monkeypatch)
    response = client.post(f"/api/applications/{application['id']}/validate-submission")
    assert response.status_code == 200
    snapshot = response.json()
    assert snapshot["status"] == "passed"
    assert snapshot["blockers"] == []
    assert len(snapshot["validation_manifest_hash"]) == 64
    assert "3.42" not in response.text
    assert any(check["code"] == "live_submission_lock" for check in snapshot["checks"])

    detail = client.get(f"/api/applications/{application['id']}").json()
    assert detail["status"] == "ready_to_apply"
    assert detail["submitted_at"] is None
    assert detail["latest_validation"]["id"] == snapshot["id"]
    assert client.post(f"/api/applications/{application['id']}/submit").status_code == 404


def test_profile_change_after_fill_blocks_validation(client, monkeypatch):
    application = prepared_candidate(client, monkeypatch)
    client.put(
        "/api/profile/education.gpa",
        json={"value": 3.5, "status": "verified", "source": "User-reviewed transcript"},
    )
    response = client.post(f"/api/applications/{application['id']}/validate-submission")
    assert response.status_code == 200
    snapshot = response.json()
    assert snapshot["status"] == "blocked"
    assert any(item["code"].startswith("profile_") for item in snapshot["blockers"])
    detail = client.get(f"/api/applications/{application['id']}").json()
    assert detail["status"] == "needs_review"
    assert any(task["category"] == "submission_validation" for task in detail["tasks"])


def test_expired_deadline_blocks_validation(client, monkeypatch):
    application = prepared_candidate(
        client,
        monkeypatch,
        deadline=datetime.now(UTC) - timedelta(days=1),
    )
    response = client.post(f"/api/applications/{application['id']}/validate-submission")
    assert response.status_code == 200
    assert any(item["code"] == "deadline_expired" for item in response.json()["blockers"])


def test_newer_changed_page_inspection_invalidates_fill(client, monkeypatch):
    application = prepared_candidate(client, monkeypatch)
    changed = inspection_result()
    changed = InspectionResult(
        final_url=changed.final_url,
        final_domain=changed.final_domain,
        redirect_chain=changed.redirect_chain,
        page_title=changed.page_title,
        response_status=changed.response_status,
        page_content_hash="d" * 64,
        fields=changed.fields,
        barriers=changed.barriers,
        blocked_requests=changed.blocked_requests,
    )
    monkeypatch.setattr(
        "app.routes.inspections.settings.inspection_min_interval_seconds",
        0,
    )
    monkeypatch.setattr(
        "app.routes.inspections.inspect_application_page",
        lambda url: changed,
    )
    assert client.post(f"/api/applications/{application['id']}/inspect").status_code == 200
    response = client.post(f"/api/applications/{application['id']}/validate-submission")
    assert response.status_code == 200
    codes = {item["code"] for item in response.json()["blockers"]}
    assert "inspection_changed" in codes
    assert "page_changed" in codes


def test_ambiguous_approved_documents_block_validation(client, monkeypatch):
    application = prepared_candidate(
        client,
        monkeypatch,
        requirements={"application_form": True, "transcript": True},
    )
    upload_approved_document(client, "transcript-one.pdf", b"fixture transcript one")
    upload_approved_document(client, "transcript-two.pdf", b"fixture transcript two")
    response = client.post(f"/api/applications/{application['id']}/validate-submission")
    assert response.status_code == 200
    assert any(
        item["code"] == "document_transcript_ambiguous"
        for item in response.json()["blockers"]
    )


@pytest.mark.parametrize(
    "barrier",
    [
        "captcha",
        "two_factor_authentication",
        "essay",
        "recommendation",
        "signature",
        "attestation",
        "file_upload",
        "unexpected_challenge",
    ],
)
def test_every_manual_barrier_is_a_submission_blocker(barrier):
    checks = barrier_checks([barrier])
    assert checks[0].status == "blocked"
    assert checks[0].code == f"barrier_{barrier}"


def test_unknown_and_expired_deadlines_are_blockers():
    assert deadline_check(None, "unknown").status == "blocked"
    assert deadline_check(None, "fixed").status == "blocked"
    assert deadline_check(datetime.now(UTC) - timedelta(seconds=1), "fixed").status == "blocked"
