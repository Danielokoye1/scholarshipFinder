from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.routes import dashboard, documents, profile, system


app = FastAPI(
    title="scholarshipFinder API",
    version="0.1.0",
    description="Local-only API. This phase cannot submit scholarship applications.",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.web_origin, "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH"],
    allow_headers=["Content-Type"],
)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "mode": "local"}


app.include_router(dashboard.router)
app.include_router(profile.router)
app.include_router(documents.router)
app.include_router(system.router)
