import logging
from contextlib import asynccontextmanager

import sentry_sdk
from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
from apscheduler.schedulers.background import BackgroundScheduler
from fastapi import FastAPI
from fastapi.routing import APIRoute
from starlette.middleware.cors import CORSMiddleware

from app.api.main import api_router
from app.api.routes.forms import expunge_expired_packets_job
from app.api.routes.report import generate_and_save_report  # Import the logic function
from app.core.config import settings

logging.basicConfig(level=logging.DEBUG)
logging.getLogger('apscheduler').setLevel(logging.DEBUG)

def custom_generate_unique_id(route: APIRoute) -> str:
    return f"{route.tags[0]}-{route.name}"


if settings.SENTRY_DSN and settings.ENVIRONMENT != "local":
    sentry_sdk.init(dsn=str(settings.SENTRY_DSN), enable_tracing=True)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # 1. Define the persistent database storage
    # APScheduler will create its own table 'apscheduler_jobs' automatically
    jobstores = {
        'default': SQLAlchemyJobStore(url=str(settings.SQLALCHEMY_DATABASE_URI))
    }

    # 2. Initialize with the jobstore
    scheduler = BackgroundScheduler(jobstores=jobstores)
    scheduler.start()

    # 3. Check if the weekly report job is already in the Postgres table
    existing_report_job = scheduler.get_job('monday_report_job')

    if not existing_report_job:
    # 4. Only add it if it's missing (e.g., first-time deployment)
        scheduler.add_job(
            generate_and_save_report,
            trigger='cron',
            day_of_week='mon',
            hour=4,
            minute=0,
            id='monday_report_job', # Unique ID is required for persistence
            misfire_grace_time=None, # KEY: Run immediately if missed
            replace_existing=True,   # Update the job if logic changes
            coalesce=True            # Only run once if missed multiple times
        )
        logging.info("Weekly report job added to database.")
    else:
        logging.info("Weekly report job already exists in database. Preserving schedule for catch-up.")

    # 5. Check if 30 day packet cleanup job is already in the Postgres table
    existing_cleanup_job = scheduler.get_job('packet_cleanup_job')
    if not existing_cleanup_job:
        scheduler.add_job(
            expunge_expired_packets_job,
            trigger='cron',
            hour=0, #run daily at midnight
            minute=0,
            day_of_week='mon-sun',
            id='packet_cleanup_job',
            misfire_grace_time=None,
            replace_existing=True,
            coalesce=True
        )
        logging.info("Packet cleanup job added to database.")
    else:
        logging.info("Packet cleanup job already exists in database. Preserving schedule for catch-up.")

    yield
    scheduler.shutdown()

app = FastAPI(
    title=settings.PROJECT_NAME,
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    generate_unique_id_function=custom_generate_unique_id,
    lifespan=lifespan,
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
