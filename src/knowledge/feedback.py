"""反馈管理：分析师对 AI 归因结果的审核反馈，持续优化知识库。"""

from datetime import datetime as dt
from pathlib import Path
from typing import Any

from src.models.knowledge_record import (
    FeedbackRecord,
    FeedbackStatus,
    KnowledgeRecord,
    KnowledgeStats,
)

from .store import KnowledgeStore


class FeedbackManager:
    """反馈管理器。

    功能：
    - 记录分析师对归因结果的反馈（正确/错误/部分正确）
    - 更新知识库记录准确性标记
    - 统计各类型异常的历史命中率
    """

    def __init__(
        self,
        store: KnowledgeStore,
        log_path: str | Path | None = None,
    ):
        self.store = store
        self.log_path = Path(log_path) if log_path else None
        self._feedback_log: list[FeedbackRecord] = []
        if self.log_path and self.log_path.exists():
            self._load_log()

    def submit(
        self,
        case_id: str,
        status: FeedbackStatus,
        note: str = "",
        reviewer: str = "",
    ) -> FeedbackRecord:
        """提交一条反馈，同时更新知识库记录。"""
        record = self.store.update_feedback(case_id, status, note)

        fb = FeedbackRecord(
            case_id=case_id,
            status=status,
            note=note,
            reviewer=reviewer,
            reviewed_at=dt.now(),
        )
        self._feedback_log.append(fb)

        if self.log_path:
            self._save_log()

        return fb

    def submit_batch(
        self,
        feedbacks: list[dict[str, Any]],
        reviewer: str = "",
    ) -> list[FeedbackRecord]:
        """批量提交反馈。"""
        results = []
        for item in feedbacks:
            fb = self.submit(
                case_id=item["case_id"],
                status=FeedbackStatus(item.get("status", "pending")),
                note=item.get("note", ""),
                reviewer=item.get("reviewer", reviewer),
            )
            results.append(fb)
        return results

    def get_stats(self) -> KnowledgeStats:
        """统计知识库中各类异常的历史命中率。"""
        raw = self.store.get_stats()
        return KnowledgeStats(
            total_cases=raw["total"],
            correct_count=raw["correct"],
            wrong_count=raw["wrong"],
            partial_count=raw["partial"],
            pending_count=raw["pending"],
        )

    def get_tag_accuracy(self) -> dict[str, dict[str, int]]:
        """按标签（如渠道、支付等）统计准确率。"""
        records = self.store.list_all(limit=self.store.count())
        tag_stats: dict[str, dict[str, int]] = {}

        for r in records:
            for tag in r.tags:
                if tag not in tag_stats:
                    tag_stats[tag] = {"correct": 0, "wrong": 0, "partial": 0, "total": 0}
                tag_stats[tag][r.feedback.value] = tag_stats[tag].get(r.feedback.value, 0) + 1
                tag_stats[tag]["total"] += 1

        return tag_stats

    def records_pending_review(self) -> list[KnowledgeRecord]:
        """获取待审核的记录列表。"""
        all_records = self.store.list_all(limit=self.store.count())
        return [r for r in all_records if r.feedback == FeedbackStatus.PENDING]

    def _save_log(self) -> None:
        import json
        items = [fb.model_dump(mode="json") for fb in self._feedback_log]
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.log_path, "w", encoding="utf-8") as f:
            json.dump(items, f, ensure_ascii=False, indent=2, default=str)

    def _load_log(self) -> None:
        import json
        with open(self.log_path, encoding="utf-8") as f:
            items = json.load(f)
        self._feedback_log = [FeedbackRecord(**item) for item in items]
