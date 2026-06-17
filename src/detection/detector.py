"""综合异常判定器：组合多种检测方法，输出 AnomalyEvent。"""

from datetime import date as date_type

from src.metrics.loader import MetricLoader
from src.metrics.registry import MetricRegistry
from src.models.anomaly_event import AnomalyEvent, DetectionMethod, Severity

from .calendar import CalendarManager
from .comparisons import baseline_compare
from .zscore import z_score_detect


class AnomalyDetector:
    """综合异常判定器。

    流程：
    1. 加载当前值和基线数据
    2. 基线均值对比检测
    3. Z-score 统计检测
    4. 日历修正判断
    5. 综合判定严重级别
    """

    def __init__(
        self,
        registry: MetricRegistry,
        loader: MetricLoader,
        calendar: CalendarManager | None = None,
    ):
        self.registry = registry
        self.loader = loader
        self.calendar = calendar

    def detect(
        self,
        metric_id: str,
        target_date: date_type,
    ) -> AnomalyEvent | None:
        """对单个指标在指定日期执行异常检测。

        如果未检测到异常，返回 None。
        """
        metric = self.registry.get_metric(metric_id)

        current_df = self.loader.load_current(metric, target_date)
        if current_df.empty:
            return None
        current_value = float(current_df["value"].iloc[0])

        baseline_df = self.loader.load_baseline(metric, target_date)
        if baseline_df.empty:
            return None
        baseline_values = baseline_df["value"].tolist()

        threshold = metric.alert_threshold.change_rate
        z_threshold = metric.alert_threshold.z_score

        comparison = baseline_compare(current_value, baseline_values, threshold)

        z_result = z_score_detect(
            current_value, baseline_values,
            threshold=z_threshold, priority=metric.priority,
        )

        triggered_methods: list[DetectionMethod] = []
        if comparison.is_anomaly:
            triggered_methods.append(DetectionMethod.MOVING_AVERAGE)
        if z_result.is_anomaly:
            triggered_methods.append(DetectionMethod.Z_SCORE)

        if not triggered_methods:
            return None

        is_calendar_adjusted = False
        calendar_event_name: str | None = None

        if self.calendar is not None:
            event = self.calendar.get_event(target_date)
            if event is not None:
                is_calendar_adjusted = True
                calendar_event_name = event["event_name"]

        severity = self._determine_severity(
            metric.priority, comparison.change_rate, z_result.z_score,
        )

        message = (
            f"{metric.metric_name}在{target_date}的值为{current_value:.0f}，"
            f"较基线{comparison.baseline:.0f}{comparison.change_rate:+.1%}，"
            f"Z-score={z_result.z_score:.2f}"
        )
        if calendar_event_name:
            message += f"（当日为{calendar_event_name}）"

        return AnomalyEvent(
            metric_id=metric_id,
            metric_name=metric.metric_name,
            event_date=target_date,
            current_value=current_value,
            baseline_value=comparison.baseline,
            change_rate=comparison.change_rate,
            z_score=z_result.z_score,
            severity=severity,
            detection_methods=triggered_methods,
            is_calendar_adjusted=is_calendar_adjusted,
            calendar_event=calendar_event_name,
            priority=metric.priority,
            message=message,
        )

    def detect_all(
        self,
        target_date: date_type,
    ) -> list[AnomalyEvent]:
        """对所有注册指标执行异常检测，返回检测到的异常列表。"""
        events = []
        for metric in self.registry.list_metrics():
            try:
                event = self.detect(metric.metric_id, target_date)
                if event is not None:
                    events.append(event)
            except Exception:
                continue
        return events

    @staticmethod
    def _determine_severity(
        priority: str,
        change_rate: float,
        z_score: float,
    ) -> Severity:
        abs_change = abs(change_rate)
        abs_z = abs(z_score)

        if priority == "P0" and (abs_change > 0.15 or abs_z > 3.0):
            return Severity.HIGH
        if priority == "P0" or abs_change > 0.20 or abs_z > 3.0:
            return Severity.MEDIUM
        return Severity.LOW
