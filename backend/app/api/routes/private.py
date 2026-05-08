from typing import Any

from fastapi import APIRouter  # ty:ignore[unresolved-import]
from pydantic import BaseModel  # ty:ignore[unresolved-import]

from app import crud
from app.api.deps import SessionDep
from app.core.security import get_password_hash
from app.models import (
    User,
    UserPublic,
)

router = APIRouter(tags=["private"], prefix="/private")


class PrivateUserCreate(BaseModel):
    email: str
    password: str
    full_name: str
    is_verified: bool = False


@router.post("/users/", response_model=UserPublic)
def create_user(user_in: PrivateUserCreate, session: SessionDep) -> Any:
    """
    Create a new user.
    """

    user = User(
        email=user_in.email,
        full_name=user_in.full_name,
        hashed_password=get_password_hash(user_in.password),
    )

    session.add(user)
    # Log the action
    crud.log_action(
        session=session,
        user=user.email,
        action=f"Created user '{user_in.email}'"
    )
    session.commit()
    return user
