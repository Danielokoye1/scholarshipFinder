from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str = "sqlite:///../../storage/database/scholarship_finder.db"
    document_storage_path: Path = Path("../../storage/documents")
    screenshot_storage_path: Path = Path("../../storage/screenshots")
    gmail_client_secret_path: Path = Path("../../storage/secrets/gmail-oauth-client.json")
    gmail_token_path: Path = Path("../../storage/secrets/gmail-token.json")
    api_host: str = "127.0.0.1"
    api_port: int = 8217
    web_origin: str = "http://127.0.0.1:3217"
    max_document_bytes: int = 25 * 1024 * 1024
    eligibility_rule_confidence_threshold: float = 0.85
    duplicate_title_similarity_threshold: float = 0.86
    trusted_source_domains: str = ""
    inspection_timeout_ms: int = 15_000
    inspection_settle_ms: int = 750
    inspection_max_fields: int = 250
    inspection_max_requests: int = 200
    inspection_max_html_bytes: int = 5_000_000
    inspection_min_interval_seconds: int = 15
    field_mapping_confidence_threshold: float = 0.9
    browser_channel: str = "chrome"

    model_config = SettingsConfigDict(
        env_file=("../../.env", ".env"),
        env_file_encoding="utf-8",
        env_prefix="SCHOLARSHIP_FINDER_",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
