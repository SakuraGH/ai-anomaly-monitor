"""监控 Agent：定时遍历指标，调用检测器发现异常。"""

from datetime import date as date_type

from src.detection.detector import AnomalyDetector
from src.models.anomaly_event import AnomalyEvent


class MonitorAgent:
    """监控 Agent —— 自动发现关键指标异常。

    职责：
    - 定时拉取所有注册指标的数据
    - 调用异常检测器（基线对比 + Z-score）
    - 返回异常事件列表
    """

    def __init__(self, detector: AnomalyDetector):
        self.detector = detector

    def run(
        self,
        metric_ids: list[str] | None = None,
        target_date: date_type | None = None,
    ) -> list[AnomalyEvent]:
        """执行监控任务。

        metric_ids=None 时遍历所有注册指标。
        target_date=None 时默认检测今天。
        """
        if target_date is None:
            target_date = date_type.today()

        if metric_ids:
            events = []
            for mid in metric_ids:
                try:
                    event = self.detector.detect(mid, target_date)
                    if event is not None:
                        events.append(event)
                except Exception:
                    continue
            return events

        return self.detector.detect_all(target_date)
