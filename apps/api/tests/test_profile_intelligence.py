from app.core.profile_intelligence import LocalDocumentText, read_local_document
from app.models import Document


def field_from_overview(body: dict, field_key: str) -> dict:
    return next(
        field
        for section in body["sections"]
        for field in section["fields"]
        if field["field_key"] == field_key
    )


def test_profile_overview_saves_multiple_inputs_and_derives_context(client):
    response = client.put(
        "/api/profile/overview",
        json={
            "items": [
                {
                    "field_key": "identity.first_name",
                    "value": "  Ada  ",
                    "status": "verified",
                    "source": "Government ID reviewed locally",
                },
                {
                    "field_key": "identity.last_name",
                    "value": "Lovelace",
                    "status": "verified",
                    "source": "Government ID reviewed locally",
                },
                {
                    "field_key": "education.graduation_date",
                    "value": "Fall 2028",
                    "status": "verified",
                    "source": "Resume reviewed locally",
                },
                {
                    "field_key": "education.class_year",
                    "value": "junior",
                    "status": "user_entered",
                    "source": "User confirmed",
                },
            ]
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert field_from_overview(body, "identity.first_name")["value"] == "Ada"
    assert field_from_overview(body, "education.class_year")["value"] == "Junior"
    assert body["external_address_verification"] == "not_performed"
    assert any(issue["code"] == "class_year_consistent" for issue in body["issues"])

    stored = client.get("/api/profile").json()
    by_key = {item["field_key"]: item for item in stored}
    assert by_key["identity.full_name"]["value"] == "Ada Lovelace"
    assert by_key["identity.full_name"]["status"] == "verified"
    assert by_key["education.graduation_year"]["value"] == 2028


def test_profile_normalizes_contact_and_address_fields(client):
    response = client.put(
        "/api/profile/overview",
        json={
            "items": [
                {
                    "field_key": "contact.email",
                    "value": " Student@Example.COM ",
                    "status": "user_entered",
                    "source": "User",
                },
                {
                    "field_key": "contact.phone",
                    "value": "+1 734 555 0100",
                    "status": "user_entered",
                    "source": "User",
                },
                {
                    "field_key": "address.state",
                    "value": "Michigan",
                    "status": "user_entered",
                    "source": "User",
                },
                {
                    "field_key": "identity.citizenship",
                    "value": "American Citizen",
                    "status": "verified",
                    "source": "User-reviewed document",
                },
            ]
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert field_from_overview(body, "contact.email")["value"] == "student@example.com"
    assert field_from_overview(body, "contact.phone")["value"] == "(734) 555-0100"
    assert field_from_overview(body, "address.state")["value"] == "MI"
    assert field_from_overview(body, "identity.citizenship")["value"] == "U.S. Citizen"


def test_profile_supports_scholarship_affiliation_context(client):
    response = client.put(
        "/api/profile/overview",
        json={
            "items": [
                {
                    "field_key": "affiliations.nsbe_membership",
                    "value": "unsure",
                    "status": "user_entered",
                    "source": "User",
                },
                {
                    "field_key": "affiliations.nsbe_region",
                    "value": "region 4",
                    "status": "user_entered",
                    "source": "User",
                },
            ]
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert field_from_overview(body, "affiliations.nsbe_membership")["value"] == "Unsure"
    assert field_from_overview(body, "affiliations.nsbe_region")["value"] == "Region 4"


def test_profile_keeps_self_identification_separate_from_citizenship(client):
    response = client.put(
        "/api/profile/overview",
        json={
            "items": [
                {
                    "field_key": "identity.national_origin",
                    "value": "Nigerian",
                    "status": "user_entered",
                    "source": "User confirmed",
                },
                {
                    "field_key": "identity.race_ethnicity",
                    "value": "African American",
                    "status": "user_entered",
                    "source": "User confirmed",
                },
            ]
        },
    )

    assert response.status_code == 200
    body = response.json()
    origin = field_from_overview(body, "identity.national_origin")
    identity = field_from_overview(body, "identity.race_ethnicity")
    assert origin["value"] == "Nigerian"
    assert origin["sensitive"] is True
    assert identity["value"] == "African American"
    assert identity["sensitive"] is True
    assert field_from_overview(body, "identity.citizenship")["value"] is None


def test_profile_rejects_ambiguous_enrollment_and_invalid_address(client):
    enrollment = client.put(
        "/api/profile/education.enrollment_status",
        json={"value": "True", "status": "user_entered", "source": "User"},
    )
    assert enrollment.status_code == 422
    assert "Full-time" in enrollment.json()["detail"]

    postal_code = client.put(
        "/api/profile/address.postal_code",
        json={"value": "not-a-zip", "status": "user_entered", "source": "User"},
    )
    assert postal_code.status_code == 422
    assert "ZIP" in postal_code.json()["detail"]


def test_profile_review_flags_address_stored_as_residency(client):
    response = client.put(
        "/api/profile/identity.residency",
        json={"value": "123 Example Street", "status": "user_entered", "source": "User"},
    )
    assert response.status_code == 200

    overview = client.get("/api/profile/overview").json()

    issue = next(item for item in overview["issues"] if item["code"] == "misplaced_address_in_residency")
    assert issue["severity"] == "error"
    assert issue["field_keys"] == ["identity.residency"]
    assert field_from_overview(overview, "identity.residency")["label"] == "Residency status (not your address)"


def test_profile_bulk_rejects_unknown_structured_fields(client):
    response = client.put(
        "/api/profile/overview",
        json={
            "items": [
                {
                    "field_key": "education.favorite_color",
                    "value": "green",
                    "status": "user_entered",
                    "source": "User",
                }
            ]
        },
    )

    assert response.status_code == 422
    assert "not a supported structured profile field" in response.json()["detail"]


def test_encrypted_pdf_is_not_decrypted_for_profile_intelligence(monkeypatch, tmp_path):
    document_path = tmp_path / "locked.pdf"
    document_path.write_bytes(b"%PDF locked fixture")
    document = Document(
        id="locked-document",
        original_filename="locked.pdf",
        stored_filename="locked.pdf",
        document_type="transcript",
        size_bytes=document_path.stat().st_size,
        sha256="a" * 64,
    )

    class EncryptedReader:
        is_encrypted = True

        def __init__(self, path):
            assert path == document_path

        def decrypt(self, password):
            raise AssertionError("Encrypted documents must not be decrypted")

    monkeypatch.setattr("app.core.profile_intelligence.settings.document_storage_path", tmp_path)
    monkeypatch.setattr("app.core.profile_intelligence.PdfReader", EncryptedReader)

    result = read_local_document(document)

    assert result.status == "locked"
    assert result.text == ""


def test_new_document_version_revokes_older_upload_approval(client):
    first = client.post(
        "/api/documents",
        files={"file": ("resume-v1.pdf", b"%PDF first", "application/pdf")},
        data={"document_type": "resume", "version": "1"},
    )
    assert first.status_code == 201
    approved = client.patch(
        f"/api/documents/{first.json()['id']}/approval",
        json={"auto_upload_allowed": True},
    )
    assert approved.status_code == 200

    second = client.post(
        "/api/documents",
        files={"file": ("resume-wn26.pdf", b"%PDF second", "application/pdf")},
        data={"document_type": "resume", "version": "WN26"},
    )
    assert second.status_code == 201
    assert second.json()["auto_upload_allowed"] is False

    documents = client.get("/api/documents").json()
    by_version = {item["version"]: item for item in documents}
    assert by_version["1"]["auto_upload_allowed"] is False
    assert by_version["WN26"]["auto_upload_allowed"] is False

    overview = client.get("/api/profile/overview").json()
    resume_checks = [
        item for item in overview["document_checks"] if item["document_type"] == "resume"
    ]
    assert next(item for item in resume_checks if item["version"] == "1")["is_latest"] is False
    assert next(item for item in resume_checks if item["version"] == "WN26")["is_latest"] is True


def test_profile_intelligence_uses_latest_resume_version(client, monkeypatch):
    for version in ("1", "WN26"):
        response = client.post(
            "/api/documents",
            files={"file": (f"resume-{version}.pdf", b"%PDF fixture", "application/pdf")},
            data={"document_type": "resume", "version": version},
        )
        assert response.status_code == 201
    profile = client.put(
        "/api/profile/education.graduation_date",
        json={"value": "Winter 2028", "status": "user_entered", "source": "User"},
    )
    assert profile.status_code == 200

    def document_text(document):
        term = "Fall" if document.version == "1" else "Winter"
        return LocalDocumentText(
            document=document,
            status="readable",
            text=f"Expected Graduation - {term} 2028",
            page_count=1,
        )

    monkeypatch.setattr("app.core.profile_intelligence.read_local_document", document_text)
    overview = client.get("/api/profile/overview").json()
    codes = {item["code"] for item in overview["issues"]}

    assert "graduation_corroborated" in codes
    assert "graduation_conflict" not in codes
