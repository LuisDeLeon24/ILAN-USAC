from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from app.core.config import DEFAULT_TIMEZONE

GUATEMALA = ZoneInfo(DEFAULT_TIMEZONE)
PERIODS = ("today", "yesterday", "this_week", "last_night", "this_month")
WEEKDAYS = ("lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo")
MONTHS = (
    "enero",
    "febrero",
    "marzo",
    "abril",
    "mayo",
    "junio",
    "julio",
    "agosto",
    "septiembre",
    "octubre",
    "noviembre",
    "diciembre",
)


def now_label(moment: datetime | None = None) -> str:
    local = (moment or datetime.now(GUATEMALA)).astimezone(GUATEMALA)
    weekday = WEEKDAYS[local.weekday()]
    month = MONTHS[local.month - 1]
    return f"{weekday} {local.day} de {month} de {local.year}, {local:%H:%M}"


def resolve_window(
    period: str | None,
    start: str | None,
    end: str | None,
    now: datetime | None = None,
) -> tuple[datetime, datetime]:
    moment = (now or datetime.now(GUATEMALA)).astimezone(GUATEMALA)
    if period:
        if period not in PERIODS:
            raise ValueError("Periodo no válido")
        if period == "last_night":
            start_at = datetime.combine(moment.date() - timedelta(days=1), time(20, 0), tzinfo=GUATEMALA)
            end_at = datetime.combine(moment.date(), time(6, 0), tzinfo=GUATEMALA)
            return start_at, end_at
        if period == "today":
            start_day = moment.date()
            end_day = start_day + timedelta(days=1)
        elif period == "yesterday":
            end_day = moment.date()
            start_day = end_day - timedelta(days=1)
        elif period == "this_week":
            start_day = moment.date() - timedelta(days=moment.weekday())
            end_day = moment.date() + timedelta(days=1)
        else:
            start_day = moment.date().replace(day=1)
            if start_day.month == 12:
                end_day = date(start_day.year + 1, 1, 1)
            else:
                end_day = date(start_day.year, start_day.month + 1, 1)
        return _bounds(start_day, end_day)
    start_day = _parse_day(start)
    end_day = _parse_day(end)
    if start_day is None or end_day is None:
        raise ValueError("Indica un periodo o las dos fechas")
    if start_day > end_day:
        raise ValueError("La fecha de inicio debe ser anterior o igual a la de fin")
    return _bounds(start_day, end_day + timedelta(days=1))


def _parse_day(value: str | None) -> date | None:
    if value is None or not str(value).strip():
        return None
    try:
        return date.fromisoformat(str(value).strip()[:10])
    except ValueError:
        raise ValueError("Fecha no válida") from None


def _bounds(start_day: date, end_day: date) -> tuple[datetime, datetime]:
    return (
        datetime.combine(start_day, time.min, tzinfo=GUATEMALA),
        datetime.combine(end_day, time.min, tzinfo=GUATEMALA),
    )
