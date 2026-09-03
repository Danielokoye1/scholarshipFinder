from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.trustedhost import TrustedHostMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

from app.config import settings
from app.routes import (
    applications,
    dashboard,
    documents,
    filling,
    inspections,
    priority,
    profile,
    safety,
    scholarships,
    system,
    tasks,
    validation,
)


app = FastAPI(
    title="scholarshipFinder API",
    version="0.6.7",
    description="Private local workflow API with profile intelligence and immutable dry-run validation.",
)
allowed_origins = {settings.web_origin, "http://localhost:3217"}
app.add_middleware(
    TrustedHostMiddleware,
    allowed_hosts=["127.0.0.1", "localhost", "testserver"],
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=sorted(allowed_origins),
    allow_credentials=False,
    allow_methods=["GET", "POST", "PUT", "PATCH"],
    allow_headers=["Content-Type"],
)


@app.middleware("http")
async def reject_cross_origin_writes(request: Request, call_next):
    if request.method not in {"GET", "HEAD", "OPTIONS"}:
        origin = request.headers.get("origin")
        if origin is not None and origin not in allowed_origins:
            return JSONResponse(
                status_code=403,
                content={"detail": "Cross-origin writes to the local API are blocked"},
            )
    return await call_next(request)


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
app.include_router(validation.router)
app.include_router(tasks.router)
app.include_router(safety.router)
app.include_router(priority.router)
app.include_router(system.router)
