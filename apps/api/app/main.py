from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.attendance import router as attendance_router
from app.api.v1.auth import router as auth_router
from app.api.v1.cases import router as cases_router
from app.api.v1.classes import router as classes_router
from app.api.v1.geo import router as geo_router
from app.api.v1.health import router as health_router
from app.api.v1.mentors import router as mentors_router
from app.api.v1.sms_webhook import router as sms_webhook_router
from app.api.v1.students import router as students_router
from app.api.v1.users import router as users_router
from app.api.v1.ussd_webhook import router as ussd_router
from app.api.v1.ussd_webhook import ussd_callback
from app.core.config import settings
from app.core.logging import setup_logging
from app.jobs.scheduler import shutdown_scheduler, start_scheduler


@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_logging()
    start_scheduler()
    try:
        yield
    finally:
        shutdown_scheduler()


app = FastAPI(
    title="Garuka API",
    description="Dropout early-warning and attendance monitoring API",
    version="0.1.0",
    lifespan=lifespan,
    openapi_url="/openapi.json",
    docs_url="/docs",
    redoc_url="/redoc",
)

# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Canonical API v1 endpoints
app.include_router(health_router, prefix="/api/v1")
app.include_router(auth_router, prefix="/api/v1")
app.include_router(geo_router, prefix="/api/v1")
app.include_router(users_router, prefix="/api/v1")
app.include_router(classes_router, prefix="/api/v1")
app.include_router(students_router, prefix="/api/v1")
app.include_router(attendance_router, prefix="/api/v1")
app.include_router(cases_router, prefix="/api/v1")
app.include_router(mentors_router, prefix="/api/v1")
app.include_router(sms_webhook_router, prefix="/api/v1")
app.include_router(ussd_router, prefix="/api/v1")


# Convenience root endpoints
@app.get("/health", include_in_schema=False)
async def root_health():
    from app.api.v1.health import health_check

    return await health_check()


# Alias for Africa's Talking webhook without /api/v1
app.add_api_route(
    "/ussd/{secret}",
    ussd_callback,
    methods=["POST"],
    include_in_schema=False,
)
