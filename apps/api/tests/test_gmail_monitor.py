from app.gmail_monitor import GMAIL_METADATA_SCOPE, classify_subject, header_value


def test_subject_classification_is_conservative():
    assert classify_subject("Congratulations — scholarship recipient") == ("awarded", True)
    assert classify_subject("Action required: missing information") == ("action_required", True)
    assert classify_subject("Application received") == ("acknowledged", False)
    assert classify_subject("September newsletter") == ("update", False)


def test_only_requested_headers_are_extracted():
    message = {
        "payload": {
            "headers": [
                {"name": "From", "value": "Awards Team <awards@example.org>"},
                {"name": "Subject", "value": "  Application   received  "},
            ]
        },
        "body": "must never be read",
    }

    assert header_value(message, "subject") == "Application received"
    assert header_value(message, "From") == "Awards Team <awards@example.org>"
    assert header_value(message, "Body") == ""


def test_email_status_reports_metadata_scope_without_exposing_credentials(client, monkeypatch, tmp_path):
    client_file = tmp_path / "client.json"
    token_file = tmp_path / "token.json"
    client_file.write_text("fixture", encoding="utf-8")
    monkeypatch.setattr("app.routes.email.settings.gmail_client_secret_path", client_file)
    monkeypatch.setattr("app.routes.email.settings.gmail_token_path", token_file)

    response = client.get("/api/email/status")

    assert response.status_code == 200
    assert response.json() == {
        "provider": "Gmail",
        "client_credentials_present": True,
        "authorization_token_present": False,
        "monitoring_enabled": False,
        "scope": GMAIL_METADATA_SCOPE,
        "messages_indexed": 0,
        "actionable_messages": 0,
        "last_sync_at": None,
    }


def test_email_monitoring_cannot_be_enabled_without_token(client, monkeypatch, tmp_path):
    monkeypatch.setattr("app.routes.system.settings.gmail_token_path", tmp_path / "missing.json")

    response = client.patch("/api/system/settings", json={"email_monitoring_enabled": True})

    assert response.status_code == 409
    assert "Connect" in response.json()["detail"]
