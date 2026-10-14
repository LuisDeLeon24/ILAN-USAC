import logging
from io import BytesIO

from minio import Minio

from app.core.config import settings

logger = logging.getLogger("sentinel.api")


def _client() -> Minio:
    return Minio(
        settings.minio_endpoint,
        access_key=settings.minio_access_key,
        secret_key=settings.minio_secret_key,
        secure=settings.minio_secure,
    )


def ensure_bucket() -> None:
    client = _client()
    if client.bucket_exists(settings.minio_bucket):
        return
    client.make_bucket(settings.minio_bucket)
    logger.info("created bucket %s", settings.minio_bucket)


def put_bytes(key: str, payload: bytes, content_type: str) -> None:
    _client().put_object(
        settings.minio_bucket,
        key,
        BytesIO(payload),
        length=len(payload),
        content_type=content_type,
    )


def get_bytes(key: str) -> bytes:
    response = _client().get_object(settings.minio_bucket, key)
    try:
        return response.read()
    finally:
        response.close()
        response.release_conn()
