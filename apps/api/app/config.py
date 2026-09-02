from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str = "sqlite:///../../storage/database/scholarship_finder.db"
    document_storage_path: Path = Path("../../storage/documents")
    api_host: str = "127.0.0.1"
    api_port: int = 8217
    web_origin: str = "http://127.0.0.1:3217"
    max_document_bytes: int = 25 * 1024 * 1024
    eligibility_rule_confidence_threshold: float = 0.85
    duplicate_title_similarity_threshold: float = 0.86
    trusted_source_domains: str = ""

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
