"""证据收集器：汇总异常相关的上下文证据。"""

from datetime import date as date_type
from pathlib import Path

from src.detection.calendar import CalendarManager
from src.models.anomaly_event import AnomalyEvent
from src.models.attribution_result import (
    AttributionResult,
    EvidenceItem,
    EvidencePack,
)


class EvidenceCollector:
    """收集异常事件的上下文证据，输出结构化证据包给 AI 总结层。"""

    def __init__(
        self,
        calendar: CalendarManager | None = None,
        version_log_path: str | Path | None = None,
        budget_log_path: str | Path | None = None,
    ):
        self.calendar = calendar
        self.version_log_path = Path(version_log_path) if version_log_path else None
        self.budget_log_path = Path(budget_log_path) if budget_log_path else None

    def collect(
        self,
        anomaly: AnomalyEvent,
        attribution: AttributionResult,
    ) -> EvidencePack:
        pack = EvidencePack(
            metric_id=anomaly.metric_id,
            metric_name=anomaly.metric_name,
            event_date=anomaly.event_date,
            current_value=anomaly.current_value,
            baseline_value=anomaly.baseline_value,
            change_rate=anomaly.change_rate,
        )

        self._add_metric_evidence(pack, anomaly)
        self._add_attribution_evidence(pack, attribution)
        self._add_calendar_evidence(pack, anomaly.event_date)
        self._add_version_evidence(pack, anomaly.event_date)
        self._add_budget_evidence(pack, anomaly.event_date)

        return pack

    def _add_metric_evidence(self, pack: EvidencePack, anomaly: AnomalyEvent) -> None:
        pack.items.append(EvidenceItem(
            source="metric",
            content=(
                f"{anomaly.metric_name}在{anomaly.event_date}的值为"
                f"{anomaly.current_value:.0f}，"
                f"较基线{anomaly.baseline_value:.0f}"
                f"变化{anomaly.change_rate:+.1%}"
            ),
            verified=True,
        ))

        if anomaly.z_score is not None:
            pack.items.append(EvidenceItem(
                source="metric",
                content=f"Z-score = {anomaly.z_score:.2f}，严重级别: {anomaly.severity.value}",
                verified=True,
            ))

    def _add_attribution_evidence(
        self, pack: EvidencePack, attribution: AttributionResult,
    ) -> None:
        for level in attribution.drill_levels:
            context_str = ""
            if level.filter_context:
                parts = [f"{k}={v}" for k, v in level.filter_context.items()]
                context_str = f"（过滤条件: {', '.join(parts)}）"

            for item in level.items:
                if abs(item.contribution_pct) < 0.05:
                    continue
                pack.items.append(EvidenceItem(
                    source="attribution",
                    content=(
                        f"{item.dimension}={item.dimension_value}: "
                        f"当前{item.current_value:.0f} vs 基线{item.baseline_value:.0f}，"
                        f"变化{item.change_amount:+.0f}，"
                        f"贡献占比{item.contribution_pct:.0%}"
                        f"{context_str}"
                    ),
                    verified=True,
                ))

    def _add_calendar_evidence(self, pack: EvidencePack, d: date_type) -> None:
        if self.calendar is None:
            return

        event = self.calendar.get_event(d)
        if event:
            pack.items.append(EvidenceItem(
                source="calendar",
                content=(
                    f"当日为{event['event_name']}（{event['event_type']}），"
                    f"预期影响: {event['expected_impact']}"
                ),
                verified=True,
            ))

        if self.calendar.is_weekend(d):
            pack.items.append(EvidenceItem(
                source="calendar",
                content=f"当日为周末（星期{d.weekday() + 1}），周末效应因子: "
                        f"{self.calendar.weekday_factor(d):.2f}",
                verified=True,
            ))

    def _add_version_evidence(self, pack: EvidencePack, d: date_type) -> None:
        if self.version_log_path is None or not self.version_log_path.exists():
            return

        import csv
        with open(self.version_log_path, encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            for row in reader:
                if row.get("date") == d.isoformat():
                    pack.items.append(EvidenceItem(
                        source="version",
                        content=f"当日有版本发布: {row.get('version', '')} - "
                                f"{row.get('description', '')}",
                        verified=True,
                    ))

    def _add_budget_evidence(self, pack: EvidencePack, d: date_type) -> None:
        if self.budget_log_path is None or not self.budget_log_path.exists():
            return

        import csv
        with open(self.budget_log_path, encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            for row in reader:
                if row.get("date") == d.isoformat():
                    pack.items.append(EvidenceItem(
                        source="budget",
                        content=f"投放预算变化: {row.get('channel', '')} - "
                                f"{row.get('description', '')}",
                        verified=True,
                    ))
