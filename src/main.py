"""Production FastAPI application entrypoint."""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.api.exception_handlers import register_exception_handlers
from src.api.routers import (
    auth,
    billing,
    encounters,
    feedback,
    hospitals,
    patients,
    prescriptions,
    queues,
    staff,
    triage,
)
from src.db.session import engine
from src.schemas.common import HealthResponse
from src.settings import get_settings

settings = get_settings()


@asynccontextmanager
async def lifespan(_app: FastAPI):
    yield
    await engine.dispose()


app = FastAPI(
    title=settings.app_name,
    version="1.0.0",
    docs_url="/docs" if settings.app_env != "production" else None,
    redoc_url=None,
    lifespan=lifespan,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH"],
    allow_headers=["Authorization", "Content-Type", "X-Request-ID"],
)
register_exception_handlers(app)

for router in (
    auth.router,
    hospitals.router,
    staff.router,
    patients.router,
    queues.router,
    encounters.router,
    triage.router,
    prescriptions.router,
    billing.router,
    feedback.router,
):
    app.include_router(router, prefix=settings.api_v1_prefix)


@app.get("/health", response_model=HealthResponse, tags=["system"])
async def health() -> HealthResponse:
    return HealthResponse(status="ok", service=settings.app_name, environment=settings.app_env)
