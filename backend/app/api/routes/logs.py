import datetime

from fastapi import APIRouter, HTTPException  # ty:ignore[unresolved-import]

from app import crud
from app.api.deps import CurrentUser, SessionDep
from app.models import ActionLogsPublic

router = APIRouter(prefix="/logs", tags=["logs"])

@router.get("/", response_model=ActionLogsPublic)
def read_logs(
    session: SessionDep,
    current_user: CurrentUser,
    user: str | None = None,
    action: str | None = None,
    start_date: datetime.datetime | None = None,
    end_date: datetime.datetime | None = None,
    skip: int = 0,
    limit: int = 100,
) -> ActionLogsPublic:
    """
    Retrieve logs.
    """
    if not current_user.is_superuser:
        raise HTTPException(status_code=403, detail="Not enough permissions")

    return crud.get_activity_logs(
        session=session,
        user=user,
        action=action,
        start_date=start_date,
        end_date=end_date,
        skip=skip,
        limit=limit,
    )
