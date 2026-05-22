import random

from fastapi.testclient import TestClient

from app.core.config import settings

BASE_URL = f"{settings.API_V1_STR}/patient"

PATIENT_PAYLOAD = {
    "ehr_id": None,  # set per test
    "session_start": "2026-01-01T09:00:00Z",
    "session_end": "2026-01-01T10:00:00Z",
    "session_status": "SCHEDULED",
}


def _patient_data(ehr_id: int | None = None) -> dict:
    data = dict(PATIENT_PAYLOAD)
    data["ehr_id"] = ehr_id or random.randint(100000, 999999)
    return data


def test_create_patient(
    client: TestClient, superuser_token_headers: dict[str, str]
) -> None:
    data = _patient_data()
    response = client.post(BASE_URL + "/", headers=superuser_token_headers, json=data)
    assert response.status_code == 200
    content = response.json()
    assert content["ehr_id"] == data["ehr_id"]
    assert content["session_status"] == data["session_status"]


def test_create_patient_duplicate(
    client: TestClient, superuser_token_headers: dict[str, str]
) -> None:
    data = _patient_data()
    # First creation
    r1 = client.post(BASE_URL + "/", headers=superuser_token_headers, json=data)
    assert r1.status_code == 200

    # Duplicate
    r2 = client.post(BASE_URL + "/", headers=superuser_token_headers, json=data)
    assert r2.status_code == 400
    assert "already exists" in r2.json()["detail"]
