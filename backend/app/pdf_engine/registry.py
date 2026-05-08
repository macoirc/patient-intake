"""Template registry with auto-discovery of JSON form templates."""

import json
from pathlib import Path

from .models.template import FormTemplate


class TemplateRegistry:
    """Scans the form_templates directory and provides access to parsed templates.

    Also supports registering uploaded templates from the database via
    register_uploaded_template().
    """

    def __init__(self, templates_dir: str | Path | None = None):
        if templates_dir is None:
            templates_dir = Path(__file__).parent / "form_templates"
        self._templates_dir = Path(templates_dir)
        self._templates: dict[str, FormTemplate] = {}
        self._errors: dict[str, str] = {}
        self._load_all()

    def _load_all(self):
        """Scan for JSON files and parse each into a FormTemplate."""
        if not self._templates_dir.is_dir():
            return
        for json_file in sorted(self._templates_dir.glob("*.json")):
            try:
                with open(json_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                template = FormTemplate.from_dict(data)
                self._templates[template.template_id] = template
            except Exception as e:
                self._errors[json_file.stem] = str(e)

    def register_uploaded_template(self, config: dict) -> FormTemplate:
        """Register a template from an uploaded PDF's config JSON.

        Args:
            config: Dict with template_id, form_name, file_label, category,
                    use_acroform, acroform_fields, source_pdf, etc.

        Returns:
            The parsed FormTemplate.
        """
        template = FormTemplate.from_dict(config)
        self._templates[template.template_id] = template
        return template

    def load_uploaded_templates(self, db_templates: list) -> None:
        """Load all configured uploaded templates from DB model instances.

        Args:
            db_templates: List of Template model instances with non-null template_config.
        """
        for db_tpl in db_templates:
            if not db_tpl.template_config:
                continue
            try:
                config = json.loads(db_tpl.template_config)
                self.register_uploaded_template(config)
            except Exception as e:
                self._errors[f"uploaded_{db_tpl.file_id}"] = str(e)

    def get(self, template_id: str) -> FormTemplate | None:
        """Return a template by ID, or None if not found."""
        return self._templates.get(template_id)

    def list_templates(self) -> list[FormTemplate]:
        """Return all loaded templates."""
        return list(self._templates.values())

    @property
    def template_ids(self) -> list[str]:
        """Return all loaded template IDs."""
        return list(self._templates.keys())

    @property
    def load_errors(self) -> dict[str, str]:
        """Return any errors encountered during template loading."""
        return dict(self._errors)
