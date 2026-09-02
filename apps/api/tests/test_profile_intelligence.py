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
            ]
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert field_from_overview(body, "contact.email")["value"] == "student@example.com"
    assert field_from_overview(body, "contact.phone")["value"] == "(734) 555-0100"
    assert field_from_overview(body, "address.state")["value"] == "MI"


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
    assert "address.street" in issue["field_keys"]
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
from app.core.profile_intelligence import read_local_document
from app.models import Document
