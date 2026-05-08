"""Form template models parsed from JSON definitions."""

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class AcroFormField:
    """An AcroForm field definition for filling existing PDF fields."""

    field_id: str  # Internal key used by the filler
    acroform_name: str  # Exact field name in the PDF AcroForm
    page: int = 0  # 0-indexed page number
    x: float = 0  # X coordinate (not needed for filling existing fields)
    y: float = 0  # Y coordinate (not needed for filling existing fields)
    width: float = 0  # Field width (not needed for filling existing fields)
    height: float = 0  # Field height (not needed for filling existing fields)
    field_type: str = "text"  # text, checkbox, radio, signature
    font_size: int = 10  # Font size for text fields
    multiline: bool = False  # For text fields that need multiple lines
    auto_map_key: str = ""  # Maps to PatientData attribute (e.g. "patient_id", "facility_nh")
    force_on_state: str = ""  # Force a specific checkbox on-state (e.g. "/On", "/Yes")

    @staticmethod
    def from_dict(data: dict) -> "AcroFormField":
        return AcroFormField(
            field_id=data["field_id"],
            acroform_name=data.get("acroform_name", data["field_id"]),
            page=data.get("page", 0),
            x=data.get("x", 0),
            y=data.get("y", 0),
            width=data.get("width", 0),
            height=data.get("height", 0),
            field_type=data.get("field_type", "text"),
            font_size=data.get("font_size", 10),
            multiline=data.get("multiline", False),
            auto_map_key=data.get("auto_map_key", ""),
            force_on_state=data.get("force_on_state", ""),
        )

    def to_dict(self) -> dict:
        d = {
            "field_id": self.field_id,
            "acroform_name": self.acroform_name,
            "page": self.page,
            "x": self.x,
            "y": self.y,
            "width": self.width,
            "height": self.height,
            "field_type": self.field_type,
            "font_size": self.font_size,
            "multiline": self.multiline,
        }
        if self.auto_map_key:
            d["auto_map_key"] = self.auto_map_key
        if self.force_on_state:
            d["force_on_state"] = self.force_on_state
        return d


@dataclass
class FormField:
    """A single input field within a form section."""

    field_id: str
    label: str
    field_type: str = "text"  # text, textarea, checkbox, radio, date
    required: bool = False
    options: list = field(default_factory=list)
    default_value: str = ""
    width_ratio: float = 1.0
    inline_group: str = ""

    @staticmethod
    def from_dict(data: dict) -> "FormField":
        return FormField(
            field_id=data["field_id"],
            label=data.get("label", ""),
            field_type=data.get("field_type", "text"),
            required=data.get("required", False),
            options=data.get("options", []),
            default_value=data.get("default_value", ""),
            width_ratio=data.get("width_ratio", 1.0),
            inline_group=data.get("inline_group", ""),
        )


@dataclass
class SignatureBlock:
    """A signature line on the form."""

    signer_role: str
    field_id: str
    include_date: bool = True

    @staticmethod
    def from_dict(data: dict) -> "SignatureBlock":
        return SignatureBlock(
            signer_role=data["signer_role"],
            field_id=data["field_id"],
            include_date=data.get("include_date", True),
        )


@dataclass
class FormSection:
    """A logical section of a form with optional heading, body text, and fields."""

    heading: Optional[str] = None
    body_text: Optional[str] = None
    fields: list = field(default_factory=list)  # list of FormField

    @staticmethod
    def from_dict(data: dict) -> "FormSection":
        fields = [FormField.from_dict(f) for f in data.get("fields", [])]
        return FormSection(
            heading=data.get("heading"),
            body_text=data.get("body_text"),
            fields=fields,
        )


@dataclass
class FormTemplate:
    """Complete form template definition loaded from JSON."""

    template_id: str
    form_name: str
    file_label: str
    revision_date: str = ""
    category: str = "Other"  # For grouping in UI
    sections: list = field(default_factory=list)  # list of FormSection
    signatures: list = field(default_factory=list)  # list of SignatureBlock
    show_dual_facility_header: bool = True
    show_patient_id: bool = True
    header_note: Optional[str] = None
    # AcroForm support fields
    source_pdf: str = ""  # Filename of source PDF (e.g., "Consent_for_Methadone_Treatment.pdf")
    acroform_fields: list = field(default_factory=list)  # list of AcroFormField
    use_acroform: bool = False  # True = use AcroForm filling, False = generate flat PDF

    @staticmethod
    def from_dict(data: dict) -> "FormTemplate":
        sections = [FormSection.from_dict(s) for s in data.get("sections", [])]
        signatures = [SignatureBlock.from_dict(s) for s in data.get("signatures", [])]
        acroform_fields = [AcroFormField.from_dict(f) for f in data.get("acroform_fields", [])]
        return FormTemplate(
            template_id=data["template_id"],
            form_name=data["form_name"],
            file_label=data["file_label"],
            revision_date=data.get("revision_date", ""),
            category=data.get("category", "Other"),
            sections=sections,
            signatures=signatures,
            show_dual_facility_header=data.get("show_dual_facility_header", True),
            show_patient_id=data.get("show_patient_id", True),
            header_note=data.get("header_note"),
            source_pdf=data.get("source_pdf", ""),
            acroform_fields=acroform_fields,
            use_acroform=data.get("use_acroform", False),
        )

    def to_dict(self) -> dict:
        """Serialize template to dictionary for JSON export."""
        return {
            "template_id": self.template_id,
            "form_name": self.form_name,
            "file_label": self.file_label,
            "revision_date": self.revision_date,
            "category": self.category,
            "show_dual_facility_header": self.show_dual_facility_header,
            "show_patient_id": self.show_patient_id,
            "header_note": self.header_note,
            "source_pdf": self.source_pdf,
            "use_acroform": self.use_acroform,
            "acroform_fields": [f.to_dict() for f in self.acroform_fields],
            "sections": [
                {
                    "heading": s.heading,
                    "body_text": s.body_text,
                    "fields": [
                        {
                            "field_id": f.field_id,
                            "label": f.label,
                            "field_type": f.field_type,
                            "required": f.required,
                            "options": f.options,
                            "default_value": f.default_value,
                        }
                        for f in s.fields
                    ],
                }
                for s in self.sections
            ],
            "signatures": [
                {
                    "signer_role": s.signer_role,
                    "field_id": s.field_id,
                    "include_date": s.include_date,
                }
                for s in self.signatures
            ],
        }
