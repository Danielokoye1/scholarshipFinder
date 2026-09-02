from collections.abc import Generator
import os
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import settings


class Base(DeclarativeBase):
    pass


database_path: Path | None = None
if settings.database_url.startswith("sqlite:///"):
    configured_path = settings.database_url.removeprefix("sqlite:///")
    if configured_path != ":memory:":
        database_path = Path(configured_path).resolve()
        database_path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        os.chmod(database_path.parent, 0o700)

for private_directory in (
    settings.document_storage_path.resolve(),
    settings.screenshot_storage_path.resolve(),
):
    private_directory.mkdir(parents=True, exist_ok=True, mode=0o700)
    os.chmod(private_directory, 0o700)

engine = create_engine(
    settings.database_url,
    connect_args={"check_same_thread": False} if settings.database_url.startswith("sqlite") else {},
)
if database_path is not None:
    with engine.connect():
        pass
    os.chmod(database_path, 0o600)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def get_db() -> Generator[Session, None, None]:
    with SessionLocal() as session:
        yield session
