import os

from tests.conftest import auth_header


def zone_payload() -> dict:
    return {
        "name": "Bodega",
        "polygon": [[0.1, 0.1], [0.8, 0.1], [0.8, 0.9]],
        "schedule": {
            "timezone": "America/Guatemala",
            "windows": [{"days": ["mon", "tue", "wed", "thu", "fri"], "start": "08:00", "end": "18:00"}],
        },
        "rule_type": "intrusion",
        "rule_params": {},
    }


def test_bootstrap_admin_can_log_in(client) -> None:
    response = client.post(
        "/auth/login",
        json={"email": os.environ["BOOTSTRAP_ADMIN_EMAIL"], "password": os.environ["BOOTSTRAP_ADMIN_PASSWORD"]},
    )
    assert response.status_code == 200
    assert response.json()["token_type"] == "bearer"


def test_health(client) -> None:
    response = client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["postgres"] == "ok"
    assert body["redis"] == "ok"
    assert body["minio"] == "ok"


def test_organizations_cannot_see_each_other(client, accounts) -> None:
    first = accounts()
    second = accounts()
    first_headers = auth_header(client, first)
    second_headers = auth_header(client, second)
    created = client.post("/sites", json={"name": "Planta norte", "address": "Mixco"}, headers=first_headers)
    assert created.status_code == 201
    site_id = created.json()["id"]
    hidden = client.get("/sites", headers=second_headers)
    assert hidden.status_code == 200
    assert hidden.json() == []
    missing = client.patch(f"/sites/{site_id}", json={"name": "Ajena", "address": None}, headers=second_headers)
    assert missing.status_code == 404


def test_operator_cannot_create_a_site(client, accounts) -> None:
    operator = accounts("operator")
    response = client.post("/sites", json={"name": "Bodega"}, headers=auth_header(client, operator))
    assert response.status_code == 403
    assert response.json()["detail"] == "No tienes permiso para esta acción"


def test_camera_response_hides_rtsp_credentials(client, accounts) -> None:
    admin = accounts()
    headers = auth_header(client, admin)
    site = client.post("/sites", json={"name": "Acceso"}, headers=headers)
    assert site.status_code == 201
    created = client.post(
        "/cameras",
        json={
            "site_id": site.json()["id"],
            "name": "Portería",
            "source_type": "rtsp",
            "rtsp_url": "rtsp://operator:s3cret@10.4.4.8:554/live",
            "fps": 3,
        },
        headers=headers,
    )
    assert created.status_code == 201
    body = created.json()
    encoded = str(body)
    assert "s3cret" not in encoded
    assert "operator" not in encoded
    assert "rtsp_url_encrypted" not in body
    assert body["rtsp_url_masked"].startswith("rtsp://***@10.4.4.8")
    listed = client.get("/cameras", headers=auth_header(client, accounts()))
    assert listed.status_code == 200
    assert listed.json() == []


def test_zone_is_scoped_to_the_camera_organization(client, accounts) -> None:
    owner = accounts()
    outsider = accounts()
    headers = auth_header(client, owner)
    site = client.post("/sites", json={"name": "Nave"}, headers=headers)
    camera = client.post(
        "/cameras",
        json={"site_id": site.json()["id"], "name": "Muelle", "source_type": "file", "file_path": "demo/muelle.mp4"},
        headers=headers,
    )
    assert camera.status_code == 201
    camera_id = camera.json()["id"]
    zone = client.post(f"/cameras/{camera_id}/zones", json=zone_payload(), headers=headers)
    assert zone.status_code == 201
    assert zone.json()["rule_type"] == "intrusion"
    foreign = client.get(f"/cameras/{camera_id}/zones", headers=auth_header(client, outsider))
    assert foreign.status_code == 404
    blocked = client.delete(f"/sites/{site.json()['id']}", headers=headers)
    assert blocked.status_code == 409
