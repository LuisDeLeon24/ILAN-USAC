from datetime import datetime, timezone

from app.models.entities import Event


def apply_event_status(event: Event, status: str, *, moment: datetime | None = None) -> None:
    event.status = status
    if status == "in_review" and event.reviewed_at is None:
        event.reviewed_at = moment or datetime.now(timezone.utc)
