from copy import deepcopy


def scholarship_payload(**overrides):
    payload = {
        "name": "Future Engineers Scholarship",
        "provider": "Engineering Foundation",
        "source_url": "https://www.example.org/scholarships/future-engineers?utm_source=test",
        "application_url": "https://apply.example.org/future-engineers/",
        "description": "Support for undergraduate engineering students.",
        "award_min_cents": 100000,
        "award_max_cents": 500000,
        "award_description": "$1,000–$5,000",
        "raw_deadline_text": "March 4, 2027 at 5:00 PM ET",
        "deadline": "2027-03-04T17:00:00-05:00",
        "deadline_type": "fixed",
        "requirements": {"application_form": True, "essay": False},
        "source_text": (
            "Applicants must have a cumulative GPA of 3.0 or higher. "
            "Applicants must major in engineering."
        ),
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
            },
            {
                "requirement": "Applicant must major in engineering",
                "field_key": "education.major",
                "operator": "contains_any",
                "expected_value": ["engineering"],
                "confidence": 0.98,
                "needs_review": False,
                "source_quote": "Applicants must major in engineering.",
            },
        ],
    }
    payload.update(overrides)
    return payload


def set_profile(client, key, value, status="verified"):
    return client.put(
        f"/api/profile/{key}",
        json={"value": value, "status": status, "source": "User-reviewed profile"},
    )


def test_ingestion_normalizes_urls_and_evaluates_verified_profile(client):
    assert set_profile(client, "education.gpa", 3.42).status_code == 200
    assert set_profile(client, "education.major", "Electrical Engineering").status_code == 200

    response = client.post("/api/scholarships/ingest", json=scholarship_payload())
    assert response.status_code == 201
    result = response.json()
    assert result["created"] is True
    assert result["eligibility_status"] == "eligible"
    assert result["legitimacy_status"] == "likely_legitimate"

    detail = client.get(f"/api/scholarships/{result['scholarship_id']}").json()
    assert detail["source_url"] == "https://example.org/scholarships/future-engineers"
    assert detail["application_url"] == "https://apply.example.org/future-engineers"
    assert detail["deadline_timezone"] == "-05:00"
    assert detail["eligibility_score"] == 1.0
    assert [check["result"] for check in detail["checks"]] == ["pass", "pass"]
    assert detail["rules"][0]["source_quote"].startswith("Applicants must have")


def test_exact_url_duplicate_is_linked_not_recreated(client):
    first = client.post("/api/scholarships/ingest", json=scholarship_payload()).json()
    duplicate_payload = scholarship_payload(
        source_url="https://example.org/scholarships/future-engineers/",
        application_url=None,
    )
    response = client.post("/api/scholarships/ingest", json=duplicate_payload)
    assert response.status_code == 200
    duplicate = response.json()
    assert duplicate["created"] is False
    assert duplicate["scholarship_id"] == first["scholarship_id"]
    assert duplicate["duplicate_reason"] == "canonical_url"
    assert client.get("/api/scholarships").json()["total"] == 1


def test_duplicate_source_can_enrich_a_missing_application_destination(client):
    first = client.post(
        "/api/scholarships/ingest",
        json=scholarship_payload(application_url=None),
    ).json()
    destination = "https://apply.example.org/future-engineers"

    duplicate = client.post(
        "/api/scholarships/ingest",
        json=scholarship_payload(application_url=destination),
    )

    assert duplicate.status_code == 200
    detail = client.get(f"/api/scholarships/{first['scholarship_id']}").json()
    assert detail["application_url"] == destination


def test_duplicate_source_does_not_replace_a_conflicting_destination(client):
    first = client.post("/api/scholarships/ingest", json=scholarship_payload()).json()

    duplicate = client.post(
        "/api/scholarships/ingest",
        json=scholarship_payload(application_url="https://different.example.org/apply"),
    )

    assert duplicate.status_code == 200
    detail = client.get(f"/api/scholarships/{first['scholarship_id']}").json()
    assert detail["application_url"] == "https://apply.example.org/future-engineers"


def test_application_route_fragment_is_preserved_and_can_enrich_a_portal_url(client):
    first = client.post(
        "/api/scholarships/ingest",
        json=scholarship_payload(application_url="https://portal.example.org/"),
    ).json()
    routed_url = "https://portal.example.org/#competition/2025940"

    duplicate = client.post(
        "/api/scholarships/ingest",
        json=scholarship_payload(application_url=routed_url),
    )

    assert duplicate.status_code == 200
    detail = client.get(f"/api/scholarships/{first['scholarship_id']}").json()
    assert detail["application_url"] == routed_url


def test_destination_enrichment_updates_open_workflow_task_link(client):
    first = client.post(
        "/api/scholarships/ingest",
        json=scholarship_payload(application_url=None),
    ).json()
    application = client.post(
        "/api/applications",
        json={"scholarship_id": first["scholarship_id"]},
    ).json()
    assert application["tasks"][0]["direct_url"] == "https://example.org/scholarships/future-engineers"
    routed_url = "https://portal.example.org/#competition/2025940"

    client.post(
        "/api/scholarships/ingest",
        json=scholarship_payload(application_url=routed_url),
    )

    refreshed = client.get(f"/api/applications/{application['id']}").json()
    assert refreshed["tasks"][0]["direct_url"] == routed_url


def test_same_provider_and_equivalent_title_are_detected_across_directories(client):
    first = client.post("/api/scholarships/ingest", json=scholarship_payload()).json()
    second_payload = scholarship_payload(
        name="Scholarship for Future Engineers",
        source_url="https://directory.example.net/listing/8291",
        application_url="https://other-portal.example.net/apply/8291",
    )
    response = client.post("/api/scholarships/ingest", json=second_payload)
    assert response.status_code == 200
    result = response.json()
    assert result["created"] is False
    assert result["scholarship_id"] == first["scholarship_id"]
    assert result["duplicate_reason"] == "provider_and_title_similarity"


def test_equivalent_deadline_offsets_share_an_identity_fingerprint(client):
    first = client.post("/api/scholarships/ingest", json=scholarship_payload()).json()
    payload = scholarship_payload(
        source_url="https://directory.example.net/future-engineers",
        application_url="https://directory.example.net/future-engineers/apply",
        raw_deadline_text="March 4, 2027 at 10:00 PM UTC",
        deadline="2027-03-04T22:00:00+00:00",
    )
    response = client.post("/api/scholarships/ingest", json=payload)
    assert response.status_code == 200
    assert response.json()["scholarship_id"] == first["scholarship_id"]
    assert response.json()["duplicate_reason"] == "identity_fingerprint"


def test_failed_rule_makes_scholarship_ineligible(client):
    assert set_profile(client, "education.gpa", 2.75).status_code == 200
    assert set_profile(client, "education.major", "Electrical Engineering").status_code == 200
    result = client.post("/api/scholarships/ingest", json=scholarship_payload()).json()
    assert result["eligibility_status"] == "ineligible"
    detail = client.get(f"/api/scholarships/{result['scholarship_id']}").json()
    assert [check["result"] for check in detail["checks"]] == ["fail", "pass"]


def test_missing_profile_value_never_becomes_a_pass(client):
    result = client.post("/api/scholarships/ingest", json=scholarship_payload()).json()
    assert result["eligibility_status"] == "needs_information"
    detail = client.get(f"/api/scholarships/{result['scholarship_id']}").json()
    assert {check["result"] for check in detail["checks"]} == {"unknown"}


def test_low_confidence_rule_requires_verification_even_with_profile_data(client):
    assert set_profile(client, "education.gpa", 4.0).status_code == 200
    payload = scholarship_payload()
    payload["rules"] = [deepcopy(payload["rules"][0])]
    payload["rules"][0]["confidence"] = 0.6
    result = client.post("/api/scholarships/ingest", json=payload).json()
    detail = client.get(f"/api/scholarships/{result['scholarship_id']}").json()
    assert result["eligibility_status"] == "needs_information"
    assert detail["checks"][0]["result"] == "needs_verification"


def test_suspicious_payment_language_blocks_scholarship(client):
    payload = scholarship_payload(
        source_text="Applicants are required to pay a processing fee before receiving scholarship funds.",
        rules=[],
    )
    result = client.post("/api/scholarships/ingest", json=payload).json()
    assert result["legitimacy_status"] == "blocked"
    detail = client.get(f"/api/scholarships/{result['scholarship_id']}").json()
    assert "Processing fee required" in detail["legitimacy_signals"]


def test_no_fee_statement_is_not_misclassified_as_a_payment_request(client):
    payload = scholarship_payload(
        source_text="There is no application fee. Applying is completely free.",
        rules=[],
    )
    result = client.post("/api/scholarships/ingest", json=payload).json()
    assert result["legitimacy_status"] == "likely_legitimate"


def test_rule_quote_must_be_grounded_in_captured_source(client):
    payload = scholarship_payload()
    payload["rules"][0]["source_quote"] = "This sentence was not on the source page."
    response = client.post("/api/scholarships/ingest", json=payload)
    assert response.status_code == 422
    assert "was not found in source_text" in response.json()["detail"]
    assert client.get("/api/scholarships").json()["total"] == 0


def test_normalized_deadline_requires_timezone_and_raw_text(client):
    response = client.post(
        "/api/scholarships/ingest",
        json=scholarship_payload(deadline="2027-03-04T17:00:00"),
    )
    assert response.status_code == 422


def test_reevaluation_uses_updated_profile_but_preserves_previous_snapshot_only_until_rerun(client):
    result = client.post("/api/scholarships/ingest", json=scholarship_payload()).json()
    scholarship_id = result["scholarship_id"]
    assert result["eligibility_status"] == "needs_information"

    assert set_profile(client, "education.gpa", 3.5).status_code == 200
    assert set_profile(client, "education.major", "Mechanical Engineering").status_code == 200
    reevaluated = client.post(f"/api/scholarships/{scholarship_id}/evaluate")
    assert reevaluated.status_code == 200
    assert reevaluated.json()["eligibility_status"] == "eligible"
    assert [check["profile_value"] for check in reevaluated.json()["checks"]] == [
        3.5,
        "Mechanical Engineering",
    ]
    history = client.get(f"/api/scholarships/{scholarship_id}/eligibility-history").json()
    assert len(history) == 4
    assert sum(check["is_current"] for check in history) == 2
    assert {check["profile_value"] for check in history if not check["is_current"]} == {None}


def test_batch_reevaluation_reports_conservative_status_counts(client):
    first = client.post("/api/scholarships/ingest", json=scholarship_payload()).json()
    second_payload = scholarship_payload(
        name="Community Service Award",
        provider="Community Foundation",
        source_url="https://community.example.com/service-award",
        application_url=None,
    )
    second = client.post("/api/scholarships/ingest", json=second_payload).json()
    assert first["scholarship_id"] != second["scholarship_id"]
    response = client.post("/api/scholarships/evaluate-all")
    assert response.status_code == 200
    assert response.json() == {
        "evaluated": 2,
        "eligible": 0,
        "ineligible": 0,
        "needs_information": 2,
    }
