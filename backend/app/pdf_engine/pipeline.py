"""Intake packet generation pipeline."""

from dataclasses import dataclass
from pathlib import Path

from .models.patient import PatientData
from .models.template import FormTemplate
from .registry import TemplateRegistry
from .renderers.form_renderer import FormRenderer
from .utils.naming import generate_filename


@dataclass
class GenerationResult:
    """Result of a single form generation attempt."""

    template_id: str
    form_name: str
    filepath: str = ""
    success: bool = False
    error: str = ""


class IntakePacketGenerator:
    """Main entry point for generating PDF intake forms.

    Initializes the template registry and provides methods to generate
    individual forms or complete intake packets.
    """

    def __init__(self, db_templates: list | None = None):
        self.registry = TemplateRegistry()
        if db_templates:
            self.registry.load_uploaded_templates(db_templates)

    def list_available_forms(self) -> list[dict]:
        """Return a list of template summaries for the UI."""
        return [
            {
                "template_id": t.template_id,
                "form_name": t.form_name,
                "file_label": t.file_label,
                "category": t.category,
            }
            for t in self.registry.list_templates()
        ]

    def generate_form(
        self, template_id: str, patient: PatientData, output_dir: str | Path
    ) -> GenerationResult:
        """Generate a single PDF form and save it to output_dir."""
        template = self.registry.get(template_id)
        if template is None:
            return GenerationResult(
                template_id=template_id,
                form_name="Unknown",
                error=f"Template '{template_id}' not found",
            )

        try:
            output_dir = Path(output_dir)
            output_dir.mkdir(parents=True, exist_ok=True)

            filename = generate_filename(patient.patient_id, template.file_label)
            filepath = output_dir / filename

            renderer = FormRenderer(template, patient)
            renderer.render_to_file(str(filepath))

            return GenerationResult(
                template_id=template_id,
                form_name=template.form_name,
                filepath=str(filepath),
                success=True,
            )
        except Exception as e:
            return GenerationResult(
                template_id=template_id,
                form_name=template.form_name,
                error=str(e),
            )

    def generate_packet(
        self,
        patient: PatientData,
        output_dir: str | Path,
        template_ids: list[str] | None = None,
    ) -> list[GenerationResult]:
        """Generate multiple forms. If template_ids is None, generates all."""
        ids = template_ids or self.registry.template_ids
        return [self.generate_form(tid, patient, output_dir) for tid in ids]

    def generate_form_bytes(self, template_id: str, patient: PatientData) -> bytes:
        """Generate a PDF and return raw bytes (for StorageService integration)."""
        template = self.registry.get(template_id)
        if template is None:
            raise ValueError(f"Template '{template_id}' not found")

        renderer = FormRenderer(template, patient)
        return renderer.render_to_bytes()
