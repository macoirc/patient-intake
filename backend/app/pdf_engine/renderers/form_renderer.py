"""Orchestrates rendering a FormTemplate + PatientData into a PDF.

Supports two rendering modes:
1. AcroForm mode: Uses prepared PDF templates with fillable fields (for PDF.js/pdf-lib compatibility)
2. Flat PDF mode: Generates PDFs from scratch using fpdf2 (fallback for templates without source PDFs)
"""

from pathlib import Path
from typing import Optional

from ..models.patient import PatientData, FACILITIES
from ..models.template import FormTemplate, FormField
from .document_builder import DocumentBuilder


# Maps field_ids to PatientData attributes for auto-population
AUTO_MAP = {
    "patient_name": "patient_name",
    "admission_date": "admission_date",
    "patient_id_display": "patient_id",
    "medical_director_name": "medical_director",
    "counselor_name": "counselor_name",
}


class FormRenderer:
    """Renders a single form template with patient data into a PDF.

    Automatically chooses between AcroForm filling (for templates with source_pdf
    and use_acroform=True) and flat PDF generation (fallback).
    """

    def __init__(
        self,
        template: FormTemplate,
        patient: PatientData,
        prepared_templates_dir: Optional[Path] = None,
    ):
        self.template = template
        self.patient = patient
        self.prepared_templates_dir = prepared_templates_dir
        self.builder = DocumentBuilder()  # For flat PDF fallback

    def should_use_acroform(self) -> bool:
        """Check if this template should use AcroForm filling."""
        if not self.template.use_acroform:
            return False

        # Check if prepared PDF exists (covers both built-in and uploaded templates)
        if self.prepared_templates_dir:
            prepared_path = self.prepared_templates_dir / f"{self.template.template_id}_prepared.pdf"
        else:
            base_dir = Path(__file__).parent.parent
            prepared_path = base_dir / "prepared_templates" / f"{self.template.template_id}_prepared.pdf"

        return prepared_path.exists()

    def resolve_value(self, field: FormField) -> str:
        """Resolve a field's value using priority: form_responses > auto-map > default."""
        # 1. Explicit form responses
        if field.field_id in self.patient.form_responses:
            return str(self.patient.form_responses[field.field_id])
        # 2. Auto-map from patient attributes
        if field.field_id in AUTO_MAP:
            val = getattr(self.patient, AUTO_MAP[field.field_id], "")
            return str(val) if val else ""
        # 3. Template default
        if field.default_value:
            return field.default_value
        return ""

    def render(self) -> DocumentBuilder:
        """Render the complete form and return the DocumentBuilder."""
        t = self.template
        b = self.builder

        # Revision date (top-right, drawn before other content)
        if t.revision_date:
            b.draw_revision_date(t.revision_date)

        # Dual facility header
        if t.show_dual_facility_header:
            b.draw_dual_facility_header(self.patient.facility, FACILITIES)

        # Patient ID line
        if t.show_patient_id:
            b.draw_patient_id_line(self.patient.patient_id)

        # Form title
        b.draw_form_title(t.form_name)

        # Header note
        if t.header_note:
            b.draw_header_note(t.header_note)

        # Sections
        for section in t.sections:
            self._render_section(section)

        # Signature blocks
        if t.signatures:
            b.y += 4  # extra space before signatures
            for sig in t.signatures:
                b.draw_signature_block(sig.signer_role, sig.include_date)

        return b

    def _render_section(self, section):
        """Render a single form section: heading, body_text, fields."""
        b = self.builder

        if section.heading:
            b.draw_section_heading(section.heading)

        if section.body_text:
            b.draw_paragraph(section.body_text)

        if section.fields:
            self._render_fields(section.fields)

    def _render_fields(self, fields: list[FormField]):
        """Render a list of fields, grouping inline fields on the same row."""
        b = self.builder
        i = 0
        while i < len(fields):
            field = fields[i]

            # Check for inline group
            if field.inline_group:
                group = []
                while i < len(fields) and fields[i].inline_group == field.inline_group:
                    group.append(fields[i])
                    i += 1
                self._render_inline_group(group)
            else:
                self._render_field(field)
                i += 1

    def _render_inline_group(self, fields: list[FormField]):
        """Render fields that share an inline_group on the same row."""
        b = self.builder
        lh = b._line_h()
        b.check_page_break(lh + 4)

        x = b.MARGIN
        for field in fields:
            w = b.CONTENT_W * field.width_ratio
            value = self.resolve_value(field)
            b.draw_text_field(field.label, value, width=w, x_offset=x)
            x += w

        b.y += lh + 3

    def _render_field(self, field: FormField):
        """Render a single form field based on its type."""
        b = self.builder
        value = self.resolve_value(field)

        if field.field_type == "text":
            b.draw_text_field(field.label, value)
            b.y += b._line_h() + 2

        elif field.field_type == "date":
            b.draw_text_field(field.label, value)
            b.y += b._line_h() + 2

        elif field.field_type == "textarea":
            if field.label:
                b.draw_section_heading(field.label)
            b.draw_textarea(value)

        elif field.field_type == "radio":
            b.draw_radio_field(field.label, field.options, value)

        elif field.field_type == "checkbox":
            checked = []
            if value:
                checked = [v.strip() for v in value.split(",")]
            b.draw_checkbox_field(field.label, field.options, checked)

    def render_to_bytes(self) -> bytes:
        """Render and return PDF as bytes.

        Uses AcroForm filling if available, otherwise generates flat PDF.
        """
        if self.should_use_acroform():
            return self._render_acroform_bytes()
        else:
            builder = self.render()
            return builder.get_bytes()

    def render_to_file(self, filepath: str):
        """Render and save PDF to a file.

        Uses AcroForm filling if available, otherwise generates flat PDF.
        """
        if self.should_use_acroform():
            pdf_bytes = self._render_acroform_bytes()
            Path(filepath).parent.mkdir(parents=True, exist_ok=True)
            with open(filepath, "wb") as f:
                f.write(pdf_bytes)
        else:
            builder = self.render()
            builder.save(filepath)

    def _render_acroform_bytes(self) -> bytes:
        """Render using AcroForm filling."""
        from .acroform_filler import AcroFormFiller

        filler = AcroFormFiller(
            template=self.template,
            patient=self.patient,
            prepared_templates_dir=self.prepared_templates_dir,
        )
        return filler.fill()
