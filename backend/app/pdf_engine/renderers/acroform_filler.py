"""AcroForm Filler - Fills prepared PDF templates with patient data.

This module takes a prepared PDF (with AcroForm fields) and fills it
with patient data, producing a fillable PDF that remains editable
in PDF.js and pdf-lib.
"""

from datetime import date
from pathlib import Path
from io import BytesIO
from typing import Optional

from pypdf import PdfReader, PdfWriter
from pypdf.generic import (
    ArrayObject,
    BooleanObject,
    DictionaryObject,
    FloatObject,
    IndirectObject,
    NameObject,
    NumberObject,
    TextStringObject,
)

from ..models.template import FormTemplate, AcroFormField
from ..models.patient import PatientData


class AcroFormFiller:
    """Fills AcroForm PDFs with patient data."""

    def __init__(
        self,
        template: FormTemplate,
        patient: PatientData,
        prepared_templates_dir: str | Path | None = None,
    ):
        self.template = template
        self.patient = patient

        base_dir = Path(__file__).parent.parent
        self.prepared_dir = (
            Path(prepared_templates_dir)
            if prepared_templates_dir
            else base_dir / "prepared_templates"
        )

    def get_prepared_pdf_path(self) -> Path:
        """Get the path to the prepared PDF template."""
        return self.prepared_dir / f"{self.template.template_id}_prepared.pdf"

    def fill(self) -> bytes:
        """Fill the prepared PDF template with patient data.

        Returns:
            PDF bytes with filled form fields
        """
        prepared_path = self.get_prepared_pdf_path()
        if not prepared_path.exists():
            raise FileNotFoundError(
                f"Prepared PDF not found: {prepared_path}. "
                f"Run template preparation first."
            )

        reader = PdfReader(prepared_path)
        writer = PdfWriter()
        writer.clone_document_from_reader(reader)

        # NeedAppearances=False: no cached /AP streams exist for text fields,
        # so the canvas renders nothing for those fields. The annotation layer
        # reads /V and shows the values as editable inputs (no doubling in PDF.js).
        if "/AcroForm" in writer._root_object:
            acroform = writer._root_object["/AcroForm"]
            acroform[NameObject("/NeedAppearances")] = BooleanObject(False)

        # Build field_name -> (value, field_type) map from template mappings
        fill_map = self._build_fill_map()

        # Build acroform_name -> AcroFormField lookup for rect overrides
        field_defs = {f.acroform_name: f for f in self.template.acroform_fields}

        # Split into text fields and checkbox fields
        text_fields = {}
        checkbox_fields = {}
        for field_name, (value, field_type) in fill_map.items():
            if field_type == "checkbox":
                checkbox_fields[field_name] = value
            else:
                text_fields[field_name] = str(value)

        # Fill ALL fields by walking every annotation on every page.
        # After clone_document_from_reader(), checkboxes may appear twice per
        # field name (widget + field dict) with different appearance state names
        # (/On vs /Yes). We must set /V consistently on ALL annotations for a
        # given field, and set /AS per-widget to match its own /AP/N on-state.
        for page in writer.pages:
            if "/Annots" not in page:
                continue
            annots = page["/Annots"]
            for annot in annots:
                annot_obj = annot.get_object() if hasattr(annot, "get_object") else annot
                if not isinstance(annot_obj, DictionaryObject):
                    continue
                if "/T" not in annot_obj:
                    continue

                field_name = str(annot_obj["/T"])

                # Determine field type from PDF
                ft = str(annot_obj.get("/FT", ""))

                # Apply rect override if JSON template specifies non-zero geometry
                field_def = field_defs.get(field_name)
                if field_def:
                    self._apply_rect_override(annot_obj, field_def)

                if field_name in checkbox_fields:
                    checked = checkbox_fields[field_name]
                    self._fill_checkbox(annot_obj, checked, field_def)
                elif field_name in text_fields:
                    self._fill_text(annot_obj, text_fields[field_name])
                elif ft == "/Tx":
                    # Unfilled text field: strip borders/background so it
                    # doesn't obscure printed content underneath
                    self._clean_text_field(annot_obj)

        output = BytesIO()
        writer.write(output)
        return output.getvalue()

    @staticmethod
    def _deref(obj):
        """Dereference IndirectObject wrappers to get the actual object."""
        if obj is None:
            return None
        if isinstance(obj, IndirectObject):
            return obj.get_object()
        return obj

    def _fill_checkbox(self, annot_obj: DictionaryObject, checked: bool, field_def=None):
        """Fill a checkbox annotation, detecting the correct 'on' appearance state.

        After clone_document_from_reader(), each checkbox field may have two
        annotations (widget + field dict) with different on-state names in
        their /AP/N dicts (/On vs /Yes). We set /AS to each widget's own
        on-state so the correct appearance stream is selected, and always
        set /V to /Yes for field-level consistency across all annotations.
        """
        if field_def and field_def.force_on_state:
            on_state = field_def.force_on_state
        else:
            on_state = self._get_checkbox_on_state(annot_obj)

        if checked:
            annot_obj[NameObject("/AS")] = NameObject(on_state)
            # /V must be consistent across all annotations for the same field.
            # Use /Yes as the canonical value — every checkbox has /Yes in at
            # least one of its duplicate annotations' /AP/N dicts.
            annot_obj[NameObject("/V")] = NameObject("/Yes")
        else:
            annot_obj[NameObject("/V")] = NameObject("/Off")
            annot_obj[NameObject("/AS")] = NameObject("/Off")

    def _get_checkbox_on_state(self, annot_obj: DictionaryObject) -> str:
        """Find the 'on' state name from a checkbox's appearance dict."""
        ap = self._deref(annot_obj.get("/AP"))
        if ap and isinstance(ap, DictionaryObject):
            n = self._deref(ap.get("/N"))
            if n and isinstance(n, DictionaryObject):
                for key in n.keys():
                    if key != "/Off":
                        return key
        return "/Yes"

    def _fill_text(self, annot_obj: DictionaryObject, value: str):
        """Fill a text field and clear its cached appearance so viewers regenerate it."""
        annot_obj[NameObject("/V")] = TextStringObject(value)
        # Set font size to 0 (auto-fit) so text scales to fit the field box
        da = str(annot_obj.get("/DA", ""))
        if da:
            import re
            # Replace existing font size with 0 (auto-size to fit field)
            da = re.sub(r"(\s)\d+(\.\d+)?(\s+Tf)", r"\g<1>0\3", da)
            annot_obj[NameObject("/DA")] = TextStringObject(da)
        # Remove border so the field doesn't obscure content underneath
        if "/BS" in annot_obj:
            del annot_obj[NameObject("/BS")]
        if "/Border" in annot_obj:
            del annot_obj[NameObject("/Border")]
        # Set zero-width border as fallback
        annot_obj[NameObject("/Border")] = ArrayObject(
            [NumberObject(0), NumberObject(0), NumberObject(0)]
        )
        # Remove background color / appearance characteristics
        if "/MK" in annot_obj:
            del annot_obj[NameObject("/MK")]
        # Remove cached appearance stream so the viewer rebuilds it
        # using the /V value and the NeedAppearances flag
        if "/AP" in annot_obj:
            del annot_obj[NameObject("/AP")]

    def _clean_text_field(self, annot_obj: DictionaryObject):
        """Strip borders and background from an unfilled text field."""
        if "/BS" in annot_obj:
            del annot_obj[NameObject("/BS")]
        if "/Border" in annot_obj:
            del annot_obj[NameObject("/Border")]
        annot_obj[NameObject("/Border")] = ArrayObject(
            [NumberObject(0), NumberObject(0), NumberObject(0)]
        )
        if "/MK" in annot_obj:
            del annot_obj[NameObject("/MK")]
        if "/AP" in annot_obj:
            del annot_obj[NameObject("/AP")]

    def _apply_rect_override(self, annot_obj: DictionaryObject, field_def: AcroFormField):
        """Override a field's /Rect when the JSON template specifies non-zero geometry."""
        if field_def.width > 0 and field_def.height > 0:
            annot_obj[NameObject("/Rect")] = ArrayObject([
                FloatObject(field_def.x),
                FloatObject(field_def.y),
                FloatObject(field_def.x + field_def.width),
                FloatObject(field_def.y + field_def.height),
            ])

    def fill_to_file(self, output_path: Path) -> Path:
        """Fill the template and save to a file."""
        pdf_bytes = self.fill()
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "wb") as f:
            f.write(pdf_bytes)
        return output_path

    def _build_fill_map(self) -> dict[str, tuple]:
        """Build a map of acroform_name -> (value, field_type)."""
        fill_map = {}

        for field_def in self.template.acroform_fields:
            value = self._resolve_value(field_def)
            if value is not None and value != "":
                fill_map[field_def.acroform_name] = (value, field_def.field_type)

        return fill_map

    def _resolve_value(self, field: AcroFormField):
        """Resolve a field's value from PatientData."""
        if field.auto_map_key:
            return self._resolve_auto_map(field.auto_map_key)

        if field.field_id in self.patient.form_responses:
            return str(self.patient.form_responses[field.field_id])

        return ""

    def _resolve_auto_map(self, key: str):
        """Resolve a value from an auto_map_key string."""
        p = self.patient

        if key == "patient_id":
            return p.patient_id
        if key == "patient_name":
            return p.patient_name
        if key == "admission_date":
            return p.admission_date
        if key == "today_date":
            return date.today().strftime("%m/%d/%Y")
        if key == "facility_nh":
            return p.facility == "new_horizons"
        if key == "facility_hs":
            return p.facility == "harbor_springs"
        if key == "date_of_birth":
            return p.date_of_birth
        if key == "counselor_name":
            return p.counselor_name
        if key == "medical_director":
            return p.medical_director

        return ""


def fill_template(
    template: FormTemplate,
    patient: PatientData,
    output_path: Optional[Path] = None,
) -> bytes | Path:
    """Convenience function to fill a template."""
    filler = AcroFormFiller(template, patient)

    if output_path:
        return filler.fill_to_file(output_path)
    return filler.fill()
