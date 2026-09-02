from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.routes import applications, dashboard, documents, filling, inspections, priority, profile, safety, scholarships, system, tasks


app = FastAPI(
    title="scholarshipFinder API",
    version="0.5.0",
    description="Private local workflow API with offline, provenance-backed dry-run filling.",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.web_origin, "http://localhost:3217"],
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
app.include_router(scholarships.router)
app.include_router(applications.router)
app.include_router(inspections.router)
app.include_router(filling.router)
app.include_router(tasks.router)
app.include_router(safety.router)
app.include_router(priority.router)
app.include_router(system.router)
