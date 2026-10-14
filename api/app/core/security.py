import hashlib
import uuid
from datetime import datetime, timedelta, timezone
from urllib.parse import urlparse, urlunparse

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerifyMismatchError, VerificationError
from cryptography.fernet import Fernet

from app.core.config import settings

password_hasher = PasswordHasher()
JWT_ALGORITHM = "HS256"


def hash_password(password: str) -> str:
    return password_hasher.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return password_hasher.verify(password_hash, password)
    except (VerifyMismatchError, VerificationError, InvalidHashError):
        return False


def create_access_token(*, user_id: uuid.UUID, organization_id: uuid.UUID, role: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.jwt_expire_minutes)
    payload = {"sub": str(user_id), "org": str(organization_id), "role": role, "exp": expire}
    return jwt.encode(payload, settings.jwt_secret, algorithm=JWT_ALGORITHM)


def decode_access_token(token: str) -> dict:
    return jwt.decode(token, settings.jwt_secret, algorithms=[JWT_ALGORITHM])


def encrypt_secret(value: str) -> str:
    return Fernet(settings.fernet_key.encode()).encrypt(value.encode()).decode()


def decrypt_secret(value: str) -> str:
    return Fernet(settings.fernet_key.encode()).decrypt(value.encode()).decode()


def hash_device_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def mask_rtsp(url: str) -> str:
    parsed = urlparse(url)
    host = parsed.hostname or ""
    if parsed.port:
        host = f"{host}:{parsed.port}"
    if parsed.username or parsed.password:
        host = f"***@{host}"
    return urlunparse((parsed.scheme, host, parsed.path, "", "", ""))
