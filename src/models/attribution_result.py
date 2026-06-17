from datetime import date as date_type

from pydantic import BaseModel, Field


class ContributionItem(BaseModel):
    """单个维度值的贡献度条目。"""
    dimension: str
    dimension_value: str
    current_value: float
    baseline_value: float
    change_amount: float
    contribution_pct: float  # 贡献占比，如 0.60 表示 60%

    @property
    def change_rate(self) -> float:
        if self.baseline_value == 0:
            return 0.0
        return (self.current_value - self.baseline_value) / self.baseline_value


class DrillDownLevel(BaseModel):
    """一次下钻的结果（某个维度的拆分）。"""
    dimension: str
    total_change: float
    items: list[ContributionItem] = Field(default_factory=list)
    filter_context: dict[str, str] = Field(default_factory=dict)


class EvidenceItem(BaseModel):
    """一条证据。"""
    source: str      # calendar / version / budget / metric
    content: str
    verified: bool = False


class EvidencePack(BaseModel):
    """结构化证据包，给 AI 总结层使用。"""
    metric_id: str
    metric_name: str
    event_date: date_type
    current_value: float
    baseline_value: float
    change_rate: float
    items: list[EvidenceItem] = Field(default_factory=list)


class AttributionResult(BaseModel):
    """完整的归因分析结果。"""
    metric_id: str
    metric_name: str
    event_date: date_type
    current_value: float
    baseline_value: float
    change_rate: float
    drill_levels: list[DrillDownLevel] = Field(default_factory=list)
    evidence: EvidencePack | None = None
    top_contributor: str = ""
    top_contribution_pct: float = 0.0
    summary: str = ""
