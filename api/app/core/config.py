from functools import lru_cache

from cryptography.fernet import Fernet
from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

DEFAULT_TIMEZONE = "America/Guatemala"


class Settings(BaseSettings):
    database_url: str
    redis_url: str
    minio_endpoint: str
    minio_access_key: str
    minio_secret_key: str
    minio_bucket: str
    minio_secure: bool = False
    jwt_secret: str
    jwt_expire_minutes: int = 720
    fernet_key: str
    bootstrap_org_name: str
    bootstrap_admin_email: str
    bootstrap_admin_password: str
    bootstrap_admin_name: str
    bootstrap_device_token: str = ""
    event_cooldown_seconds: int = 60
    alert_cooldown_seconds: int = 600
    twilio_account_sid: str = ""
    twilio_auth_token: str = ""
    twilio_whatsapp_from: str = ""
    twilio_content_sid: str = ""
    telegram_bot_token: str = ""
    public_base_url: str = ""
    live_stream_secret: str = ""
    worker_public_url: str = ""
    llm_provider: str = "gemini"
    llm_api_key: str = ""
    llm_model: str = ""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @field_validator("jwt_secret")
    @classmethod
    def jwt_secret_length(cls, value: str) -> str:
        if len(value) < 32:
            raise ValueError("JWT_SECRET must be at least 32 characters")
        return value

    @field_validator("fernet_key")
    @classmethod
    def fernet_key_valid(cls, value: str) -> str:
        Fernet(value.encode())
        return value

    @field_validator("bootstrap_device_token")
    @classmethod
    def device_token_length(cls, value: str) -> str:
        cleaned = value.strip()
        if cleaned and len(cleaned) < 16:
            raise ValueError("BOOTSTRAP_DEVICE_TOKEN must be at least 16 characters")
        return cleaned

    @field_validator("event_cooldown_seconds")
    @classmethod
    def cooldown_positive(cls, value: int) -> int:
        if value < 1:
            raise ValueError("EVENT_COOLDOWN_SECONDS must be at least 1")
        return value

    @field_validator("alert_cooldown_seconds")
    @classmethod
    def alert_cooldown_positive(cls, value: int) -> int:
        if value < 1:
            raise ValueError("ALERT_COOLDOWN_SECONDS must be at least 1")
        return value

    @field_validator(
        "twilio_account_sid",
        "twilio_auth_token",
        "twilio_whatsapp_from",
        "twilio_content_sid",
        "telegram_bot_token",
    )
    @classmethod
    def strip_alert_secrets(cls, value: str) -> str:
        return value.strip()

    @field_validator("llm_provider")
    @classmethod
    def llm_provider_known(cls, value: str) -> str:
        cleaned = value.strip().lower()
        if cleaned not in {"gemini", "openai", "anthropic"}:
            raise ValueError("LLM_PROVIDER must be gemini, openai, or anthropic")
        return cleaned

    @field_validator("llm_api_key", "llm_model")
    @classmethod
    def strip_llm(cls, value: str) -> str:
        return value.strip()

    @field_validator("public_base_url", "worker_public_url")
    @classmethod
    def http_origin(cls, value: str) -> str:
        cleaned = value.strip().rstrip("/")
        if cleaned and not cleaned.startswith(("http://", "https://")):
            raise ValueError("URL must start with http:// or https://")
        return cleaned

    @field_validator("live_stream_secret")
    @classmethod
    def live_secret_length(cls, value: str) -> str:
        cleaned = value.strip()
        if cleaned and len(cleaned) < 16:
            raise ValueError("LIVE_STREAM_SECRET must be at least 16 characters")
        return cleaned


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
