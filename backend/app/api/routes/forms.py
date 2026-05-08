import datetime
import logging
import uuid
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, Request, Response
from sqlmodel import Session, col, func, select

from app import crud
from app.api.deps import CurrentUser, SessionDep, get_db
from app.core.config import settings
from app.core.db import engine
from app.models import (
    IntakeDocument,
    IntakeDocumentPublic,
    IntakePacket,
    IntakePacketCreate,
    IntakePacketPublic,
    IntakePacketsPublic,
    Message,
    Template,
)
from app.pdf_engine.models.patient import PatientData
from app.pdf_engine.pipeline import IntakePacketGenerator

router = APIRouter(prefix="/forms", tags=["forms"])


def _get_uploaded_templates(session):
    """Fetch all uploaded templates that have been configured."""
    return session.exec(
        select(Template).where(Template.template_config.is_not(None))  # type: ignore
    ).all()


def _make_generator(session) -> IntakePacketGenerator:
    """Create an IntakePacketGenerator that includes uploaded templates."""
    uploaded = _get_uploaded_templates(session)
    return IntakePacketGenerator(db_templates=uploaded)


@router.get("/templates")
def list_templates(session: SessionDep, current_user: CurrentUser) -> Any:  # noqa: ARG001
    """List all available intake form templates (built-in + uploaded)."""
    generator = _make_generator(session)
    return generator.list_available_forms()


@router.post("/packets", response_model=IntakePacketPublic)
def create_intake_packet(
    *,
    session: SessionDep,
    current_user: CurrentUser,
    packet_in: IntakePacketCreate,
) -> Any:
    """Generate a new intake packet (pre-fills and stores PDFs)."""
    patient = PatientData(
        patient_id=packet_in.patient_id_number,
        patient_name=packet_in.patient_name,
        facility=packet_in.facility,
        admission_date=packet_in.admission_date,
        counselor_name=packet_in.counselor_name,
    )

    packet = IntakePacket.model_validate(
        packet_in, update={"owner_id": current_user.id}
    )
    session.add(packet)
    session.commit()
    session.refresh(packet)

    output_dir = Path(settings.PDF_STORAGE_DIR) / str(packet.id)
    output_dir.mkdir(parents=True, exist_ok=True)

    generator = _make_generator(session)
    results = generator.generate_packet(patient, output_dir, packet_in.template_ids)

    for r in results:
        if r.success and r.filepath:
            template = generator.registry.get(r.template_id)
            doc = IntakeDocument(
                template_id=r.template_id,
                form_name=r.form_name,
                category=template.category if template else "Other",
                filename=Path(r.filepath).name,
                packet_id=packet.id,
            )
            session.add(doc)

    session.commit()

    crud.log_action(
        session=session,
        user=current_user.email,
        action=f"Created intake packet for patient '{packet.patient_id_number}'"
    )
    session.commit()
    session.refresh(packet)

    return packet

@router.patch("/packets/{packet_id}", response_model=IntakePacketPublic)
def update_intake_packet(
    *,
    session: SessionDep,
    current_user: CurrentUser,
    packet_id: uuid.UUID,
    update: dict[str, Any],
) -> Any:
    """Update an existing intake packet."""
    packet: IntakePacket = session.get(IntakePacket, packet_id)

    documents_update = update.pop("documents", None)
    if documents_update is not None:
        if not isinstance(documents_update, list):
            raise HTTPException(status_code=422, detail="documents must be a list")

        for document_update in documents_update:
            if not isinstance(document_update, dict):
                continue

            document_id = document_update.get("id")
            if not document_id:
                continue

            try:
                document_uuid = uuid.UUID(str(document_id))
            except ValueError:
                continue

            document = session.get(IntakeDocument, document_uuid)
            if not document or document.packet_id != packet_id:
                continue

            for key, value in document_update.items():
                if key in {"id", "packet_id", "created_at"}:
                    continue
                if hasattr(document, key):
                    setattr(document, key, value)

    for key, value in update.items():
        if hasattr(packet, key):
            setattr(packet, key, value)
    session.commit()

    crud.log_action(
        session=session,
        user=current_user.email,
        action=f"updated intake packet for patient '{packet.patient_id_number}' with new data: {update}"
    )
    session.commit()
    session.refresh(packet)

    return packet

@router.get("/packets", response_model=IntakePacketsPublic)
def read_packets(
    session: SessionDep,
    current_user: CurrentUser,
    skip: int = 0,
    limit: int = 100,
) -> Any:
    """List intake packets for the current user."""
    if current_user:# Once owner_id is implemented append .is_superuser:
        count = session.exec(
            select(func.count()).select_from(IntakePacket)
        ).one()
        packets = session.exec(
            select(IntakePacket)
            .order_by(col(IntakePacket.created_at).desc())
            .offset(skip)
            .limit(limit)
        ).all()
    else:
        count = session.exec(
            select(func.count())
            .select_from(IntakePacket)
            .where(IntakePacket.owner_id == current_user.id)
        ).one()
        packets = session.exec(
            select(IntakePacket)
            .where(IntakePacket.owner_id == current_user.id)
            .order_by(col(IntakePacket.created_at).desc())
            .offset(skip)
            .limit(limit)
        ).all()

    return IntakePacketsPublic(data=list(packets), count=count)


@router.get("/packets/{packet_id}", response_model=IntakePacketPublic)
def read_packet(
    session: SessionDep,
    current_user: CurrentUser,
    packet_id: uuid.UUID,
) -> Any:
    """Get a single intake packet with its documents."""
    packet = session.get(IntakePacket, packet_id)
    if not packet:
        raise HTTPException(status_code=404, detail="Packet not found")
    if not current_user.is_superuser and packet.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not enough permissions")
    return packet


@router.get("/packets/{packet_id}/documents/{doc_id}/pdf")
def get_document_pdf(
    session: SessionDep,
    current_user: CurrentUser,
    packet_id: uuid.UUID,
    doc_id: uuid.UUID,
) -> Response:
    """Serve raw PDF bytes for the in-browser viewer."""
    packet = session.get(IntakePacket, packet_id)
    if not packet:
        raise HTTPException(status_code=404, detail="Packet not found")
    if not current_user.is_superuser and packet.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not enough permissions")

    doc = session.get(IntakeDocument, doc_id)
    if not doc or doc.packet_id != packet_id:
        raise HTTPException(status_code=404, detail="Document not found")

    filepath = Path(settings.PDF_STORAGE_DIR) / str(packet_id) / doc.filename
    if not filepath.is_file():
        raise HTTPException(status_code=404, detail="PDF file not found on disk")

    return Response(content=filepath.read_bytes(), media_type="application/pdf")


@router.post("/packets/{packet_id}/documents/{doc_id}/save")
async def save_document_pdf(
    request: Request,
    session: SessionDep,
    current_user: CurrentUser,
    packet_id: uuid.UUID,
    doc_id: uuid.UUID,
) -> Any:
    """Save a completed PDF (with signatures) back to the server."""
    packet = session.get(IntakePacket, packet_id)
    if not packet:
        raise HTTPException(status_code=404, detail="Packet not found")
    if not current_user.is_superuser and packet.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not enough permissions")

    doc = session.get(IntakeDocument, doc_id)
    if not doc or doc.packet_id != packet_id:
        raise HTTPException(status_code=404, detail="Document not found")

    body = await request.body()
    if len(body) > 50 * 1024 * 1024:  # 50 MB hard limit
        raise HTTPException(status_code=413, detail="PDF file too large")
    if not body.startswith(b"%PDF"):
        raise HTTPException(status_code=400, detail="Invalid PDF content")
    filepath = Path(settings.PDF_STORAGE_DIR) / str(packet_id) / doc.filename
    filepath.parent.mkdir(parents=True, exist_ok=True)
    filepath.write_bytes(body)

    doc.status = "IN_PROGRESS"

    crud.log_action(
        session=session,
        user=current_user.email,
        action=f"Saved pdf '{doc.filename}' for patient '{packet.patient_id_number}' to server"
    )
    session.commit()

    return {"success": True, "filename": doc.filename}


@router.delete("/packets/{packet_id}")
def delete_packet(
    session: SessionDep,
    current_user: CurrentUser,
    packet_id: uuid.UUID,
) -> Message:
    """Delete an intake packet and all its associated PDF files."""
    packet = session.get(IntakePacket, packet_id)
    if not packet:
        raise HTTPException(status_code=404, detail="Packet not found")
    if not current_user.is_superuser and packet.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not enough permissions")

    patient_id_number = packet.patient_id_number
    crud.delete_packet_and_files(session=session, packet=packet)

    crud.log_action(
        session=session,
        user=current_user.email,
        action=f"Deleted intake packet for patient '{patient_id_number}'"
    )
    session.commit()

    return Message(message="Intake packet deleted successfully")


@router.get(
    "/packets/{packet_id}/documents/{doc_id}",
    response_model=IntakeDocumentPublic,
)
def read_document(
    session: SessionDep,
    current_user: CurrentUser,
    packet_id: uuid.UUID,
    doc_id: uuid.UUID,
) -> Any:
    """Get a single document record."""
    packet = session.get(IntakePacket, packet_id)
    if not packet:
        raise HTTPException(status_code=404, detail="Packet not found")
    if not current_user.is_superuser and packet.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not enough permissions")

    doc = session.get(IntakeDocument, doc_id)
    if not doc or doc.packet_id != packet_id:
        raise HTTPException(status_code=404, detail="Document not found")
    return doc


@router.post(
    "/packets/{packet_id}/documents",
    response_model=list[IntakeDocumentPublic],
)
def add_documents_to_packet(
    *,
    session: SessionDep,
    current_user: CurrentUser,
    packet_id: uuid.UUID,
    body: dict[str, Any],
) -> Any:
    """Add new forms to an existing packet.

    Body: {"template_ids": ["template_id_1", "template_id_2"]}
    """
    packet = session.get(IntakePacket, packet_id)
    if not packet:
        raise HTTPException(status_code=404, detail="Packet not found")
    if not current_user.is_superuser and packet.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not enough permissions")

    template_ids = body.get("template_ids", [])
    if not template_ids:
        raise HTTPException(status_code=422, detail="template_ids is required")

    # Check which templates already exist in the packet
    existing_ids = {d.template_id for d in packet.documents}

    patient = PatientData(
        patient_id=packet.patient_id_number,
        patient_name=packet.patient_name,
        facility=packet.facility,
        admission_date=packet.admission_date,
        counselor_name=packet.counselor_name,
    )

    output_dir = Path(settings.PDF_STORAGE_DIR) / str(packet_id)
    output_dir.mkdir(parents=True, exist_ok=True)

    generator = _make_generator(session)
    new_docs = []

    for tid in template_ids:
        if tid in existing_ids:
            continue

        result = generator.generate_form(tid, patient, output_dir)
        if result.success and result.filepath:
            template = generator.registry.get(tid)
            doc = IntakeDocument(
                template_id=tid,
                form_name=result.form_name,
                category=template.category if template else "Other",
                filename=Path(result.filepath).name,
                packet_id=packet_id,
            )
            session.add(doc)
            new_docs.append(doc)

    session.commit()
    for doc in new_docs:
        session.refresh(doc)

    crud.log_action(
        session=session,
        user=current_user.email,
        action=f"Added {len(new_docs)} form(s) to packet for patient '{packet.patient_id_number}'"
    )

    return new_docs


@router.delete(
    "/packets/{packet_id}/documents/{doc_id}",
    response_model=Message,
)
def remove_document_from_packet(
    *,
    session: SessionDep,
    current_user: CurrentUser,
    packet_id: uuid.UUID,
    doc_id: uuid.UUID,
) -> Message:
    """Remove a form from an existing packet."""
    packet = session.get(IntakePacket, packet_id)
    if not packet:
        raise HTTPException(status_code=404, detail="Packet not found")
    if not current_user.is_superuser and packet.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not enough permissions")

    doc = session.get(IntakeDocument, doc_id)
    if not doc or doc.packet_id != packet_id:
        raise HTTPException(status_code=404, detail="Document not found")

    # Delete PDF file from disk
    filepath = Path(settings.PDF_STORAGE_DIR) / str(packet_id) / doc.filename
    if filepath.is_file():
        filepath.unlink()

    form_name = doc.form_name
    session.delete(doc)
    session.commit()

    crud.log_action(
        session=session,
        user=current_user.email,
        action=f"Removed form '{form_name}' from packet for patient '{packet.patient_id_number}'"
    )

    return Message(message=f"Document '{form_name}' removed from packet")

def expunge_expired_packets_job() -> None:
    """
    Scheduled job: delete intake packets older than 30 days.
    Runs daily at midnight UTC.
    """
    logging.info("Scheduler: Running expired packet expungement job.")
    with Session(engine) as session:
        try:
            cutoff:datetime.datetime = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=30)
            statement = (
                select(IntakePacket)
                .where(col(IntakePacket.created_at).is_not(None))
                .where(col(IntakePacket.created_at) < cutoff)
            )
            expired_packets: list[IntakePacket] = session.exec(statement).all()
            crud.log_action(
                session=session,
                user="Scheduler",
                action=f"Running check for expired intake packets to expunge. Found {len(expired_packets)}."
            )
            logging.info(f"Scheduler: Found {len(expired_packets)} expired packet(s).")
            for packet in expired_packets:
                logging.info(f"Scheduler: Processing packet ID {packet.id} for patient {packet.patient_id_number}")
                patient_id_number = packet.patient_id_number
                crud.delete_packet_and_files(session=session, packet=packet)
                crud.log_action(
                    session=session,
                    user="Scheduler",
                    action=f"Deleted expired intake packet for patient '{patient_id_number}'"
                )
                logging.info(f"Scheduler: Marked packet ID {packet.id} for deletion.")
            logging.info("Scheduler: Committing deletions.")
            session.commit()
            logging.info("Scheduler: Deletions committed.")
        except Exception as e:
            logging.error(f"Scheduler: Error during packet expungement: {e}", exc_info=True)
            # The 'with' statement will automatically handle session rollback on exception
