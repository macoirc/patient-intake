import random

from fastapi.testclient import TestClient

from app.core.config import settings

PATIENT_BASE_URL = f"{settings.API_V1_STR}/patient"
REMINDERS_BASE_URL = f"{settings.API_V1_STR}/reminders"


def _create_patient(client: TestClient, headers: dict[str, str]) -> int:
    ehr_id = random.randint(100000, 999999)
    data = {
        "ehr_id": ehr_id,
        "session_start": "2026-01-01T09:00:00Z",
        "session_end": "2026-01-01T10:00:00Z",
        "session_status": "SCHEDULED",
    }
    resp = client.post(PATIENT_BASE_URL + "/", headers=headers, json=data)
    assert resp.status_code == 200
    return ehr_id


def test_get_reminder_status_not_found(
    client: TestClient, superuser_token_headers: dict[str, str]
) -> None:
    mid = _create_patient(client, superuser_token_headers)
    response = client.get(
        f"{REMINDERS_BASE_URL}/session_completed",
        params={"ehr_id": mid},
    )
    assert response.status_code == 200
    content = response.json()
    assert content["completed"] is False
    assert content["seen"] is False


def test_get_reminder_status_found(
    client: TestClient, superuser_token_headers: dict[str, str]
) -> None:
    mid = _create_patient(client, superuser_token_headers)
    key = "check_found"

    # mark complete so a state row exists
    client.post(
        f"{REMINDERS_BASE_URL}/{key}/complete",
        json={"ehr_id": mid},
    )

    response = client.get(
        f"{REMINDERS_BASE_URL}/{key}",
        params={"ehr_id": mid},
    )
    assert response.status_code == 200
    content = response.json()
    assert content["completed"] is True


def test_mark_reminder_complete_patient_not_found(
    client: TestClient,
) -> None:
    response = client.post(
        f"{REMINDERS_BASE_URL}/session_completed/complete",
        json={"ehr_id": 999999999},
    )
    assert response.status_code == 404


def test_mark_reminder_complete_creates_new(
    client: TestClient, superuser_token_headers: dict[str, str]
) -> None:
    mid = _create_patient(client, superuser_token_headers)
    response = client.post(
        f"{REMINDERS_BASE_URL}/new_reminder/complete",
        json={"ehr_id": mid},
    )
    assert response.status_code == 200
    content = response.json()
    assert content["ok"] is True
    assert content["completed_at"] is not None


def test_mark_reminder_complete_already_complete(
    client: TestClient, superuser_token_headers: dict[str, str]
) -> None:
    mid = _create_patient(client, superuser_token_headers)
    key = "already_done"

    # Complete it once
    r1 = client.post(
        f"{REMINDERS_BASE_URL}/{key}/complete",
        json={"ehr_id": mid},
    )
    assert r1.status_code == 200
    first_ts = r1.json()["completed_at"]

    # Complete it again — should not change completed_at
    r2 = client.post(
        f"{REMINDERS_BASE_URL}/{key}/complete",
        json={"ehr_id": mid},
    )
    assert r2.status_code == 200
    assert r2.json()["completed_at"] == first_ts


def test_mark_reminder_seen_not_completed(
    client: TestClient, superuser_token_headers: dict[str, str]
) -> None:
    mid = _create_patient(client, superuser_token_headers)
    response = client.post(
        f"{REMINDERS_BASE_URL}/not_done_yet/seen",
        json={"ehr_id": mid},
    )
    assert response.status_code == 400


def test_mark_reminder_seen_success(
    client: TestClient, superuser_token_headers: dict[str, str]
) -> None:
    mid = _create_patient(client, superuser_token_headers)
    key = "see_me"

    # Complete first
    client.post(
        f"{REMINDERS_BASE_URL}/{key}/complete",
        json={"ehr_id": mid},
    )

    # Now mark as seen
    response = client.post(
        f"{REMINDERS_BASE_URL}/{key}/seen",
        json={"ehr_id": mid},
    )
    assert response.status_code == 200
    content = response.json()
    assert content["ok"] is True
    assert content["seen_at"] is not None
