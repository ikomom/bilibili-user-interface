import logging

import sentry_sdk
from fastapi import FastAPI
from fastapi.routing import APIRoute
from sqlmodel import Session
from starlette.middleware.cors import CORSMiddleware

from app.api.main import api_router
from app.bilibili.scheduler import create_scheduler, init_scheduler
from app.core.config import settings
from app.core.db import engine

logger = logging.getLogger(__name__)


def custom_generate_unique_id(route: APIRoute) -> str:
    return f"{route.tags[0]}-{route.name}"


if settings.SENTRY_DSN and settings.ENVIRONMENT != "local":
    sentry_sdk.init(dsn=str(settings.SENTRY_DSN), enable_tracing=True)

app = FastAPI(
    title=settings.PROJECT_NAME,
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    generate_unique_id_function=custom_generate_unique_id,
)

# Set all CORS enabled origins
if settings.all_cors_origins:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.all_cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

app.include_router(api_router, prefix=settings.API_V1_STR)


scheduler = create_scheduler(
    str(settings.SQLALCHEMY_DATABASE_URI),
    settings.APSCHEDULER_TIMEZONE,
)


@app.on_event("startup")
async def startup_event() -> None:
    scheduler.start()
    with Session(engine) as session:
        init_scheduler(scheduler, session)
    logger.info("APScheduler 已启动")


@app.on_event("shutdown")
async def shutdown_event() -> None:
    scheduler.shutdown()
    logger.info("APScheduler 已停止")
