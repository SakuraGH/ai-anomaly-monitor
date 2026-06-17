"""API 依赖注入：统一管理系统各组件的单例。"""

from typing import Any


class AppState:
    def __init__(self):
        self.registry = None
        self.loader = None
        self.calendar = None
        self.detector = None
        self.orchestrator = None
        self.scheduler = None
        self.store = None
        self.feedback_mgr = None

    def init_all(self, config: dict[str, Any] | None = None):
        from pathlib import Path

        project_root = Path(__file__).resolve().parent.parent.parent

        from src.metrics.registry import MetricRegistry
        from src.metrics.loader import MetricLoader
        from src.detection.calendar import CalendarManager
        from src.detection.detector import AnomalyDetector
        from src.agents.monitor_agent import MonitorAgent
        from src.attribution.evidence_collector import EvidenceCollector
        from src.agents.attribution_agent import AttributionAgent
        from src.agents.orchestrator import Orchestrator
        from src.scheduler.task_scheduler import TaskScheduler
        from src.llm.summarizer import Summarizer

        cal_path = project_root / "data" / "activity_calendar.csv"
        metrics_path = project_root / "config" / "metrics_registry.yaml"
        llm_config_path = project_root / "config" / "llm_config.yaml"

        self.registry = MetricRegistry(metrics_path)
        self.loader = MetricLoader(project_root=str(project_root))
        self.calendar = CalendarManager(cal_path)
        self.detector = AnomalyDetector(self.registry, self.loader, self.calendar)

        # 尝试加载 LLM，失败则降级到规则摘要
        summarizer = None
        try:
            from src.llm.factory import create_llm
            llm = create_llm(str(llm_config_path))
            summarizer = Summarizer(llm)
        except Exception:
            pass

        monitor = MonitorAgent(self.detector)
        evidence_collector = EvidenceCollector(calendar=self.calendar)
        attributor = AttributionAgent(
            self.registry, self.loader, evidence_collector,
            summarizer=summarizer,
        )

        self.orchestrator = Orchestrator(monitor, attributor)

        self.scheduler = TaskScheduler()
        self.scheduler.add_cron_job(
            "daily_monitor",
            lambda: self.orchestrator.run_pipeline(),
            "0 9 * * *",
        )


_state = AppState()


def get_state() -> AppState:
    return _state
