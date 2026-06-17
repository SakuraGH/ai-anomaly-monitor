from pydantic import BaseModel, Field


class MetricDimension(BaseModel):
    name: str
    label: str
    values: list[str] = Field(default_factory=list)


class MetricDataSource(BaseModel):
    type: str  # csv / database / api
    path: str | None = None
    date_column: str = "date"
    value_column: str = "value"
    # 数据库专用
    table: str | None = None
    metric_id_column: str = "metric_id"
    # API 专用
    endpoint: str | None = None
    method: str = "POST"
    date_field: str = "date"
    value_field: str = "value"


class AlertThreshold(BaseModel):
    change_rate: float = 0.10
    z_score: float = 2.0


class MetricDefinition(BaseModel):
    metric_id: str
    metric_name: str
    formula: str = ""
    description: str = ""
    data_source: MetricDataSource
    update_time: str = "08:00"
    owner: str = ""
    dimensions: list[MetricDimension] = Field(default_factory=list)
    priority: str = "P1"  # P0 / P1 / P2
    baseline_type: str = "近4周同期均值"
    alert_threshold: AlertThreshold = Field(default_factory=AlertThreshold)

    @property
    def dimension_names(self) -> list[str]:
        return [d.name for d in self.dimensions]
