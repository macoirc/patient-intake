from fastapi import APIRouter, HTTPException  # ty:ignore[unresolved-import]

from app import crud
from app.api.deps import CurrentUser, SessionDep
from app.models import (
    AdminSettingsPublic,
)

router = APIRouter(prefix="/admin", tags=["admin"])

@router.get("/settings/folder", response_model=AdminSettingsPublic)
async def read_folder(
    session: SessionDep,
) -> AdminSettingsPublic:
    """ Retrieve the export folder path
        configured by the admin.
    """
    res = crud.get_admin_settings(session=session, setting="storage_folder")
    if res.value == "":
        raise HTTPException(status_code=404, detail="Folder not found. Try setting one.")
    return res


@router.put("/settings/folder", response_model=AdminSettingsPublic)
async def update_folder(
    session: SessionDep,
    current_user: CurrentUser,
    folder: str,
) -> AdminSettingsPublic:
    """ Update the export folder path
        configured by the admin.
    """
    if not current_user.is_superuser:
        raise HTTPException(status_code=403, detail="Not enough permissions")

    try:
        res = crud.update_admin_settings(session=session, setting="storage_folder", value=folder)
        crud.log_action(
            session=session,
            user=current_user.email,
            action=f"Updated default folder path to '{folder}'"
        )
        session.commit()
        return res
    except Exception as e:
        session.rollback()
        raise HTTPException(status_code=500, detail=str(e))
