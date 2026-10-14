import uuid

from app.core.security import create_access_token, decrypt_secret, encrypt_secret, mask_rtsp, verify_password, hash_password
from app.core.security import decode_access_token


def test_password_roundtrip() -> None:
    stored = hash_password("password1")
    assert verify_password("password1", stored)
    assert not verify_password("otra-clave", stored)


def test_rtsp_secret_is_encrypted_and_masked() -> None:
    raw = "rtsp://operator:s3cret@10.1.1.5:554/Streaming/Channels/101"
    stored = encrypt_secret(raw)
    assert stored != raw
    assert decrypt_secret(stored) == raw
    masked = mask_rtsp(raw)
    assert "s3cret" not in masked
    assert "operator" not in masked
    assert "10.1.1.5:554" in masked
    assert masked.startswith("rtsp://***@")


def test_access_token_carries_the_organization() -> None:
    user_id = uuid.uuid4()
    organization_id = uuid.uuid4()
    token = create_access_token(user_id=user_id, organization_id=organization_id, role="operator")
    payload = decode_access_token(token)
    assert payload["sub"] == str(user_id)
    assert payload["org"] == str(organization_id)
    assert payload["role"] == "operator"
