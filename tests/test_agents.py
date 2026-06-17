"""Agent 编排层单元测试。"""

from datetime import date
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
CONFIG_PATH = PROJECT_ROOT / "config" / "metrics_registry.yaml"
CALENDAR_PATH = PROJECT_ROOT / "data" / "activity_calendar.csv"
TARGET_DATE = date(2026, 6, 12)


def _make_registry():
    from src.metrics.registry import MetricRegistry
    return MetricRegistry(CONFIG_PATH)


def _make_loader():
    from src.metrics.loader import MetricLoader
    return MetricLoader(project_root=str(PROJECT_ROOT))


def _make_calendar():
    from src.detection.calendar import CalendarManager
    return CalendarManager(CALENDAR_PATH)


def _make_detector():
    from src.detection.detector import AnomalyDetector
    registry = _make_registry()
    loader = _make_loader()
    calendar = _make_calendar()
    return AnomalyDetector(registry, loader, calendar)


# ── MonitorAgent 测试 ───────────────────────────────────────

class TestMonitorAgent:
    def test_run_all_metrics(self):
        from src.agents.monitor_agent import MonitorAgent

        agent = MonitorAgent(_make_detector())
        events = agent.run(target_date=TARGET_DATE)

        assert isinstance(events, list)
        assert len(events) > 0
        for evt in events:
            assert evt.metric_id

    def test_run_specific_metric(self):
        from src.agents.monitor_agent import MonitorAgent

        agent = MonitorAgent(_make_detector())
        events = agent.run(["reg_daily"], TARGET_DATE)

        assert len(events) >= 0
        if events:
            assert events[0].metric_id == "reg_daily"

    def test_run_nonexistent_metric(self):
        from src.agents.monitor_agent import MonitorAgent

        agent = MonitorAgent(_make_detector())
        events = agent.run(["nonexistent"], TARGET_DATE)
        assert events == []


# ── AttributionAgent 测试 ────────────────────────────────────

class TestAttributionAgent:
    def _make_agent(self):
        from src.agents.attribution_agent import AttributionAgent
        from src.attribution.evidence_collector import EvidenceCollector

        return AttributionAgent(
            registry=_make_registry(),
            loader=_make_loader(),
            evidence_collector=EvidenceCollector(calendar=_make_calendar()),
        )

    def _make_anomaly(self):
        from src.agents.monitor_agent import MonitorAgent
        agent = MonitorAgent(_make_detector())
        events = agent.run(["reg_daily"], TARGET_DATE)
        assert len(events) > 0
        return events[0]

    def test_run_returns_attribution_result(self):
        agent = self._make_agent()
        anomaly = self._make_anomaly()
        result = agent.run(anomaly)

        assert result.metric_id == "reg_daily"
        assert result.metric_name == "日注册量"
        assert len(result.drill_levels) > 0
        assert result.summary

    def test_drill_levels_contain_channel(self):
        agent = self._make_agent()
        anomaly = self._make_anomaly()
        result = agent.run(anomaly)

        dims = {l.dimension for l in result.drill_levels}
        assert "channel" in dims

    def test_baidu_sem_is_top_contributor(self):
        agent = self._make_agent()
        anomaly = self._make_anomaly()
        result = agent.run(anomaly)

        assert "百度SEM" in result.top_contributor

    def test_evidence_collected(self):
        agent = self._make_agent()
        anomaly = self._make_anomaly()
        result = agent.run(anomaly)

        assert result.evidence is not None
        assert len(result.evidence.items) > 0

    def test_summary_not_empty(self):
        agent = self._make_agent()
        anomaly = self._make_anomaly()
        result = agent.run(anomaly)

        assert len(result.summary) > 50
        assert "异常摘要" in result.summary
        assert "主要贡献来源" in result.summary

    def test_summary_mentions_baidu(self):
        agent = self._make_agent()
        anomaly = self._make_anomaly()
        result = agent.run(anomaly)

        assert "百度SEM" in result.summary


# ── Orchestrator 测试 ────────────────────────────────────────

class TestOrchestrator:
    def _make_orchestrator(self):
        from src.agents.monitor_agent import MonitorAgent
        from src.agents.attribution_agent import AttributionAgent
        from src.agents.orchestrator import Orchestrator
        from src.attribution.evidence_collector import EvidenceCollector

        monitor = MonitorAgent(_make_detector())
        attributor = AttributionAgent(
            registry=_make_registry(),
            loader=_make_loader(),
            evidence_collector=EvidenceCollector(calendar=_make_calendar()),
        )
        return Orchestrator(monitor, attributor)

    def test_run_pipeline(self):
        orchestrator = self._make_orchestrator()
        result = orchestrator.run_pipeline(TARGET_DATE)

        assert result.run_id
        assert result.target_date == TARGET_DATE
        assert result.anomaly_count > 0
        assert len(result.attributions) > 0
        assert "reg_daily" in result.attributions
        assert result.message

    def test_run_pipeline_stores_result(self):
        orchestrator = self._make_orchestrator()
        result = orchestrator.run_pipeline(TARGET_DATE)

        stored = orchestrator.store.get(result.run_id)
        assert stored is not None
        assert stored.run_id == result.run_id

    def test_run_single_metric(self):
        orchestrator = self._make_orchestrator()
        result = orchestrator.run_single("reg_daily", TARGET_DATE)

        assert result.anomaly_count >= 0
        if result.anomaly_count > 0:
            assert "reg_daily" in result.attributions

    def test_list_results(self):
        orchestrator = self._make_orchestrator()
        orchestrator.run_pipeline(TARGET_DATE)
        orchestrator.run_pipeline(TARGET_DATE)

        results = orchestrator.store.list()
        assert len(results) >= 2

    def test_on_anomaly_callback(self):
        from src.agents.monitor_agent import MonitorAgent
        from src.agents.attribution_agent import AttributionAgent
        from src.agents.orchestrator import Orchestrator
        from src.attribution.evidence_collector import EvidenceCollector

        callbacks = []

        def cb(anomaly, attribution):
            callbacks.append((anomaly.metric_id, attribution.metric_id))

        monitor = MonitorAgent(_make_detector())
        attributor = AttributionAgent(
            registry=_make_registry(),
            loader=_make_loader(),
            evidence_collector=EvidenceCollector(calendar=_make_calendar()),
        )
        orchestrator = Orchestrator(monitor, attributor, on_anomaly=cb)
        orchestrator.run_pipeline(TARGET_DATE)

        assert len(callbacks) > 0
        assert callbacks[0][0] == callbacks[0][1]  # same metric_id


# ── ResultStore 测试 ─────────────────────────────────────────

class TestResultStore:
    def test_save_and_get(self):
        from src.agents.orchestrator import ResultStore
        from src.models.pipeline_result import PipelineResult

        store = ResultStore()
        r = PipelineResult(run_id="test-1", message="hello")
        store.save(r)

        assert store.get("test-1") is not None
        assert store.get("test-1").message == "hello"

    def test_get_nonexistent(self):
        from src.agents.orchestrator import ResultStore

        store = ResultStore()
        assert store.get("nonexistent") is None

    def test_list_limit(self):
        from src.agents.orchestrator import ResultStore
        from src.models.pipeline_result import PipelineResult

        store = ResultStore()
        for i in range(50):
            store.save(PipelineResult(run_id=f"r-{i}"))

        results = store.list(limit=10)
        assert len(results) == 10


# ── TaskScheduler 测试 ───────────────────────────────────────

class TestTaskScheduler:
    def test_create_scheduler(self):
        from src.scheduler.task_scheduler import TaskScheduler

        s = TaskScheduler()
        assert s is not None
        assert len(s.jobs) == 0
        s.shutdown(wait=False)

    def test_add_cron_job(self):
        from src.scheduler.task_scheduler import TaskScheduler

        s = TaskScheduler()
        calls = []

        s.add_cron_job("test", lambda: calls.append(1), "0 9 * * *")
        assert "test" in s.jobs
        assert s.jobs["test"] == "0 9 * * *"
        s.shutdown(wait=False)

    def test_add_interval_job(self):
        from src.scheduler.task_scheduler import TaskScheduler

        s = TaskScheduler()
        s.add_interval_job("test", lambda: None, hours=1)
        assert "test" in s.jobs
        assert s.jobs["test"] == "every_1h"
        s.shutdown(wait=False)

    def test_remove_job(self):
        from src.scheduler.task_scheduler import TaskScheduler

        s = TaskScheduler()
        s.add_cron_job("test", lambda: None, "0 9 * * *")
        s.remove_job("test")
        assert "test" not in s.jobs
        s.shutdown(wait=False)

    def test_invalid_cron_raises(self):
        from src.scheduler.task_scheduler import TaskScheduler

        s = TaskScheduler()
        with pytest.raises(ValueError, match="cron"):
            s.add_cron_job("bad", lambda: None, "bad")
        s.shutdown(wait=False)

    def test_next_fire_times(self):
        from src.scheduler.task_scheduler import TaskScheduler

        s = TaskScheduler()
        s.add_cron_job("test", lambda: None, "0 9 * * *")
        times = s.next_fire_times
        assert "test" in times
        s.shutdown(wait=False)

    def test_create_monitor_scheduler(self):
        from src.agents.monitor_agent import MonitorAgent
        from src.agents.attribution_agent import AttributionAgent
        from src.agents.orchestrator import Orchestrator
        from src.attribution.evidence_collector import EvidenceCollector
        from src.scheduler.task_scheduler import create_monitor_scheduler

        monitor = MonitorAgent(_make_detector())
        attributor = AttributionAgent(
            registry=_make_registry(),
            loader=_make_loader(),
            evidence_collector=EvidenceCollector(calendar=_make_calendar()),
        )
        orchestrator = Orchestrator(monitor, attributor)

        s = create_monitor_scheduler(orchestrator, "0 9 * * *")
        assert "daily_monitor" in s.jobs
        s.shutdown(wait=False)


# ── PipelineResult 模型测试 ──────────────────────────────────

class TestPipelineResult:
    def test_anomaly_count(self):
        from src.models.pipeline_result import PipelineResult

        r = PipelineResult(anomalies=[])
        assert r.anomaly_count == 0

    def test_to_dict(self):
        from src.models.pipeline_result import PipelineResult

        r = PipelineResult(run_id="x", message="done")
        d = r.model_dump()
        assert d["run_id"] == "x"
        assert d["message"] == "done"
