import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import PlainTextResponse

from app.api.v1.admin import router as admin_router
from app.api.v1.analytics import router as analytics_router
from app.api.v1.attendance import router as attendance_router
from app.api.v1.auth import router as auth_router
from app.api.v1.cases import router as cases_router
from app.api.v1.classes import router as classes_router
from app.api.v1.geo import router as geo_router
from app.api.v1.health import router as health_router
from app.api.v1.help_requests import router as help_requests_router
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

logger = logging.getLogger("garuka.app")

# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def ussd_always_200_middleware(request: Request, call_next):
    path = request.url.path
    is_ussd = (
        path.startswith("/ussd/")
        or path.startswith("/api/v1/ussd/")
        or (path in ("/dev/ussd", "/api/v1/dev/ussd") and settings.APP_ENV != "production")
    )
    if not is_ussd:
        return await call_next(request)

    try:
        response = await call_next(request)
        # Any 4xx/5xx error on USSD route (e.g. dependency failure, 422 validation, 500)
        # must be converted to HTTP 200 text/plain with END Service temporarily unavailable
        if response.status_code >= 400:
            logger.warning(
                "USSD route %s produced status %d, converting to 200 PlainText",
                path,
                response.status_code,
            )
            return PlainTextResponse(
                "END Service temporarily unavailable. Please try again.",
                status_code=200,
                media_type="text/plain; charset=utf-8",
            )
        return response
    except Exception as exc:
        logger.exception("USSD middleware trapped escaping exception on %s: %s", path, exc)
        return PlainTextResponse(
            "END Service temporarily unavailable. Please try again.",
            status_code=200,
            media_type="text/plain; charset=utf-8",
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
app.include_router(help_requests_router, prefix="/api/v1")
app.include_router(mentors_router, prefix="/api/v1")
app.include_router(analytics_router, prefix="/api/v1")
app.include_router(admin_router, prefix="/api/v1")
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
