import csv
import datetime
from io import StringIO

from fastapi.testclient import TestClient

from app.api.routes.report import _build_csv_report
from app.core.config import settings

REPORTS_BASE_URL = f"{settings.API_V1_STR}/reports"

# ---------------------------------------------------------------------------
# Unit tests — _build_csv_report
# ---------------------------------------------------------------------------

def _parse_csv(output: StringIO) -> list[list[str]]:
    return list(csv.reader(output))


def test_build_csv_report_section_headers() -> None:
    output = _build_csv_report(1.5, [], [], datetime.date(2026, 1, 1))
    rows = _parse_csv(output)
    first_cells = [r[0] for r in rows if r]
    assert "Section: Incomplete Patients" in first_cells
    assert "Section: Missing Forms by Type" in first_cells
    assert "Section: Summary" in first_cells


def test_build_csv_report_patient_rows() -> None:
    patients = ["P001", "P002", "P003"]
    output = _build_csv_report(None, patients, [], datetime.date(2026, 1, 1))
    rows = _parse_csv(output)
    all_cells = [cell for row in rows for cell in row]
    for pid in patients:
        assert pid in all_cells


def test_build_csv_report_form_rows() -> None:
    forms = [{"form_name": "Consent", "count": 3}, {"form_name": "Intake", "count": 7}]
    output = _build_csv_report(None, [], forms, datetime.date(2026, 1, 1))
    rows = _parse_csv(output)
    all_cells = [cell for row in rows for cell in row]
    assert "Consent" in all_cells
    assert "3" in all_cells
    assert "Intake" in all_cells
    assert "7" in all_cells


def test_build_csv_report_avg_duration_value() -> None:
    output = _build_csv_report(4.125, [], [], datetime.date(2026, 1, 1))
    rows = _parse_csv(output)
    all_cells = [cell for row in rows for cell in row]
    assert "4.125" in all_cells


def test_build_csv_report_avg_duration_none() -> None:
    output = _build_csv_report(None, [], [], datetime.date(2026, 1, 1))
    rows = _parse_csv(output)
    all_cells = [cell for row in rows for cell in row]
    assert "N/A" in all_cells


def test_build_csv_report_empty_lists() -> None:
    output = _build_csv_report(None, [], [], datetime.date(2026, 1, 1))
    rows = _parse_csv(output)
    # Should not raise and must produce at least the column headers
    first_cells = [r[0] for r in rows if r]
    assert "patient_id" in first_cells
    assert "form_name" in first_cells
    assert "metric" in first_cells


def test_build_csv_report_date() -> None:
    report_date = datetime.date(2026, 4, 23)
    output = _build_csv_report(None, [], [], report_date)
    rows = _parse_csv(output)
    all_cells = [cell for row in rows for cell in row]
    assert report_date.isoformat() in all_cells


def test_build_csv_report_seeked_to_start() -> None:
    output = _build_csv_report(1.0, ["P1"], [], datetime.date(2026, 1, 1))
    assert output.tell() == 0


# ---------------------------------------------------------------------------
# Integration tests — GET /reports/download-csv
# ---------------------------------------------------------------------------

def test_download_csv_unauthenticated(client: TestClient) -> None:
    response = client.get(f"{REPORTS_BASE_URL}/download-csv")
    assert response.status_code == 401


def test_download_csv_normal_user_forbidden(
    client: TestClient, normal_user_token_headers: dict[str, str]
) -> None:
    response = client.get(
        f"{REPORTS_BASE_URL}/download-csv", headers=normal_user_token_headers
    )
    assert response.status_code == 403


def test_download_csv_superuser_returns_200(
    client: TestClient, superuser_token_headers: dict[str, str]
) -> None:
    response = client.get(
        f"{REPORTS_BASE_URL}/download-csv", headers=superuser_token_headers
    )
    assert response.status_code == 200


def test_download_csv_content_type(
    client: TestClient, superuser_token_headers: dict[str, str]
) -> None:
    response = client.get(
        f"{REPORTS_BASE_URL}/download-csv", headers=superuser_token_headers
    )
    assert response.headers["content-type"].startswith("text/csv")


def test_download_csv_content_disposition(
    client: TestClient, superuser_token_headers: dict[str, str]
) -> None:
    response = client.get(
        f"{REPORTS_BASE_URL}/download-csv", headers=superuser_token_headers
    )
    disposition = response.headers.get("content-disposition", "")
    assert "attachment" in disposition
    assert ".csv" in disposition


def test_download_csv_body_contains_sections(
    client: TestClient, superuser_token_headers: dict[str, str]
) -> None:
    response = client.get(
        f"{REPORTS_BASE_URL}/download-csv", headers=superuser_token_headers
    )
    body = response.text
    assert "Section: Incomplete Patients" in body
    assert "Section: Missing Forms by Type" in body
    assert "Section: Summary" in body
