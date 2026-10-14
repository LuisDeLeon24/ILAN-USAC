from datetime import date

from pydantic import BaseModel, field_validator


class DayCount(BaseModel):
    date: date
    count: int


class MetricsRead(BaseModel):
    month_start: date
    events_per_day: list[DayCount]
    average_response_seconds: float | None
    analyzed_minutes: float
    rate_per_minute: float
    currency: str
    estimated_cost: float
    previous_month_start: date | None = None
    previous_analyzed_minutes: float | None = None
    previous_estimated_cost: float | None = None


class PricingWrite(BaseModel):
    rate_per_minute: float

    @field_validator("rate_per_minute")
    @classmethod
    def rate_is_valid(cls, value: float) -> float:
        if isinstance(value, bool) or value < 0 or value > 10000:
            raise ValueError("La tarifa por minuto no es válida")
        return round(float(value), 4)


class PricingRead(BaseModel):
    rate_per_minute: float
    currency: str
