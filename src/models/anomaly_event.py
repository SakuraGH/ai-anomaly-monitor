from datetime import date as date_type
from enum import Enum

from pydantic import BaseModel, Field


class Severity(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class DetectionMethod(str, Enum):
    YEAR_OVER_YEAR = "year_over_year"
    MONTH_OVER_MONTH = "month_over_month"
    MOVING_AVERAGE = "moving_average"
    Z_SCORE = "z_score"
    THREE_SIGMA = "three_sigma"


class AnomalyEvent(BaseModel):
    metric_id: str
    metric_name: str = ""
    event_date: date_type
    current_value: float
    baseline_value: float
    change_rate: float
    z_score: float | None = None
    severity: Severity = Severity.MEDIUM
    detection_methods: list[DetectionMethod] = Field(default_factory=list)
    is_calendar_adjusted: bool = False
    calendar_event: str | None = None
    priority: str = "P1"
    message: str = ""

    @property
    def change_pct(self) -> str:
        sign = "+" if self.change_rate > 0 else ""
        return f"{sign}{self.change_rate:.1%}"

    @property
    def is_decline(self) -> bool:
        return self.change_rate < 0
