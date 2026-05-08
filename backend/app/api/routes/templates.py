import json
import logging
import os
import re
import uuid
from pathlib import Path
from typing import Any

from fastapi import (  # ty:ignore[unresolved-import]
    APIRouter,
    File,
    HTTPException,
    Response,
    UploadFile,
)
from sqlmodel import col, func, select  # ty:ignore[unresolved-import]

from app import crud
from app.api.deps import CurrentUser, SessionDep
from app.core.config import settings
from app.models import (
    Template,
    TemplatePublic,
    TemplatesPublic,
)

router = APIRouter(prefix="/templates", tags=["templates"])

@router.get("/", response_model=TemplatesPublic)
def read_templates(
    session: SessionDep, skip: int = 0, limit: int = 100
) -> Any:
    """
    Retrieve templates.
    """

    count_statement = (
        select(func.count())
        .select_from(Template)
    )
    count = session.exec(count_statement).one()
    statement = (
        select(Template)
        .offset(skip)
        .limit(limit)
        .order_by(col(Template.file_name).asc())
    )
    templates = session.exec(statement).all()
    templates_public = [TemplatePublic(file_id=t.file_id, file_name=t.file_name, file_modified=t.file_modified, file_owner=t.file_owner, category=t.category, template_config=t.template_config) for t in templates]
    return TemplatesPublic(data=templates_public, count=count)

@router.get(
    "/{id}",
    response_class=Response,
    responses={
        200: {
            "content": {"application/pdf": {"schema": {"type": "string", "format": "binary"}}},
            "description": "Return the PDF file",
        },
        404: {"description": "Template not found"},
    },
)
def read_template(session: SessionDep, id: uuid.UUID) -> Any:
    """
    Get template by ID.
    """
    template = session.get(Template, id)
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")

    file_path = Path(template.file_path)
    if not file_path.is_file():
        raise HTTPException(status_code=404, detail="Template file not found on disk")

    return Response(content=file_path.read_bytes(), media_type="application/pdf")

@router.post("/", response_model=TemplatePublic)
async def create_template(
    session: SessionDep,
    current_user: CurrentUser,
    file: UploadFile = File(...),  # Validates that a file is present
) -> Any:
    """
    Create a new template with a PDF file upload.
    """
    if not current_user.is_superuser:
        raise HTTPException(status_code=403, detail="You must be administrator to upload forms")

    # 1. Validate Content Type
    if file.content_type != "application/pdf":
        raise HTTPException(status_code=400, detail="File must be a PDF")

    # 2. Read the binary content
    file_content = await file.read()

    # 3. Create the DB object via CRUD
    db_template = crud.create_template(
        session=session,
        file_contents=file_content,
        file_name=file.filename or "unnamed_file",
        owner_id=current_user.id,
    )

    # 4. Auto-configure: analyze fields and set up template for packet use
    try:
        _auto_configure_template(session, db_template)
    except Exception as e:
        # Non-fatal: template is still uploaded, just not auto-configured
        logging.error(f"Auto-configure failed for '{db_template.file_name}'. Exception: {e!r}", exc_info=True)

    # 5. Log the action
    crud.log_action(
        session=session,
        user=current_user.email,
        action=f"Created template '{db_template.file_name}'"
    )
    session.commit()

    # Return the public schema
    session.refresh(db_template)
    return db_template

@router.put("/{id}", response_model=TemplatePublic)
async def update_template(
    session: SessionDep,
    current_user: CurrentUser,
    id: uuid.UUID,
    file: UploadFile | None = File(None),
) -> Any:
    """
    Update an existing template.
    """
    if not current_user.is_superuser:
        raise HTTPException(status_code=403, detail="Not enough permissions")

    # 1. Get the DB object
    db_template = session.get(Template, id)
    if not db_template:
        raise HTTPException(status_code=404, detail="Template not found")

    file_contents = None
    file_name = None
    if file:
        # 2. Validate Content Type
        if file.content_type != "application/pdf":
            raise HTTPException(status_code=400, detail="File must be a PDF")

        # 3. Read the binary content
        file_contents = await file.read()
        file_name = file.filename

    # 4. Update via CRUD
    db_template = crud.update_template(session=session, db_template=db_template, file_contents=file_contents, file_name=file_name, owner_id=current_user.id)

    # 5. Re-run auto-configure if a new file was uploaded
    if file_contents:
        try:
            _auto_configure_template(session, db_template)
        except Exception as e:
            logging.warning(f"Auto-configure skipped for '{db_template.file_name}': {e}")
    else:
        logging.debug(f"No new file uploaded for template '{db_template.file_name}', skipping auto-configure.")

    # 6. Log the action
    crud.log_action(
        session=session,
        user=current_user.email,
        action=f"Updated template '{db_template.file_name}'"
    )
    session.commit()
    session.refresh(db_template)
    return db_template

@router.delete("/{id}")
def delete_template(session: SessionDep, current_user: CurrentUser, id: uuid.UUID) -> Any:
    """
    Delete a template.
    """
    template = session.get(Template, id)
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")
    if not current_user.is_superuser:
        raise HTTPException(status_code=403, detail="Not enough permissions")

    # Delete file from disk
    try:
        file_path = Path(template.file_path)
        if file_path.is_file():
            os.remove(file_path)
    except Exception as e:  # pragma: no cover
        logging.error(f"Error deleting template file: {e}")
    file_name = template.file_name

    # Delete prepared PDF if it exists
    if template.template_config:
        try:
            config = json.loads(template.template_config)
            tid = config.get("template_id", "")
            prepared = Path(__file__).resolve().parents[2] / "pdf_engine" / "prepared_templates" / f"{tid}_prepared.pdf"
            if prepared.is_file():
                os.remove(prepared)
        except Exception as e:
            logging.error(f"Error deleting prepared template file: {e}")

    session.delete(template)
    crud.log_action(
        session=session,
        user=current_user.email,
        action=f"Deleted template '{file_name}'"
    )
    session.commit()
    return None


def _fields_overlap(f1: dict, f2: dict) -> bool:
    """Check if two field dicts overlap significantly based on their bounding boxes."""
    if f1.get("page") != f2.get("page"):
        return False

    # Bounding box for f1
    x1_1, y1_1, w1, h1 = f1.get("x", 0), f1.get("y", 0), f1.get("width", 0), f1.get("height", 0)
    x2_1, y2_1 = x1_1 + w1, y1_1 + h1

    # Bounding box for f2
    x1_2, y1_2, w2, h2 = f2.get("x", 0), f2.get("y", 0), f2.get("width", 0), f2.get("height", 0)
    x2_2, y2_2 = x1_2 + w2, y1_2 + h2

    # Calculate intersection coordinates
    x_left = max(x1_1, x1_2)
    y_top = max(y1_1, y1_2)
    x_right = min(x2_1, x2_2)
    y_bottom = min(y2_1, y2_2)

    if x_right < x_left or y_bottom < y_top:
        return False  # No overlap

    # Calculate overlap area
    overlap_area = (x_right - x_left) * (y_bottom - y_top)

    # Calculate area of the smaller field
    area1 = w1 * h1
    area2 = w2 * h2
    smaller_area = min(area1, area2)

    if smaller_area == 0:
        return overlap_area > 0

    # Consider it an overlap if the overlap area is > 50% of the smaller field's area
    return (overlap_area / smaller_area) > 0.5


def _auto_configure_template(session, db_template) -> None:
    """Automatically analyze and configure an uploaded PDF template.

    Extracts AcroForm fields (or uses visual detection as fallback),
    auto-maps fields to patient data keys, and saves the configuration
    so the template is immediately available in the packet selector.
    """
    import shutil
    logging.debug(f"Starting auto-configuration for template ID: {db_template.file_id}, Name: {db_template.file_name}")

    file_path = Path(db_template.file_path)
    if not file_path.is_file():
        logging.debug(f"Template file not found at {file_path}. Aborting auto-configure.")
        return
    logging.debug(f"Template file found at: {file_path}")

    # Step 1: Attempting to extract AcroForm fields.
    acroform_fields = _extract_acroform_fields(file_path)
    logging.info(f"Extracted {len(acroform_fields)} AcroForm fields from '{db_template.file_name}'.")

    # Step 2: Always run visual analysis to find fields AcroForms might miss.
    visual_fields = []
    try:
        from app.pdf_engine.utils.pdf_analyzer import PDFAnalyzer
        analyzer = PDFAnalyzer(file_path)
        result = analyzer.analyze()
        visual_fields = [
            {
                "field_id": f.suggested_id,
                "acroform_name": f.suggested_id,
                "field_type": f.field_type,
                "page": f.page,
                "x": round(f.x, 2),
                "y": round(f.y, 2),
                "width": round(f.width, 2),
                "height": round(f.height, 2),
                "auto_map_key": _suggest_auto_map_key(f.suggested_id, f.field_type),
                "label": f.label or f.nearby_text,
            }
            for f in result.detected_fields
        ]
        logging.info(f"Visual analysis found {len(visual_fields)} potential fields.")
    except Exception as e:
        logging.warning(f"Visual analysis failed with error: {e}")

    # Step 3: Combine and deduplicate fields, prioritizing AcroForm fields.
    final_fields = list(acroform_fields)
    for v_field in visual_fields:
        is_duplicate = False
        for final_field in final_fields:
            if _fields_overlap(v_field, final_field):
                is_duplicate = True
                break
        if not is_duplicate:
            final_fields.append(v_field)
    fields = final_fields
    logging.info(f"Combined and deduplicated to {len(fields)} total fields.")

    form_name = db_template.file_name.replace(".pdf", "").replace(".PDF", "")
    template_id = f"uploaded_{db_template.file_id.hex[:12]}"
    file_label = _slugify(form_name) or template_id
    category = "Other"
    logging.debug(f"Generated template metadata: template_id='{template_id}', form_name='{form_name}', file_label='{file_label}'")
    
    template_config = {
        "template_id": template_id,
        "form_name": form_name,
        "file_label": file_label,
        "category": category,
        "source_pdf": db_template.file_name,
        "use_acroform": True,
        "show_dual_facility_header": False,
        "show_patient_id": False,
        "acroform_fields": [
            {
                "field_id": f.get("field_id", ""),
                "acroform_name": f.get("acroform_name", f.get("field_id", "")),
                "field_type": f.get("field_type", "text"),
                "auto_map_key": f.get("auto_map_key", ""),
                "page": f.get("page", 0),
                "x": f.get("x", 0),
                "y": f.get("y", 0),
                "width": f.get("width", 200),
                "height": f.get("height", 18),
                "font_size": f.get("font_size", 10),
                "multiline": f.get("multiline", False),
            }
            for f in fields
        ],
    }
    logging.debug(f"Constructed template_config with {len(fields)} fields.")

    # Save config to DB
    db_template.template_config = json.dumps(template_config)
    db_template.category = category
    logging.debug("Saved template_config and category to DB object.")

    # Copy the uploaded PDF as the prepared template
    prepared_dir = Path(__file__).resolve().parents[2] / "pdf_engine" / "prepared_templates"
    prepared_dir.mkdir(parents=True, exist_ok=True)
    prepared_path = prepared_dir / f"{template_id}_prepared.pdf"
    logging.debug(f"Copying source PDF from '{file_path}' to prepared path '{prepared_path}'.")
    shutil.copy2(str(file_path), str(prepared_path))

    session.add(db_template)
    session.commit()
    logging.debug("Committed changes to the database. Auto-configuration complete.")


def _slugify(text: str) -> str:
    """Convert text to a valid template ID slug."""
    text = text.lower().strip()
    text = re.sub(r"\.pdf$", "", text)
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"[\s-]+", "_", text)
    return text[:80]


def _extract_acroform_fields(pdf_path: Path) -> list[dict]:
    """Extract existing AcroForm fields from a PDF using pypdf."""
    from pypdf import PdfReader
    from pypdf.generic import DictionaryObject, ArrayObject

    try:
        # Use strict=False for better tolerance of malformed PDFs
        reader = PdfReader(str(pdf_path), strict=False)
    except Exception as e:
        logging.warning(f"pypdf failed to read PDF '{pdf_path.name}': {e}")
        return []

    fields = []
    logging.debug(f"PDF has {len(reader.pages)} pages. Checking for AcroForm fields...")

    # Use .get() for safe access to potentially missing keys
    root = reader.trailer.get("/Root")
    if not root:
        logging.debug("No /Root object found in PDF trailer.")
        return fields
    root = root.get_object()

    acroform = root.get("/AcroForm")
    if not acroform:
        logging.debug("No /AcroForm dictionary found in PDF's /Root object.")
        return fields
    acroform = acroform.get_object() if hasattr(acroform, "get_object") else acroform

    field_list = acroform.get("/Fields")
    if not field_list:
        logging.debug("No fields found in AcroForm.")
        return fields
    logging.debug(f"Found {len(field_list)} top-level field references in AcroForm.")
    field_list = field_list.get_object() if hasattr(field_list, "get_object") else field_list

    def _process_field(field_obj, page_num: int = 0):
        obj = field_obj.get_object() if hasattr(field_obj, "get_object") else field_obj
        if not isinstance(obj, DictionaryObject):
            logging.debug(f"Skipping field object of type {type(obj)}, not a DictionaryObject.")
            return

        name = str(obj.get("/T", ""))
        ft = str(obj.get("/FT", ""))
        logging.debug(f"Processing field: Name='{name}', Type='{ft}'")

        # Handle kids (hierarchical fields)
        kids = obj.get("/Kids")
        if kids:
            logging.debug(f"Field '{name}' has children (Kids). Processing them.")
            kids = kids.get_object() if hasattr(kids, "get_object") else kids
            if isinstance(kids, ArrayObject):
                for kid in kids:
                    _process_field(kid, page_num)
                return

        if not name:
            logging.debug("Skipping field with no name (/T key).")
            return

        # Determine field type
        if ft == "/Btn":
            field_type = "checkbox"
        elif ft == "/Sig":
            field_type = "signature"
        elif ft == "/Ch":
            field_type = "text"
        else:
            field_type = "text"
        logging.debug(f"Determined field_type as '{field_type}' for '{name}'.")

        # Get coordinates from /Rect if available
        rect = obj.get("/Rect")
        x, y, w, h = 0, 0, 200, 18
        if rect:
            rect = rect.get_object() if hasattr(rect, "get_object") else rect
            try:
                coords = [float(v) for v in rect]
                x = coords[0]
                y = coords[1]
                w = abs(coords[2] - coords[0])
                h = abs(coords[3] - coords[1])
                logging.debug(f"Extracted Rect for '{name}': [x={x}, y={y}, w={w}, h={h}]")
            except (ValueError, IndexError):
                logging.debug(f"Could not parse Rect for '{name}': {rect}")
                pass
        else:
            logging.debug(f"No Rect found for field '{name}'. Using default dimensions.")
        field_data = {
            "field_id": _slugify(name),
            "acroform_name": name,
            "field_type": field_type,
            "page": page_num,
            "x": round(x, 2),
            "y": round(y, 2),
            "width": round(w, 2),
            "height": round(h, 2),
            "auto_map_key": _suggest_auto_map_key(name, field_type),
            "label": name,
        }
        logging.debug(f"Appending field data for '{name}': {field_data}")
        fields.append(field_data)

    for field_ref in field_list:
        _process_field(field_ref)

    logging.debug(f"Finished processing. Total fields extracted: {len(fields)}")
    return fields


def _suggest_auto_map_key(field_name: str, field_type: str) -> str:
    """Suggest an auto_map_key based on field name heuristics."""
    lower = field_name.lower()
    if "patient" in lower and ("name" in lower or "client" in lower):
        return "patient_name"
    if "patient" in lower and "id" in lower:
        return "patient_id"
    if "date of birth" in lower or "dob" in lower or lower == "date_of_birth":
        return "date_of_birth"
    if "admission" in lower and "date" in lower:
        return "admission_date"
    if "counselor" in lower or "therapist" in lower:
        return "counselor_name"
    if "medical director" in lower or "physician" in lower:
        return "medical_director"
    if field_type == "checkbox" and "sample facility 1" in lower:
        return "facility_1"
    if field_type == "checkbox" and "sample facility 2" in lower:
        return "facility_2"
    if "date" in lower and field_type != "checkbox":
        return "today_date"
    return ""


@router.post("/{id}/analyze")
def analyze_template(
    session: SessionDep,
    current_user: CurrentUser,
    id: uuid.UUID,
) -> Any:
    """Analyze an uploaded PDF to extract its AcroForm fields.

    Returns detected fields that can be mapped to patient data keys.
    """
    if not current_user.is_superuser:
        raise HTTPException(status_code=403, detail="Not enough permissions")

    template = session.get(Template, id)
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")

    file_path = Path(template.file_path)
    if not file_path.is_file():
        raise HTTPException(status_code=404, detail="Template file not found on disk")

    # Step 1: Extract existing AcroForm fields
    acroform_fields = _extract_acroform_fields(file_path)

    # Step 2: Always run visual analysis
    visual_fields = []
    try:
        from app.pdf_engine.utils.pdf_analyzer import PDFAnalyzer
        analyzer = PDFAnalyzer(file_path)
        result = analyzer.analyze()
        visual_fields = [
            {
                "field_id": f.suggested_id,
                "acroform_name": f.suggested_id,
                "field_type": f.field_type,
                "page": f.page,
                "x": round(f.x, 2),
                "y": round(f.y, 2),
                "width": round(f.width, 2),
                "height": round(f.height, 2),
                "auto_map_key": _suggest_auto_map_key(f.suggested_id, f.field_type),
                "label": f.label or f.nearby_text,
                "confidence": f.confidence,
            }
            for f in result.detected_fields
        ]
    except Exception as e:
        # If visual analysis fails, we can still return the AcroForm fields
        logging.warning(f"Visual analysis failed during analyze endpoint: {e}")

    # Step 3: Combine and deduplicate
    final_fields = list(acroform_fields)
    for v_field in visual_fields:
        is_duplicate = False
        for final_field in final_fields:
            if _fields_overlap(v_field, final_field):
                is_duplicate = True
                break
        if not is_duplicate:
            final_fields.append(v_field)

    # Sort fields for consistent output
    final_fields.sort(key=lambda f: (f.get("page", 0), f.get("y", 0), f.get("x", 0)))
    
    # Available auto_map_keys the frontend can offer
    auto_map_keys = [
        {"key": "patient_id", "label": "Patient ID"},
        {"key": "patient_name", "label": "Patient Name"},
        {"key": "admission_date", "label": "Admission Date"},
        {"key": "today_date", "label": "Today's Date"},
        {"key": "facility_1", "label": "Facility: Sample Facility 1 (checkbox)"},
        {"key": "facility_2", "label": "Facility: Sample Facility 2 (checkbox)"},
        {"key": "date_of_birth", "label": "Date of Birth"},
        {"key": "counselor_name", "label": "Counselor Name"},
        {"key": "medical_director", "label": "Medical Director"},
    ]

    return {
        "template_id": str(template.file_id),
        "file_name": template.file_name,
        "fields": final_fields,
        "auto_map_keys": auto_map_keys,
    }


@router.post("/{id}/configure")
def configure_template(
    session: SessionDep,
    current_user: CurrentUser,
    id: uuid.UUID,
    config: dict[str, Any],
) -> Any:
    """Save field mappings and activate an uploaded template for use in packets.

    Expected body:
    {
        "form_name": "My Custom Form",
        "category": "Patient Intake",
        "fields": [
            {"field_id": "...", "acroform_name": "...", "field_type": "...",
             "auto_map_key": "patient_name", "page": 0, ...},
            ...
        ]
    }
    """
    if not current_user.is_superuser:
        raise HTTPException(status_code=403, detail="Not enough permissions")

    template = session.get(Template, id)
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")

    file_path = Path(template.file_path)
    if not file_path.is_file():
        raise HTTPException(status_code=404, detail="Template file not found on disk")

    form_name = config.get("form_name", template.file_name.replace(".pdf", ""))
    category = config.get("category", "Other")
    fields = config.get("fields", [])

    # Build template_id from file_id to ensure uniqueness
    template_id = f"uploaded_{template.file_id.hex[:12]}"
    file_label = _slugify(form_name) or template_id

    # Build full template config
    template_config = {
        "template_id": template_id,
        "form_name": form_name,
        "file_label": file_label,
        "category": category,
        "source_pdf": template.file_name,
        "use_acroform": True,
        "show_dual_facility_header": False,
        "show_patient_id": False,
        "acroform_fields": [
            {
                "field_id": f.get("field_id", ""),
                "acroform_name": f.get("acroform_name", f.get("field_id", "")),
                "field_type": f.get("field_type", "text"),
                "auto_map_key": f.get("auto_map_key", ""),
                "page": f.get("page", 0),
                "x": f.get("x", 0),
                "y": f.get("y", 0),
                "width": f.get("width", 200),
                "height": f.get("height", 18),
                "font_size": f.get("font_size", 10),
                "multiline": f.get("multiline", False),
            }
            for f in fields
        ],
    }

    # Save config to DB
    template.template_config = json.dumps(template_config)
    template.category = category

    # Copy the uploaded PDF as the prepared template
    prepared_dir = Path(__file__).resolve().parents[2] / "pdf_engine" / "prepared_templates"
    prepared_dir.mkdir(parents=True, exist_ok=True)
    prepared_path = prepared_dir / f"{template_id}_prepared.pdf"

    import shutil
    shutil.copy2(str(file_path), str(prepared_path))

    session.add(template)
    session.commit()
    session.refresh(template)

    crud.log_action(
        session=session,
        user=current_user.email,
        action=f"Configured template '{form_name}' for use in packets"
    )

    return {
        "success": True,
        "template_id": template_id,
        "form_name": form_name,
        "category": category,
        "field_count": len(fields),
    }
