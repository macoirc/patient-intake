from typing import Any

from fastapi import APIRouter, HTTPException  # ty:ignore[unresolved-import]
from sqlmodel import func, select

from app import crud
from app.api.deps import (
    CurrentUser,
    SessionDep,
)
from app.models import (
    Patient,
    PatientCreate,
    PatientsPublic,
)

router = APIRouter(prefix="/patient", tags=["patients"])

@router.get("/", response_model=PatientsPublic)
def read_patients(
    session: SessionDep, current_user: CurrentUser, skip: int = 0, limit: int = 100
) -> Any:
    """
    Retrieve patients.
    """

    if current_user:# Once owner_id is implemented append .is_superuser:
        count_statement = select(func.count()).select_from(Patient)
        count = session.exec(count_statement).one()
        statement = (
            select(Patient).order_by(Patient.ehr_id).offset(skip).limit(limit)
        )
        patients = session.exec(statement).all()
    else:
        count_statement = (
            select(func.count())
            .select_from(Patient)
            .where(Patient.owner_id == current_user.id)
        )
        count = session.exec(count_statement).one()
        statement = (
            select(Patient)
            .where(Patient.owner_id == current_user.id)
            .order_by(Patient.ehr_id)
            .offset(skip)
            .limit(limit)
        )
        patients = session.exec(statement).all()

    return PatientsPublic(data=patients, count=count)

@router.post("/", response_model=Patient)
def create_patient(
    *,
    session: SessionDep,
    current_user: CurrentUser,
    patient_in: PatientCreate,
) -> Any:
    """
    Create new patient.
    """
    existing_patient = crud.get_patient_by_ehr_id(session=session, ehr_id=patient_in.ehr_id)
    if existing_patient:
        raise HTTPException(
            status_code=400,
            detail="The patient with this EHR ID already exists in the system.",
        )

    patient = crud.create_patient(session=session, patient_create=patient_in)

    # Log the action
    crud.log_action(
        session=session,
        user=current_user.email,
        action=f"Created patient '{patient_in.ehr_id}'"
    )
    session.commit()
    return patient


@router.get("/{ehr_id}", response_model=Patient)
def read_patient(
    ehr_id: int,
    session: SessionDep,

) -> Patient:
    """
    Get patient by EHR ID.
    """
    patient = crud.get_patient_by_ehr_id(session=session, ehr_id=ehr_id)
    if not patient:
        raise HTTPException(status_code=404, detail="Patient not found")
    else:
        return patient
