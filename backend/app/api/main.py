from fastapi import APIRouter  # ty:ignore[unresolved-import]

from app.api.routes import (
    admin,
    forms,
    login,
    logs,
    patient,
    private,
    reminders,
    report,
    templates,
    users,
    utils,
)
from app.core.config import settings

api_router = APIRouter()
api_router.include_router(login.router)
api_router.include_router(users.router)
api_router.include_router(utils.router)
api_router.include_router(templates.router)
api_router.include_router(reminders.router)
api_router.include_router(report.router)
api_router.include_router(patient.router)
api_router.include_router(logs.router)
api_router.include_router(admin.router)
api_router.include_router(forms.router)

if settings.ENVIRONMENT == "local":
    api_router.include_router(private.router)
