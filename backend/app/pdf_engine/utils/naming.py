"""File naming convention utility for generated PDFs."""

import re
from datetime import date


def generate_filename(patient_id: str, file_label: str, form_date: str = "") -> str:
    """Generate a standardized PDF filename.

    Convention: {PatientID}_{FileLabel}_{YYYY-MM-DD}.pdf
    Example: P-10042_Consent_Methadone_Treatment_2026-02-10.pdf
    """
    # Sanitize patient_id: keep alphanumeric and hyphens only
    safe_id = re.sub(r"[^a-zA-Z0-9\-]", "", patient_id)

    if not form_date:
        form_date = date.today().strftime("%Y-%m-%d")

    return f"{safe_id}_{file_label}_{form_date}.pdf"
