import uuid
from datetime import datetime, timezone
from enum import Enum

from pydantic import EmailStr  # ty:ignore[unresolved-import]
from sqlalchemy import DateTime  # ty:ignore[unresolved-import]
from sqlmodel import (  # ty:ignore[unresolved-import]
    Field,
    Relationship,
    SQLModel,
    UniqueConstraint,
)


def get_datetime_utc() -> datetime:
    return datetime.now(timezone.utc)


# Shared properties
class UserBase(SQLModel):
    email: EmailStr = Field(unique=True, index=True, max_length=255)
    is_active: bool = True
    is_superuser: bool = False
    full_name: str | None = Field(default=None, max_length=255)


# Properties to receive via API on creation
class UserCreate(UserBase):
    password: str = Field(min_length=8, max_length=128)


class UserRegister(SQLModel):
    email: EmailStr = Field(max_length=255)
    password: str = Field(min_length=8, max_length=128)
    full_name: str | None = Field(default=None, max_length=255)


# Properties to receive via API on update, all are optional
class UserUpdate(UserBase):
    email: EmailStr | None = Field(default=None, max_length=255)
    password: str | None = Field(default=None, min_length=8, max_length=128)
    role: str | None = Field(default=None, min_length=1, max_length=10)


class UserUpdateMe(SQLModel):
    full_name: str | None = Field(default=None, max_length=255)
    email: EmailStr | None = Field(default=None, max_length=255)


class UpdatePassword(SQLModel):
    current_password: str = Field(min_length=8, max_length=128)
    new_password: str = Field(min_length=8, max_length=128)


# Database model, database table inferred from class name
class User(UserBase, table=True):
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    hashed_password: str
    created_at: datetime | None = Field(
        default_factory=get_datetime_utc,
        sa_type=DateTime(timezone=True),
    )
    intake_packets: list["IntakePacket"] = Relationship(
        back_populates="owner", cascade_delete=True
    )


# Properties to return via API, id is always required
class UserPublic(UserBase):
    id: uuid.UUID
    created_at: datetime | None = None


class UsersPublic(SQLModel):
    data: list[UserPublic]
    count: int


# --- Intake Packet / Form Models ---
class FormStatus(str, Enum):
    NOT_STARTED = "NOT_STARTED"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"
    LINKED = "LINKED"


class IntakePacketBase(SQLModel):
    patient_id_number: str = Field(max_length=20)
    patient_name: str = Field(max_length=255)
    facility: str = Field(max_length=50)
    admission_date: str = Field(max_length=20)
    counselor_name: str = Field(max_length=255)


class IntakePacketCreate(IntakePacketBase):
    template_ids: list[str]


class IntakePacketUpdate(SQLModel):
    status: str | None = Field(default=None, max_length=50)
    patient_name: str | None = Field(max_length=255)


class IntakeDocumentPublic(SQLModel):
    id: uuid.UUID
    template_id: str
    form_name: str
    category: str
    filename: str
    status: str
    packet_id: uuid.UUID
    created_at: datetime | None = None


class IntakePacket(IntakePacketBase, table=True):
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    created_at: datetime | None = Field(
        default_factory=get_datetime_utc,
        sa_type=DateTime(timezone=True),  # type: ignore
    )
    status: str = Field(default=FormStatus.NOT_STARTED, max_length=50, nullable=False)
    owner_id: uuid.UUID = Field(
        foreign_key="user.id", nullable=False, ondelete="CASCADE"
    )
    owner: User | None = Relationship(back_populates="intake_packets")
    documents: list["IntakeDocument"] = Relationship(
        back_populates="packet", cascade_delete=True
    )


class IntakePacketPublic(IntakePacketBase):
    id: uuid.UUID
    status: str
    owner_id: uuid.UUID
    created_at: datetime | None = None
    documents: list[IntakeDocumentPublic] = []


class IntakePacketsPublic(SQLModel):
    data: list[IntakePacketPublic]
    count: int


class IntakeDocumentBase(SQLModel):
    template_id: str = Field(max_length=100)
    form_name: str = Field(max_length=255)
    category: str = Field(default="Other", max_length=100)
    filename: str = Field(max_length=500)


class IntakeDocument(IntakeDocumentBase, table=True):
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    created_at: datetime | None = Field(
        default_factory=get_datetime_utc,
        sa_type=DateTime(timezone=True),  # type: ignore
    )
    status: str = Field(default=FormStatus.NOT_STARTED, max_length=50, nullable=False)
    packet_id: uuid.UUID = Field(
        foreign_key="intakepacket.id", nullable=False, ondelete="CASCADE"
    )
    packet: IntakePacket | None = Relationship(back_populates="documents")

# Generic message
class Message(SQLModel):
    message: str


# JSON payload containing access token
class Token(SQLModel):
    access_token: str
    token_type: str = "bearer"


# Contents of JWT token
class TokenPayload(SQLModel):
    sub: str | None = None


class NewPassword(SQLModel):
    token: str
    new_password: str = Field(min_length=8, max_length=128)


class PatientBase(SQLModel):
    ehr_id: int = Field(unique=True)


# Properties to receive via API on creation
class PatientCreate(PatientBase):
    pass


# Properties to receive via API on update
class PatientUpdate(PatientBase):
    session_start: datetime | None
    session_end: datetime | None
    session_status: str | None = Field(default=None)
    counselorId: uuid.UUID | None = Field(default = None, foreign_key="user.id")


# Database model, database table inferred from class name
class Patient(PatientBase, table=True):
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    created_at: datetime | None = Field(
        default_factory=get_datetime_utc,
        sa_type=DateTime(timezone=True),
    )
    counselorId: uuid.UUID | None = Field(default = None, foreign_key="user.id")

# Properties to return via API, id is always required
class PatientPublic(PatientBase):
    id: uuid.UUID
    created_at: datetime | None = None

class PatientsPublic(SQLModel):
    data: list[PatientPublic]
    count: int


class TemplateBase(SQLModel):
    file_name: str = Field(min_length=1, max_length=255)
    class Config:
        from_attributes = True


# Properties to receive on template creation
class TemplateCreate(TemplateBase):
    pass

# Database model, database table inferred from class name
class Template(SQLModel, table=True):
    file_id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    file_modified: datetime | None = Field(
        default_factory=get_datetime_utc,
        sa_type=DateTime(timezone=True),
    )
    file_owner: uuid.UUID = Field(
        foreign_key="user.id", nullable=False, ondelete="CASCADE"
    )
    file_name: str = Field(min_length=1, max_length=255)
    file_path: str = Field(max_length=1024)
    category: str = Field(default="Other", max_length=100)
    template_config: str | None = Field(default=None)  # JSON: acroform field mappings

    class Config:
        from_attributes = True


class TemplatePublic(SQLModel):
    file_id: uuid.UUID
    file_name: str
    file_modified: datetime | None = None
    file_owner: uuid.UUID
    category: str = "Other"
    template_config: str | None = None
    class Config:
        from_attributes = True


class TemplatesPublic(SQLModel):
    data: list[TemplatePublic]
    count: int
    class Config:
        from_attributes = True

class TemplateUpdate(TemplateBase):
    file_name: str | None = Field(default=None, min_length=1, max_length=255)
    class Config:
        from_attributes = True


# ------------------------------
# Reminder State
# ------------------------------

class ReminderStateBase(SQLModel):
    """
    Shared fields for a one-time reminder.
    Show when:
      completed_at IS NOT NULL AND seen_at IS NULL
    """
    key: str = Field(index=True, max_length=100)  # e.g. "session_completed"

    completed_at: datetime | None = Field(
        default=None,
        sa_type=DateTime(timezone=True),  # type: ignore
    )
    seen_at: datetime | None = Field(
        default=None,
        sa_type=DateTime(timezone=True),  # type: ignore
    )


class ReminderState(ReminderStateBase, table=True):
    """
    Per-patient (ehr_id), per-reminder state.
    """
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)

    # FK to Patient.ehr_id (integer)
    patient_ehr_id: int = Field(
        foreign_key="patient.ehr_id",
        nullable=False,
        ondelete="CASCADE",
        index=True,
    )

    # Optional relationship (works because FK points to a unique column)
    #patient: Optional["Patient"] = Relationship()

    # Ensure one row per patient + reminder key
    __table_args__ = (
        UniqueConstraint(
            "patient_ehr_id",
            "key",
            name="uq_reminderstate_ehr_key",
        ),
    )


class WeeklyReportBase(SQLModel):
    reportEmail: str | None = Field(min_length=1, max_length=255)
    avgCompletionTime: str | None
    # incompleteUsers: list["Patient"] | None = Relationship(back_populates="weekly_report")
    # incompleteForms: list[str] | None


class WeeklyReportCreate(WeeklyReportBase):
    pass


class WeeklyReport(WeeklyReportBase, table=True):
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    created_at: datetime | None = Field(
        default_factory=get_datetime_utc,
        sa_type=DateTime(timezone=True),
    )


class ActionLog(SQLModel):
    action: str = Field(max_length=1024)


class ActionLogPublic(SQLModel):
    user: str
    action: str
    timestamp: datetime


class ActionLogsPublic(SQLModel):
    data: list[ActionLogPublic]
    count: int


class UserActionLog(SQLModel, table=True):
    id: int = Field(primary_key=True)
    user: EmailStr = Field(
        index=True,
        nullable=False,
        max_length=255,
    )
    action: str = Field(max_length=1024, index=True, nullable=False)
    timestamp: datetime = Field(
        default_factory=get_datetime_utc,
        sa_type=DateTime(timezone=True),
    )

class AdminSettings(SQLModel, table=True):
    id: int = Field(default=1, primary_key=True)
    name: str = Field()
    value: str = Field()

class AdminSettingsPublic(SQLModel):
    name: str
    value: str
