from datetime import date as date_type, datetime as dt
from enum import Enum

from pydantic import BaseModel, Field


class FeedbackStatus(str, Enum):
    CORRECT = "correct"
    WRONG = "wrong"
    PARTIAL = "partial"
    PENDING = "pending"


class KnowledgeRecord(BaseModel):
    """知识库记录：每次异常归因结束后自动录入。"""

    case_id: str = ""
    date: date_type | None = None
    metric_id: str = ""
    metric_name: str = ""
    anomaly_description: str = ""
    anomaly_detail: str = ""  # 详细描述（用于向量化检索）
    root_cause: str = ""
    evidence_chain: list[str] = Field(default_factory=list)
    dimension_drill: str = ""  # 维度下钻结果摘要
    action_taken: str = ""
    recovery: str = ""
    tags: list[str] = Field(default_factory=list)
    feedback: FeedbackStatus = FeedbackStatus.PENDING
    feedback_note: str = ""
    created_at: dt | None = None
    source_run_id: str = ""  # 关联的管道 run_id

    @property
    def search_text(self) -> str:
        """组合所有文本字段用于向量化检索。"""
        parts = [
            f"指标:{self.metric_name}",
            self.anomaly_description,
            self.anomaly_detail,
            f"根因:{self.root_cause}",
            " ".join(self.evidence_chain),
            " ".join(self.tags),
        ]
        return " | ".join(p for p in parts if p)


class FeedbackRecord(BaseModel):
    """反馈记录。"""

    case_id: str
    status: FeedbackStatus
    note: str = ""
    reviewer: str = ""
    reviewed_at: dt | None = None


class KnowledgeStats(BaseModel):
    """知识库统计。"""

    total_cases: int = 0
    correct_count: int = 0
    wrong_count: int = 0
    partial_count: int = 0
    pending_count: int = 0

    @property
    def accuracy(self) -> float:
        total = self.correct_count + self.wrong_count + self.partial_count
        if total == 0:
            return 0.0
        return self.correct_count / total
