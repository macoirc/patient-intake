"""Template Preparer - Adds AcroForm fields to source PDFs.

This module takes a source PDF and field definitions, then creates
a prepared PDF with interactive AcroForm fields that can be filled
by PDF.js and pdf-lib.
"""

import json
from pathlib import Path
from typing import Optional

from pypdf import PdfReader, PdfWriter
from pypdf.annotations import FreeText
from pypdf.generic import (
    ArrayObject,
    BooleanObject,
    DictionaryObject,
    NameObject,
    NumberObject,
    TextStringObject,
    IndirectObject,
)

from ..models.template import AcroFormField, FormTemplate


# Standard PDF field flags
FIELD_FLAG_READONLY = 1
FIELD_FLAG_REQUIRED = 2
FIELD_FLAG_MULTILINE = 1 << 12  # For text fields


class TemplatePreparer:
    """Prepares PDF templates by adding AcroForm fields."""

    def __init__(
        self,
        source_pdfs_dir: str | Path | None = None,
        prepared_dir: str | Path | None = None,
    ):
        """
        Initialize the preparer.

        Args:
            source_pdfs_dir: Directory containing source PDFs
            prepared_dir: Directory to save prepared PDFs
        """
        base_dir = Path(__file__).parent.parent
        self.source_pdfs_dir = Path(source_pdfs_dir) if source_pdfs_dir else base_dir / "source_pdfs"
        self.prepared_dir = Path(prepared_dir) if prepared_dir else base_dir / "prepared_templates"

        # Ensure directories exist
        self.source_pdfs_dir.mkdir(parents=True, exist_ok=True)
        self.prepared_dir.mkdir(parents=True, exist_ok=True)

    def prepare_from_template(self, template: FormTemplate) -> Path:
        """
        Prepare a PDF from a FormTemplate definition.

        If the source PDF already has AcroForm fields, just copies it
        (avoids adding duplicate fields on top of existing ones).

        Args:
            template: FormTemplate with source_pdf and acroform_fields

        Returns:
            Path to the prepared PDF

        Raises:
            FileNotFoundError: If source PDF doesn't exist
        """
        import shutil

        if not template.source_pdf:
            raise ValueError(f"Template {template.template_id} has no source_pdf defined")

        source_path = self.source_pdfs_dir / template.source_pdf
        if not source_path.exists():
            raise FileNotFoundError(f"Source PDF not found: {source_path}")

        output_path = self.prepared_dir / f"{template.template_id}_prepared.pdf"

        # If source PDF already has AcroForm fields or no fields to add, just copy as-is
        reader = PdfReader(source_path)
        existing_fields = reader.get_fields()
        if existing_fields or not template.acroform_fields:
            shutil.copy(source_path, output_path)
            return output_path

        return self.prepare_pdf(source_path, template.acroform_fields, output_path)

    def prepare_pdf(
        self,
        source_path: Path,
        fields: list[AcroFormField],
        output_path: Path,
    ) -> Path:
        """
        Add AcroForm fields to a PDF.

        Args:
            source_path: Path to source PDF
            fields: List of AcroFormField definitions
            output_path: Path to save prepared PDF

        Returns:
            Path to the prepared PDF
        """
        reader = PdfReader(source_path)
        writer = PdfWriter()

        # Copy all pages from source
        for page in reader.pages:
            writer.add_page(page)

        # Create AcroForm if it doesn't exist
        if "/AcroForm" not in writer._root_object:
            writer._root_object[NameObject("/AcroForm")] = DictionaryObject()

        acroform = writer._root_object["/AcroForm"]
        if not isinstance(acroform, DictionaryObject):
            acroform = DictionaryObject()
            writer._root_object[NameObject("/AcroForm")] = acroform

        # Set NeedAppearances to true for better compatibility
        acroform[NameObject("/NeedAppearances")] = BooleanObject(True)

        # Initialize fields array if needed
        if "/Fields" not in acroform:
            acroform[NameObject("/Fields")] = ArrayObject()

        # Add each field
        for field_def in fields:
            self._add_field(writer, field_def)

        # Save the prepared PDF
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "wb") as f:
            writer.write(f)

        return output_path

    def _add_field(self, writer: PdfWriter, field_def: AcroFormField):
        """Add a single AcroForm field to the PDF."""
        page_num = field_def.page
        if page_num >= len(writer.pages):
            return  # Skip if page doesn't exist

        page = writer.pages[page_num]
        page_obj = page.indirect_reference

        # Get page dimensions for coordinate conversion
        media_box = page.mediabox
        page_height = float(media_box.height)

        # Create field dictionary
        field_dict = DictionaryObject()

        # Common field properties
        field_dict[NameObject("/T")] = TextStringObject(field_def.acroform_name)
        field_dict[NameObject("/P")] = page_obj

        # Field rectangle [x1, y1, x2, y2] - PDF coordinates from bottom-left
        rect = ArrayObject([
            NumberObject(field_def.x),
            NumberObject(field_def.y),
            NumberObject(field_def.x + field_def.width),
            NumberObject(field_def.y + field_def.height),
        ])
        field_dict[NameObject("/Rect")] = rect

        # Field type-specific setup
        if field_def.field_type == "checkbox":
            self._setup_checkbox_field(field_dict)
        elif field_def.field_type == "radio":
            self._setup_radio_field(field_dict)
        elif field_def.field_type == "signature":
            self._setup_signature_field(field_dict)
        else:  # text, date
            self._setup_text_field(field_dict, field_def)

        # Add annotation flags (make it visible and printable)
        field_dict[NameObject("/F")] = NumberObject(4)  # Print flag

        # Add field to page annotations
        if "/Annots" not in page:
            page[NameObject("/Annots")] = ArrayObject()

        annots = page["/Annots"]
        if isinstance(annots, IndirectObject):
            annots = annots.get_object()

        # Add field as indirect reference
        field_ref = writer._add_object(field_dict)
        annots.append(field_ref)

        # Add to AcroForm fields array
        acroform = writer._root_object["/AcroForm"]
        fields_array = acroform["/Fields"]
        if isinstance(fields_array, IndirectObject):
            fields_array = fields_array.get_object()
        fields_array.append(field_ref)

    def _setup_text_field(self, field_dict: DictionaryObject, field_def: AcroFormField):
        """Configure a text field."""
        field_dict[NameObject("/FT")] = NameObject("/Tx")  # Text field type
        field_dict[NameObject("/V")] = TextStringObject("")  # Empty default value

        # Field flags
        flags = 0
        if field_def.multiline:
            flags |= FIELD_FLAG_MULTILINE
        field_dict[NameObject("/Ff")] = NumberObject(flags)

        # Default appearance string (required for text fields)
        # Format: "/FontName FontSize Tf Color rg"
        da = f"/Helv {field_def.font_size} Tf 0 0 0 rg"
        field_dict[NameObject("/DA")] = TextStringObject(da)

        # Border style
        border_dict = DictionaryObject()
        border_dict[NameObject("/W")] = NumberObject(1)  # Border width
        border_dict[NameObject("/S")] = NameObject("/S")  # Solid border
        field_dict[NameObject("/BS")] = border_dict

        # Make field editable (widget annotation type)
        field_dict[NameObject("/Subtype")] = NameObject("/Widget")
        field_dict[NameObject("/Type")] = NameObject("/Annot")

    def _setup_checkbox_field(self, field_dict: DictionaryObject):
        """Configure a checkbox field."""
        field_dict[NameObject("/FT")] = NameObject("/Btn")  # Button field type
        field_dict[NameObject("/V")] = NameObject("/Off")  # Default off

        # Checkbox-specific flags (not pushbutton, not radio)
        field_dict[NameObject("/Ff")] = NumberObject(0)

        # Appearance states
        ap_dict = DictionaryObject()
        n_dict = DictionaryObject()
        n_dict[NameObject("/Off")] = NameObject("/Off")
        n_dict[NameObject("/Yes")] = NameObject("/Yes")
        ap_dict[NameObject("/N")] = n_dict
        field_dict[NameObject("/AP")] = ap_dict

        # Mark as widget
        field_dict[NameObject("/Subtype")] = NameObject("/Widget")
        field_dict[NameObject("/Type")] = NameObject("/Annot")

    def _setup_radio_field(self, field_dict: DictionaryObject):
        """Configure a radio button field."""
        field_dict[NameObject("/FT")] = NameObject("/Btn")
        field_dict[NameObject("/V")] = NameObject("/Off")

        # Radio button flags (bit 15 = radio, bit 16 = no toggle to off)
        flags = (1 << 15) | (1 << 16)
        field_dict[NameObject("/Ff")] = NumberObject(flags)

        field_dict[NameObject("/Subtype")] = NameObject("/Widget")
        field_dict[NameObject("/Type")] = NameObject("/Annot")

    def _setup_signature_field(self, field_dict: DictionaryObject):
        """Configure a signature field (placeholder for image)."""
        # Signature fields are typically text fields or dedicated /Sig types
        # For compatibility with pdf-lib image placement, use text field
        field_dict[NameObject("/FT")] = NameObject("/Tx")
        field_dict[NameObject("/V")] = TextStringObject("")
        field_dict[NameObject("/Ff")] = NumberObject(0)
        field_dict[NameObject("/DA")] = TextStringObject("/Helv 10 Tf 0 0 0 rg")
        field_dict[NameObject("/Subtype")] = NameObject("/Widget")
        field_dict[NameObject("/Type")] = NameObject("/Annot")


def prepare_template(template: FormTemplate, source_dir: Path = None, output_dir: Path = None) -> Path:
    """
    Convenience function to prepare a template.

    Args:
        template: FormTemplate with source_pdf and acroform_fields
        source_dir: Optional source PDFs directory
        output_dir: Optional output directory

    Returns:
        Path to prepared PDF
    """
    preparer = TemplatePreparer(source_dir, output_dir)
    return preparer.prepare_from_template(template)


def generate_template_json(
    template_id: str,
    form_name: str,
    file_label: str,
    source_pdf: str,
    detected_fields: list,
) -> dict:
    """
    Generate a complete template JSON from detected fields.

    Args:
        template_id: Unique template identifier
        form_name: Display name
        file_label: Label for filename
        source_pdf: Source PDF filename
        detected_fields: List of DetectedField objects or dicts

    Returns:
        Complete template dictionary ready for JSON serialization
    """
    acroform_fields = []
    for field in detected_fields:
        if isinstance(field, dict):
            acroform_fields.append({
                "field_id": field["suggested_id"],
                "acroform_name": field["suggested_id"],
                "page": field["page"],
                "x": field["x"],
                "y": field["y"],
                "width": field["width"],
                "height": field["height"],
                "field_type": field["field_type"],
            })
        else:
            acroform_fields.append({
                "field_id": field.suggested_id,
                "acroform_name": field.suggested_id,
                "page": field.page,
                "x": field.x,
                "y": field.y,
                "width": field.width,
                "height": field.height,
                "field_type": field.field_type,
            })

    return {
        "template_id": template_id,
        "form_name": form_name,
        "file_label": file_label,
        "source_pdf": source_pdf,
        "use_acroform": True,
        "show_dual_facility_header": False,
        "show_patient_id": False,
        "acroform_fields": acroform_fields,
        "sections": [],
        "signatures": [],
    }
