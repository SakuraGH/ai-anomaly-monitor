from datetime import datetime as dt
from datetime import date as date_type

from pydantic import BaseModel, Field, computed_field

from .anomaly_event import AnomalyEvent
from .attribution_result import AttributionResult


class PipelineResult(BaseModel):
    """一次完整管道执行的结果。"""
    run_id: str = ""
    run_time: dt | None = None
    target_date: date_type | None = None
    anomalies: list[AnomalyEvent] = Field(default_factory=list)
    attributions: dict[str, AttributionResult] = Field(default_factory=dict)
    message: str = ""

    @computed_field
    @property
    def anomaly_count(self) -> int:
        return len(self.anomalies)
