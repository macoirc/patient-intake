import io
import uuid

from fastapi.testclient import TestClient
from sqlmodel import Session

from app.core.config import settings

MINIMAL_PDF = b"%PDF-1.4\n1 0 obj\n<< /Type /Catalog >>\nendobj\nxref\n0 1\n0000000000 65535 f \ntrailer\n<< /Size 1 /Root 1 0 R >>\nstartxref\n9\n%%EOF"


def _pdf_file(name: str = "test.pdf") -> dict:
    return {"file": (name, io.BytesIO(MINIMAL_PDF), "application/pdf")}


def test_read_templates(
    client: TestClient, superuser_token_headers: dict[str, str]
) -> None:
    response = client.get(
        f"{settings.API_V1_STR}/templates/",
        headers=superuser_token_headers,
    )
    assert response.status_code == 200
    content = response.json()
    assert "data" in content
    assert "count" in content


def test_create_template(
    client: TestClient, superuser_token_headers: dict[str, str]
) -> None:
    response = client.post(
        f"{settings.API_V1_STR}/templates/",
        headers=superuser_token_headers,
        files=_pdf_file("create_test.pdf"),
    )
    assert response.status_code == 200
    content = response.json()
    assert content["file_name"] == "create_test.pdf"


def test_create_template_not_superuser(
    client: TestClient, normal_user_token_headers: dict[str, str]
) -> None:
    response = client.post(
        f"{settings.API_V1_STR}/templates/",
        headers=normal_user_token_headers,
        files=_pdf_file(),
    )
    assert response.status_code == 403


def test_create_template_not_pdf(
    client: TestClient, superuser_token_headers: dict[str, str]
) -> None:
    response = client.post(
        f"{settings.API_V1_STR}/templates/",
        headers=superuser_token_headers,
        files={"file": ("test.txt", io.BytesIO(b"not a pdf"), "text/plain")},
    )
    assert response.status_code == 400


def test_read_template(
    client: TestClient, superuser_token_headers: dict[str, str]
) -> None:
    create_resp = client.post(
        f"{settings.API_V1_STR}/templates/",
        headers=superuser_token_headers,
        files=_pdf_file("read_test.pdf"),
    )
    assert create_resp.status_code == 200
    template_id = create_resp.json()["file_id"]

    response = client.get(
        f"{settings.API_V1_STR}/templates/{template_id}",
        headers=superuser_token_headers,
    )
    assert response.status_code == 200
    assert response.content == MINIMAL_PDF


def test_read_template_not_found(
    client: TestClient, superuser_token_headers: dict[str, str]
) -> None:
    response = client.get(
        f"{settings.API_V1_STR}/templates/{uuid.uuid4()}",
        headers=superuser_token_headers,
    )
    assert response.status_code == 404


def test_update_template(
    client: TestClient, superuser_token_headers: dict[str, str]
) -> None:
    create_resp = client.post(
        f"{settings.API_V1_STR}/templates/",
        headers=superuser_token_headers,
        files=_pdf_file("before_update.pdf"),
    )
    assert create_resp.status_code == 200
    template_id = create_resp.json()["file_id"]

    new_content = MINIMAL_PDF + b" updated"
    response = client.put(
        f"{settings.API_V1_STR}/templates/{template_id}",
        headers=superuser_token_headers,
        files={"file": ("after_update.pdf", io.BytesIO(new_content), "application/pdf")},
    )
    assert response.status_code == 200
    content = response.json()
    assert content["file_name"] == "after_update.pdf"


def test_update_template_not_found(
    client: TestClient, superuser_token_headers: dict[str, str]
) -> None:
    response = client.put(
        f"{settings.API_V1_STR}/templates/{uuid.uuid4()}",
        headers=superuser_token_headers,
        files=_pdf_file(),
    )
    assert response.status_code == 404


def test_update_template_not_superuser(
    client: TestClient,
    superuser_token_headers: dict[str, str],
    normal_user_token_headers: dict[str, str],
) -> None:
    create_resp = client.post(
        f"{settings.API_V1_STR}/templates/",
        headers=superuser_token_headers,
        files=_pdf_file(),
    )
    template_id = create_resp.json()["file_id"]

    response = client.put(
        f"{settings.API_V1_STR}/templates/{template_id}",
        headers=normal_user_token_headers,
        files=_pdf_file(),
    )
    assert response.status_code == 403


def test_update_template_not_pdf(
    client: TestClient, superuser_token_headers: dict[str, str]
) -> None:
    create_resp = client.post(
        f"{settings.API_V1_STR}/templates/",
        headers=superuser_token_headers,
        files=_pdf_file(),
    )
    template_id = create_resp.json()["file_id"]

    response = client.put(
        f"{settings.API_V1_STR}/templates/{template_id}",
        headers=superuser_token_headers,
        files={"file": ("bad.txt", io.BytesIO(b"not pdf"), "text/plain")},
    )
    assert response.status_code == 400


def test_delete_template(
    client: TestClient, superuser_token_headers: dict[str, str]
) -> None:
    create_resp = client.post(
        f"{settings.API_V1_STR}/templates/",
        headers=superuser_token_headers,
        files=_pdf_file("to_delete.pdf"),
    )
    template_id = create_resp.json()["file_id"]

    response = client.delete(
        f"{settings.API_V1_STR}/templates/{template_id}",
        headers=superuser_token_headers,
    )
    assert response.status_code == 200


def test_delete_template_not_found(
    client: TestClient, superuser_token_headers: dict[str, str]
) -> None:
    response = client.delete(
        f"{settings.API_V1_STR}/templates/{uuid.uuid4()}",
        headers=superuser_token_headers,
    )
    assert response.status_code == 404


def test_delete_template_not_superuser(
    client: TestClient,
    superuser_token_headers: dict[str, str],
    normal_user_token_headers: dict[str, str],
) -> None:
    create_resp = client.post(
        f"{settings.API_V1_STR}/templates/",
        headers=superuser_token_headers,
        files=_pdf_file(),
    )
    template_id = create_resp.json()["file_id"]

    response = client.delete(
        f"{settings.API_V1_STR}/templates/{template_id}",
        headers=normal_user_token_headers,
    )
    assert response.status_code == 403
