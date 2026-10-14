import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    api_base_url: str
    device_token: str
    preview_dir: Path
    buffer_dir: Path
    model_path: Path
    model_version: str
    sensor_webhook_token: str
    sensor_webhook_port: int
    live_dir: Path
    live_stream_secret: str
    live_cors_origin: str


def load_settings() -> Settings:
    buffer_dir = Path(os.environ.get("BUFFER_DIR", "/var/lib/sentinel"))
    return Settings(
        api_base_url=os.environ.get("API_BASE_URL", "http://api:8000").rstrip("/"),
        device_token=os.environ.get("DEVICE_TOKEN", "").strip(),
        preview_dir=Path(os.environ.get("PREVIEW_DIR", "/preview")),
        buffer_dir=buffer_dir,
        model_path=Path(os.environ.get("MODEL_PATH", "/models/yolov8n.pt")),
        model_version=os.environ.get("MODEL_VERSION", "yolov8n.pt").strip() or "yolov8n.pt",
        sensor_webhook_token=os.environ.get("SENSOR_WEBHOOK_TOKEN", "").strip(),
        sensor_webhook_port=_webhook_port(os.environ.get("SENSOR_WEBHOOK_PORT", "8081")),
        live_dir=Path(os.environ.get("LIVE_DIR", str(buffer_dir / "live"))),
        live_stream_secret=os.environ.get("LIVE_STREAM_SECRET", "").strip(),
        live_cors_origin=os.environ.get("LIVE_CORS_ORIGIN", "").strip().rstrip("/"),
    )


def _webhook_port(value: str) -> int:
    try:
        port = int(value)
    except ValueError:
        return 0
    if 1 <= port <= 65535:
        return port
    return 0
