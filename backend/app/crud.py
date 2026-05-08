import datetime
import uuid
import logging
import shutil
from pathlib import Path
from typing import Any

from sqlalchemy import String, cast, insert  # ty:ignore[unresolved-import]
from sqlmodel import Session, col, func, select  # ty:ignore[unresolved-import]

from app.core.config import settings
from app.core.security import get_password_hash, verify_password
from app.models import (
    ActionLogsPublic,
    AdminSettings,
    AdminSettingsPublic,
    IntakeDocument,
    IntakePacket,
    Patient,
    PatientCreate,
    ReminderState,
    Template,
    User,
    UserActionLog,
    UserCreate,
    UserUpdate,
)


def create_user(*, session: Session, user_create: UserCreate) -> User:
    db_obj = User.model_validate(
        user_create, update={"hashed_password": get_password_hash(user_create.password)}
    )
    session.add(db_obj)
    return db_obj

def create_template(
    *,
    session: Session,
    file_contents: bytes,
    file_name: str,
    owner_id: uuid.UUID,
) -> Template:
    file_id = uuid.uuid4()
    storage_dir = Path(settings.TEMPLATE_STORAGE_DIR)
    storage_dir.mkdir(parents=True, exist_ok=True)
    file_path = storage_dir / f"{file_name}"
    file_path.write_bytes(file_contents)
    db_template = Template(
        file_id=file_id,
        file_name=file_name,
        file_path=str(file_path),
        file_owner=owner_id,
    )
    session.add(db_template)
    return db_template

def update_template(
    *,
    session: Session,
    db_template: Template,
    file_contents: bytes | None = None,
    file_name: str | None = None,
    owner_id: uuid.UUID,
) -> Template:
    if file_contents is not None:
        db_template.file_name = file_name or "unnamed_file"
        Path(db_template.file_path).write_bytes(file_contents)
        db_template.file_modified = func.now()
    db_template.file_owner = owner_id
    session.add(db_template)
    return db_template


def update_user(*, session: Session, db_user: User, user_in: UserUpdate) -> Any:
    user_data = user_in.model_dump(exclude_unset=True)
    extra_data = {}
    if "password" in user_data:
        password = user_data["password"]
        hashed_password = get_password_hash(password)
        extra_data["hashed_password"] = hashed_password
    db_user.sqlmodel_update(user_data, update=extra_data)
    session.add(db_user)
    return db_user


def get_user_by_email(*, session: Session, email: str) -> User | None:
    statement = select(User).where(User.email == email)
    session_user = session.exec(statement).first()
    return session_user


# Dummy hash to use for timing attack prevention when user is not found
# This is an Argon2 hash of a random password, used to ensure constant-time comparison
DUMMY_HASH = "$argon2id$v=19$m=65536,t=3,p=4$MjQyZWE1MzBjYjJlZTI0Yw$YTU4NGM5ZTZmYjE2NzZlZjY0ZWY3ZGRkY2U2OWFjNjk"


def authenticate(*, session: Session, email: str, password: str) -> User | None:
    db_user = get_user_by_email(session=session, email=email)
    if not db_user:
        # Prevent timing attacks by running password verification even when user doesn't exist
        # This ensures the response time is similar whether or not the email exists
        verify_password(password, DUMMY_HASH)
        return None
    verified, updated_password_hash = verify_password(password, db_user.hashed_password)
    if not verified:
        return None
    if updated_password_hash:
        db_user.hashed_password = updated_password_hash
        session.add(db_user)
    return db_user

def get_patient_by_ehr_id(*, session: Session, ehr_id: int) -> Patient | None:
    statement = select(Patient).where(Patient.ehr_id == ehr_id)
    session_user = session.exec(statement).first()
    return session_user

def get_patient_by_guid(*, session: Session, patient_guid: uuid.UUID) -> Patient | None:
    statement = select(Patient).where(Patient.id == patient_guid)
    patient = session.exec(statement).first()
    return patient

def create_patient(*, session: Session, patient_create: PatientCreate) -> Patient:
    # create the patient record in the database
    db_obj = Patient.model_validate(patient_create, update={"ehr_id": patient_create.ehr_id}
    )
    session.add(db_obj)
    return db_obj

def delete_packet_and_files(*, session: Session, packet: IntakePacket) -> None:
    """
    Deletes an intake packet record and its associated directory from storage.
    """
    logging.info(f"CRUD: Deleting files for packet ID {packet.id}")
    storage_dir = Path(settings.PDF_STORAGE_DIR) / str(packet.id)
    if storage_dir.is_dir():
        logging.info(f"CRUD: Removing directory {storage_dir}")
        shutil.rmtree(storage_dir)
    else:
        logging.warning(f"CRUD: Directory {storage_dir} not found for packet ID {packet.id}")
    logging.info(f"CRUD: Staging deletion of packet record for ID {packet.id}")
    session.delete(packet)

def log_action(session: Session, user: str, action: str):
    statement = insert(UserActionLog).values(user=user, action=action, timestamp=func.now())
    session.exec(statement)

def get_activity_logs(
    session: Session,
    user: str | None = None,
    action: str | None = None,
    start_date: datetime.datetime | None = None,
    end_date: datetime.datetime | None = None,
    skip: int = 0,
    limit: int = 100,
) -> ActionLogsPublic:
    statement = select(UserActionLog)

    if user:
        statement = statement.where(col(UserActionLog.user).icontains(user))
    if action:
        statement = statement.where(col(UserActionLog.action).icontains(action))
    if start_date:
        statement = statement.where(col(UserActionLog.timestamp) >= start_date)
    if end_date:
        statement = statement.where(col(UserActionLog.timestamp) <= end_date)
    if skip:
        statement = statement.offset(skip)
    if limit:
        statement = statement.limit(limit)

    statement = statement.order_by(col(UserActionLog.timestamp).desc())
    results = session.exec(statement).all()
    return ActionLogsPublic(data=results, count=len(results))

def get_admin_settings(session: Session, setting: str) -> AdminSettingsPublic:
    statement = select(AdminSettings).where(AdminSettings.name == setting)
    # check if record exists
    if not session.exec(statement).first():
        return AdminSettingsPublic(name=setting, value="")
    return session.exec(statement).first()

def update_admin_settings(session: Session, setting: str, value: str) -> AdminSettingsPublic:
    # first check if the setting exists already
    session_setting = get_admin_settings(session, setting)
    if session_setting.value:
        session_setting.value = value # set a new value
    else:
        session_setting = AdminSettings(name=setting, value=value) #create a new setting
    session.add(session_setting)
    return session_setting

def get_avg_duration(session: Session) -> float | None:
    """
    Calculates the average duration in hours between intake packet creation and reminder completion.
    """
    average_completion_duration_hours = func.round(
        func.avg(
            func.extract(
                "epoch",
                func.age(ReminderState.completed_at, IntakePacket.created_at)
            )
        )
        / 3600,
        3,
    ).label("average_completion_duration_hours")

    statement = (
        select(average_completion_duration_hours)
        .select_from(IntakePacket)
        .join(
            ReminderState,
            IntakePacket.patient_id_number
            == cast(ReminderState.patient_ehr_id, String),
        )
        .where(col(ReminderState.completed_at).is_not(None))
        .where(col(IntakePacket.created_at).is_not(None))
    )
    result = session.exec(statement).first()
    return result

def get_incomplete_patients(session: Session) -> list[str]:
    """
    Returns the list of patients who have incomplete forms
    (i.e. intake packets that have not yet been completed).
    """
    statement = (
        select(IntakePacket.patient_id_number)
        .where(IntakePacket.status != "COMPLETED")
        .where(IntakePacket.status != "LINKED")
    )
    results = session.exec(statement).all()
    return results

def get_incomplete_forms(session: Session) -> list[dict[str, Any]]:
    """
    Returns the summary of forms that have not yet
    been completed (i.e. status != COMPLETED or LINKED)
    """
    statement = (
        select(IntakeDocument.form_name, func.count(IntakeDocument.form_name).label("count"))
        .group_by(IntakeDocument.form_name)
        .where(IntakeDocument.status != "COMPLETED")
        .where(IntakeDocument.status != "LINKED")
    )
    results = session.exec(statement).all()
    return [r._mapping for r in results]
