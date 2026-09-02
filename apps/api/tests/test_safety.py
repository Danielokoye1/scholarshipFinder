def test_dashboard_starts_with_real_empty_metrics(client):
    response = client.get("/api/dashboard")
    assert response.status_code == 200
    data = response.json()
    assert data["metrics"] == {
        "applications_submitted": 0,
        "potential_awards_cents": 0,
        "applications_this_week": 0,
        "need_attention": 0,
        "awaiting_decision": 0,
        "awards_won": 0,
        "total_won_cents": 0,
    }
    assert data["settings"]["operating_mode"] == "discovery_only"
    assert data["settings"]["automatic_submission_enabled"] is False


def test_unknown_profile_value_is_rejected(client):
    response = client.put(
        "/api/profile/education.gpa",
        json={"value": 3.42, "status": "unknown", "source": None},
    )
    assert response.status_code == 422


def test_verified_profile_value_requires_provenance(client):
    response = client.put(
        "/api/profile/education.gpa",
        json={"value": 3.42, "status": "verified", "source": None},
    )
    assert response.status_code == 422


def test_autonomous_mode_is_safety_gated(client):
    response = client.patch("/api/system/settings", json={"operating_mode": "autonomous"})
    assert response.status_code == 409


def test_automatic_submission_is_safety_gated(client):
    response = client.patch("/api/system/settings", json={"automatic_submission_enabled": True})
    assert response.status_code == 409


def test_emergency_stop_disables_all_activity(client):
    client.patch(
        "/api/system/settings",
        json={
            "discovery_enabled": True,
            "eligibility_enabled": True,
            "preparation_enabled": True,
            "email_monitoring_enabled": True,
        },
    )
    response = client.post("/api/system/emergency-stop")
    assert response.status_code == 200
    data = response.json()
    assert data["automation_status"] == "stopped"
    assert data["emergency_stop"] is True
    assert data["discovery_enabled"] is False
    assert data["eligibility_enabled"] is False
    assert data["preparation_enabled"] is False
    assert data["automatic_submission_enabled"] is False
    assert data["email_monitoring_enabled"] is False


def test_emergency_stop_must_be_cleared_before_resume(client):
    client.post("/api/system/emergency-stop")
    response = client.post("/api/system/resume")
    assert response.status_code == 409


def test_hostile_web_origin_cannot_write_to_local_api(client):
    response = client.post(
        "/api/system/emergency-stop",
        headers={"origin": "https://malicious.example"},
    )
    assert response.status_code == 403
    assert "Cross-origin writes" in response.json()["detail"]


def test_configured_local_web_origin_can_write(client):
    response = client.post(
        "/api/system/pause",
        headers={"origin": "http://127.0.0.1:3217"},
    )
    assert response.status_code == 200


def test_untrusted_host_header_is_rejected(client):
    response = client.get("/health", headers={"host": "attacker.example"})
    assert response.status_code == 400
