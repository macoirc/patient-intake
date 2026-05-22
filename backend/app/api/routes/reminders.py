from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from sqlalchemy.exc import IntegrityError
from sqlmodel import select

from app import crud
from app.api.deps import CurrentUser, SessionDep
from app.models import Patient, ReminderState  # <-- import from models.py

router = APIRouter(prefix="/reminders", tags=["reminders"])


def _now() -> datetime:
    return datetime.now(timezone.utc)


class ReminderPatientPayload(BaseModel):
    ehr_id: int


@router.post("/new")
def create_reminder_status(
    patient_ehr_id: int,
    db: SessionDep
) -> ReminderState:
    db_reminder: ReminderState = ReminderState(
        patient_ehr_id=patient_ehr_id,
        key="session_completed",
        completed_at=None,
        seen_at=None
    )
    db.add(db_reminder)
    db.commit()
    db.refresh(db_reminder)
    return db_reminder


@router.get("/{key}")
def get_reminder_status(
    key: str,
    ehr_id: int,  # query param: ?ehr_id=123
    db: SessionDep,
) -> dict:
    state = db.exec(
        select(ReminderState).where(
            ReminderState.patient_ehr_id == ehr_id,
            ReminderState.key == key,
        )
    ).first()

    if not state:
        return {}

    return {
        "key": key,
        "completed": state.completed_at is not None,
        "seen": state.seen_at is not None,
        "completed_at": state.completed_at,
        "seen_at": state.seen_at,
    }


@router.post("/{key}/complete")
def mark_reminder_complete(
    current_user: CurrentUser,
    key: str,
    payload: ReminderPatientPayload,
    db: SessionDep,
) -> dict:
    patient = db.exec(select(Patient).where(Patient.ehr_id == payload.ehr_id)).first()
    if not patient:
        raise HTTPException(status_code=404, detail="Patient not found")

    try:
        state = db.exec(
            select(ReminderState).where(
                ReminderState.patient_ehr_id == payload.ehr_id,
                ReminderState.key == key,
            )
        ).first()

        if not state:
            state = ReminderState(patient_ehr_id=payload.ehr_id, key=key, completed_at=_now())
            db.add(state)
        elif state.completed_at is None:
            state.completed_at = _now()
            db.add(state)

        crud.log_action(
            session=db,
            user=current_user.email,
            action=f"Acknowledged linking reminder for patient '{payload.ehr_id}'"
        )
        db.commit()
    except IntegrityError:
        db.rollback()
        # Race condition: another request created the state. Re-fetch it.
        state = db.exec(select(ReminderState).where(
            ReminderState.patient_ehr_id == payload.ehr_id,
            ReminderState.key == key,
        )).first()

    return {"ok": True, "key": key, "completed_at": state.completed_at}


@router.post("/seen")
def mark_reminder_seen(
    current_user: CurrentUser,
    payload: ReminderPatientPayload,
    db: SessionDep,
) -> dict:
    state = db.exec(
        select(ReminderState).where(
            ReminderState.patient_ehr_id == payload.ehr_id,
        )
    ).first()

    if not state:
        raise HTTPException(status_code=400, detail="Reminder not created yet")
    if state.completed_at is not None:
        raise HTTPException(status_code=400, detail="Reminder already completed")

    state.seen_at = _now()
    db.add(state)

    crud.log_action(
        session=db,
        user=current_user.email,
        action=f"Viewed linking reminder for patient '{payload.ehr_id}'"
    )
    db.commit()
    db.refresh(state)

    return {"ok": True, "seen_at": state.seen_at}
