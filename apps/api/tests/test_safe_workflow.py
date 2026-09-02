from copy import deepcopy


def scholarship_payload(**overrides):
    payload = {
        "name": "Safe Future Scholarship",
        "provider": "Community Education Foundation",
        "source_url": "https://directory.example.org/safe-future",
        "application_url": "https://apply.safe-foundation.org/start",
        "description": "Support for current college students.",
        "award_max_cents": 500_000,
        "raw_deadline_text": "March 4, 2027 at 5:00 PM ET",
        "deadline": "2027-03-04T17:00:00-05:00",
        "deadline_type": "fixed",
        "requirements": {"application_form": True},
        "source_text": "Applicants must have a cumulative GPA of 3.0 or higher.",
        "source_adapter": "manual",
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
    payload.update(overrides)
    return payload


def set_gpa(client, value=3.5):
    return client.put(
        "/api/profile/education.gpa",
        json={"value": value, "status": "verified", "source": "User-reviewed transcript"},
    )


def ingest(client, **overrides):
    return client.post("/api/scholarships/ingest", json=scholarship_payload(**overrides))


def approve_domain(client, domain="apply.safe-foundation.org"):
    return client.put(
        "/api/safety/domains",
        json={
            "domain": domain,
            "decision": "approved",
            "notes": "Reviewed locally against the provider's official information.",
        },
    )


def test_new_https_domain_defaults_to_review_and_is_explained(client):
    result = ingest(client).json()
    detail = client.get(f"/api/scholarships/{result['scholarship_id']}").json()
    assessment = client.get(
        f"/api/safety/scholarships/{result['scholarship_id']}"
    ).json()

    assert detail["safety_status"] == "review_required"
    assert assessment["status"] == "review_required"
    assert assessment["application_domain"] == "apply.safe-foundation.org"
    assert "The application domain has not been manually approved" in assessment["reasons"]


def test_listing_url_never_substitutes_for_missing_application_destination(client):
    result = ingest(client, application_url=None).json()
    assert approve_domain(client, "directory.example.org").status_code == 200
    assessment = client.post(
        f"/api/safety/scholarships/{result['scholarship_id']}/assess"
    ).json()

    assert assessment["status"] == "review_required"
    assert assessment["application_domain"] is None
    assert "No distinct application URL has been verified" in assessment["reasons"]


def test_insecure_and_direct_ip_application_destinations_are_blocked(client):
    insecure = ingest(
        client,
        name="Insecure Scholarship",
        source_url="https://directory.example.org/insecure",
        application_url="http://apply.insecure.example/start",
    ).json()
    insecure_assessment = client.get(
        f"/api/safety/scholarships/{insecure['scholarship_id']}"
    ).json()
    assert insecure_assessment["status"] == "blocked"
    assert "The application endpoint does not use HTTPS" in insecure_assessment["reasons"]

    direct_ip = ingest(
        client,
        name="IP Scholarship",
        source_url="https://directory.example.org/ip",
        application_url="https://192.0.2.10/apply",
    ).json()
    ip_assessment = client.get(
        f"/api/safety/scholarships/{direct_ip['scholarship_id']}"
    ).json()
    assert ip_assessment["status"] == "blocked"
    assert "Direct IP-address application endpoints are not allowed" in ip_assessment["reasons"]

    ipv6 = ingest(
        client,
        name="IPv6 Scholarship",
        source_url="https://directory.example.org/ipv6",
        application_url="https://[2001:db8::1]/apply",
    ).json()
    ipv6_assessment = client.get(
        f"/api/safety/scholarships/{ipv6['scholarship_id']}"
    ).json()
    assert ipv6_assessment["status"] == "blocked"
    assert "Direct IP-address application endpoints are not allowed" in ipv6_assessment["reasons"]


def test_sensitive_requirements_override_domain_approval(client):
    assert approve_domain(client).status_code == 200
    review = ingest(client, requirements={"social_security_number": True}).json()
    review_assessment = client.get(
        f"/api/safety/scholarships/{review['scholarship_id']}"
    ).json()
    assert review_assessment["status"] == "review_required"
    assert any("social_security_number" in reason for reason in review_assessment["reasons"])

    blocked = ingest(
        client,
        name="Fee Scholarship",
        source_url="https://directory.example.org/fee",
        application_url="https://fees.safe-foundation.org/start",
        requirements={"application_fee": True},
    ).json()
    blocked_assessment = client.get(
        f"/api/safety/scholarships/{blocked['scholarship_id']}"
    ).json()
    assert blocked_assessment["status"] == "blocked"
    assert any("application_fee" in reason for reason in blocked_assessment["reasons"])


def test_approved_domain_enables_workflow_but_phase_four_blocks_data_entry(client):
    assert set_gpa(client).status_code == 200
    assert approve_domain(client).status_code == 200
    scholarship = ingest(client).json()
    detail = client.get(f"/api/scholarships/{scholarship['scholarship_id']}").json()
    assert detail["safety_status"] == "approved"

    created = client.post(
        "/api/applications", json={"scholarship_id": scholarship["scholarship_id"]}
    )
    assert created.status_code == 201
    application = created.json()
    assert application["status"] == "ready_to_apply"
    assert application["safety_status"] == "approved"

    transition = client.post(
        f"/api/applications/{application['id']}/transition",
        json={
            "to_status": "application_started",
            "reason": "Attempt to begin form preparation",
            "expected_version": application["version"],
        },
    )
    assert transition.status_code == 409
    assert "disabled in Phase 4" in transition.json()["detail"]


def test_unapproved_domain_creates_a_safety_task_then_explicit_reassessment_clears_it(client):
    assert set_gpa(client).status_code == 200
    scholarship = ingest(client).json()
    created = client.post(
        "/api/applications", json={"scholarship_id": scholarship["scholarship_id"]}
    ).json()

    assert created["status"] == "needs_review"
    assert created["safety_status"] == "review_required"
    assert [task["category"] for task in created["tasks"]] == ["safety_review"]
    assert client.get("/api/tasks").json()[0]["id"] == created["tasks"][0]["id"]

    assert approve_domain(client).status_code == 200
    reassessed = client.post(
        f"/api/applications/{created['id']}/reassess-safety"
    ).json()
    assert reassessed["status"] == "ready_to_apply"
    assert reassessed["safety_status"] == "approved"
    assert reassessed["tasks"][0]["status"] == "resolved"
    assert client.get("/api/tasks").json() == []


def test_unknown_and_failed_eligibility_have_distinct_terminal_workflow_states(client):
    unknown_scholarship = ingest(client).json()
    unknown = client.post(
        "/api/applications", json={"scholarship_id": unknown_scholarship["scholarship_id"]}
    ).json()
    assert unknown["status"] == "needs_user_input"
    assert unknown["tasks"][0]["category"] == "verify_information"

    assert set_gpa(client, 2.0).status_code == 200
    failed_payload = deepcopy(scholarship_payload())
    failed_payload.update(
        {
            "name": "High GPA Scholarship",
            "source_url": "https://directory.example.org/high-gpa",
            "application_url": "https://apply.high-gpa.example/start",
        }
    )
    failed_scholarship = client.post("/api/scholarships/ingest", json=failed_payload).json()
    failed = client.post(
        "/api/applications", json={"scholarship_id": failed_scholarship["scholarship_id"]}
    ).json()
    assert failed["status"] == "ineligible"


def test_transition_uses_optimistic_version_guard(client):
    assert set_gpa(client).status_code == 200
    scholarship = ingest(client).json()
    application = client.post(
        "/api/applications", json={"scholarship_id": scholarship["scholarship_id"]}
    ).json()
    response = client.post(
        f"/api/applications/{application['id']}/transition",
        json={
            "to_status": "cancelled",
            "reason": "No longer pursuing this opportunity",
            "expected_version": application["version"] - 1,
        },
    )
    assert response.status_code == 409
    assert "changed since it was loaded" in response.json()["detail"]


def test_blocklist_and_priority_settings_are_local_and_persistent(client):
    blocked_policy = client.put(
        "/api/safety/domains",
        json={
            "domain": "apply.safe-foundation.org",
            "decision": "blocked",
            "notes": "Local owner decided this destination is unsafe.",
        },
    )
    assert blocked_policy.status_code == 200
    scholarship = ingest(client).json()
    assessment = client.get(
        f"/api/safety/scholarships/{scholarship['scholarship_id']}"
    ).json()
    assert assessment["status"] == "blocked"

    settings = client.get("/api/priority/settings").json()
    settings["award_weight"] = 0.4
    settings.pop("updated_at")
    updated = client.put("/api/priority/settings", json=settings)
    assert updated.status_code == 200
    assert updated.json()["award_weight"] == 0.4
    assert client.post("/api/priority/recalculate").json() == {"recalculated": 1}
