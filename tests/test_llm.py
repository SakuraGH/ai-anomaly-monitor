"""LLM 抽象层单元测试。"""

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


# ── LLM Base 测试 ───────────────────────────────────────────

class TestLLMBase:
    def test_init_with_defaults(self):
        from src.llm.base import LLMBase

        class FakeLLM(LLMBase):
            def generate(self, system, user):
                return "ok"

            def test_connection(self):
                return True

        llm = FakeLLM()
        assert llm.temperature == 0.3
        assert llm.max_tokens == 4096
        assert llm.max_retries == 3

    def test_init_with_config(self):
        from src.llm.base import LLMBase

        class FakeLLM(LLMBase):
            def generate(self, system, user):
                return "ok"

            def test_connection(self):
                return True

        llm = FakeLLM({"temperature": 0.7, "max_tokens": 1024})
        assert llm.temperature == 0.7
        assert llm.max_tokens == 1024

    def test_generate_with_retry_success(self):
        from src.llm.base import LLMBase

        class FakeLLM(LLMBase):
            def generate(self, system, user):
                return "success"

            def test_connection(self):
                return True

        llm = FakeLLM()
        result = llm.generate_with_retry("system", "user")
        assert result == "success"

    def test_generate_with_retry_eventual_failure(self):
        from src.llm.base import LLMBase, LLMError

        class FailingLLM(LLMBase):
            def generate(self, system, user):
                raise RuntimeError("always fails")

            def test_connection(self):
                return False

        llm = FailingLLM({"max_retries": 2, "retry_delay": 0.01})
        with pytest.raises(LLMError, match="已重试"):
            llm.generate_with_retry("s", "u")

    def test_load_llm_config(self):
        from src.llm.base import load_llm_config

        config = load_llm_config(str(PROJECT_ROOT / "config" / "llm_config.yaml"))
        assert "provider" in config
        assert "model" in config
        assert "temperature" in config


# ── 适配器初始化测试 ─────────────────────────────────────────

class TestAdapters:
    def test_claude_adapter_init(self):
        from src.llm.claude_adapter import ClaudeAdapter

        a = ClaudeAdapter({"api_key": "test-key", "model": "claude-sonnet-4-6"})
        assert a.model == "claude-sonnet-4-6"
        assert a.temperature == 0.3

    def test_claude_adapter_default_model(self):
        from src.llm.claude_adapter import ClaudeAdapter

        a = ClaudeAdapter({"api_key": "test"})
        assert "claude" in a.model

    def test_claude_connection_no_key(self):
        from src.llm.claude_adapter import ClaudeAdapter

        a = ClaudeAdapter({"api_key": ""})
        assert a.test_connection() is False

    def test_openai_adapter_init(self):
        from src.llm.openai_adapter import OpenAIAdapter

        a = OpenAIAdapter({"api_key": "test-key", "model": "gpt-4o"})
        assert a.model == "gpt-4o"

    def test_openai_connection_no_key(self):
        from src.llm.openai_adapter import OpenAIAdapter

        a = OpenAIAdapter({"api_key": ""})
        assert a.test_connection() is False

    def test_custom_adapter_init(self):
        from src.llm.custom_adapter import CustomAdapter

        a = CustomAdapter({
            "api_key": "test",
            "base_url": "https://api.example.com",
            "model": "qwen-plus",
        })
        assert a.model == "qwen-plus"
        assert a.base_url == "https://api.example.com"

    def test_custom_adapter_connection_no_key(self):
        from src.llm.custom_adapter import CustomAdapter

        a = CustomAdapter({"api_key": ""})
        assert a.test_connection() is False


# ── Factory 测试 ─────────────────────────────────────────────

class TestFactory:
    def test_create_claude(self):
        from src.llm.factory import create_llm
        from src.llm.claude_adapter import ClaudeAdapter

        llm = create_llm({
            "provider": "claude",
            "api_key": "test",
            "model": "claude-sonnet-4-6",
        })
        assert isinstance(llm, ClaudeAdapter)

    def test_create_openai(self):
        from src.llm.factory import create_llm
        from src.llm.openai_adapter import OpenAIAdapter

        llm = create_llm({
            "provider": "openai",
            "api_key": "test",
        })
        assert isinstance(llm, OpenAIAdapter)

    def test_create_custom(self):
        from src.llm.factory import create_llm
        from src.llm.custom_adapter import CustomAdapter

        llm = create_llm({
            "provider": "custom",
            "api_key": "test",
            "base_url": "https://api.example.com",
        })
        assert isinstance(llm, CustomAdapter)

    def test_create_from_file(self):
        from src.llm.factory import create_llm

        llm = create_llm(str(PROJECT_ROOT / "config" / "llm_config.yaml"))
        assert llm is not None

    def test_create_invalid_provider(self):
        from src.llm.factory import create_llm

        with pytest.raises(ValueError, match="不支持的"):
            create_llm({"provider": "unknown"})


# ── Prompt 模板测试 ──────────────────────────────────────────

class TestPromptTemplates:
    def _make_anomaly_and_result(self):
        from src.agents.monitor_agent import MonitorAgent
        from src.agents.attribution_agent import AttributionAgent
        from src.detection.detector import AnomalyDetector
        from src.attribution.evidence_collector import EvidenceCollector

        detector = AnomalyDetector(_make_registry(), _make_loader(), _make_calendar())
        monitor = MonitorAgent(detector)
        events = monitor.run(["reg_daily"], TARGET_DATE)
        anomaly = events[0]

        attributor = AttributionAgent(
            _make_registry(),
            _make_loader(),
            EvidenceCollector(calendar=_make_calendar()),
        )
        result = attributor.run(anomaly)
        return anomaly, result

    def test_anomaly_summary_prompt(self):
        from src.llm.prompt_templates import build_anomaly_summary_prompt

        anomaly, result = self._make_anomaly_and_result()
        system, user = build_anomaly_summary_prompt(
            anomaly, result, result.evidence,
        )

        assert "数据分析助手" in system
        assert "已验证的事实" in system
        assert "异常事件" in user
        assert "日注册量" in user
        assert "证据" in user

    def test_attribution_report_prompt(self):
        from src.llm.prompt_templates import build_attribution_report_prompt

        anomaly, result = self._make_anomaly_and_result()
        system, user = build_attribution_report_prompt(
            anomaly, result, result.evidence,
        )

        assert "维度下钻" in user
        assert "百度SEM" in user

    def test_investigation_suggestion_prompt(self):
        from src.llm.prompt_templates import build_investigation_suggestion_prompt

        anomaly, result = self._make_anomaly_and_result()
        system, user = build_investigation_suggestion_prompt(anomaly, result)

        assert "排查建议" in user
        assert "贡献" in user


# ── Summarizer 测试 ──────────────────────────────────────────

class TestSummarizer:
    def _make_anomaly_and_result(self):
        from src.agents.monitor_agent import MonitorAgent
        from src.agents.attribution_agent import AttributionAgent
        from src.detection.detector import AnomalyDetector
        from src.attribution.evidence_collector import EvidenceCollector

        detector = AnomalyDetector(_make_registry(), _make_loader(), _make_calendar())
        monitor = MonitorAgent(detector)
        events = monitor.run(["reg_daily"], TARGET_DATE)
        anomaly = events[0]

        attributor = AttributionAgent(
            _make_registry(),
            _make_loader(),
            EvidenceCollector(calendar=_make_calendar()),
        )
        result = attributor.run(anomaly)
        return anomaly, result

    def test_rule_summary_produces_output(self):
        from src.llm.summarizer import build_rule_summary

        anomaly, result = self._make_anomaly_and_result()
        summary = build_rule_summary(anomaly, result)

        assert "异常摘要" in summary
        assert "主要贡献来源" in summary
        assert "已验证的事实" in summary
        assert "可能的原因" in summary
        assert "排查建议" in summary
        assert "需要补充的数据" in summary
        assert "百度SEM" in summary

    def test_summarizer_without_llm(self):
        """Summarizer 没有 LLM 时降级到规则摘要。"""
        from src.llm.summarizer import Summarizer

        anomaly, result = self._make_anomaly_and_result()
        s = Summarizer(llm=None)
        summary = s.summarize(anomaly, result)

        assert "异常摘要" in summary
        assert "百度SEM" in summary

    def test_summarizer_without_evidence(self):
        """即使不传 evidence 也应工作（从 result 中取）。"""
        from src.llm.summarizer import Summarizer

        anomaly, result = self._make_anomaly_and_result()
        s = Summarizer(llm=None)
        summary = s.summarize(anomaly, result, evidence=None)

        assert len(summary) > 100

    def test_investigation_without_llm(self):
        from src.llm.summarizer import Summarizer

        anomaly, result = self._make_anomaly_and_result()
        s = Summarizer(llm=None)
        summary = s.summarize_investigation(anomaly, result)

        assert len(summary) > 0

    def test_rule_summary_distinguishes_fact_from_conjecture(self):
        """规则摘要必须区分四类信息（视频要求）。"""
        from src.llm.summarizer import build_rule_summary

        anomaly, result = self._make_anomaly_and_result()
        summary = build_rule_summary(anomaly, result)

        # 必须包含四类标记
        assert "已验证的事实" in summary
        assert "可能的原因" in summary
        assert "排查建议" in summary
        assert "需要补充的数据" in summary


# ── 集成测试：AttributionAgent + Summarizer ──────────────────

class TestIntegration:
    def test_attribution_agent_with_summarizer(self):
        from src.agents.attribution_agent import AttributionAgent
        from src.agents.monitor_agent import MonitorAgent
        from src.detection.detector import AnomalyDetector
        from src.attribution.evidence_collector import EvidenceCollector
        from src.llm.summarizer import Summarizer

        detector = AnomalyDetector(_make_registry(), _make_loader(), _make_calendar())
        monitor = MonitorAgent(detector)
        events = monitor.run(["reg_daily"], TARGET_DATE)

        summarizer = Summarizer(llm=None)  # 无 LLM，使用规则降级
        attributor = AttributionAgent(
            _make_registry(),
            _make_loader(),
            EvidenceCollector(calendar=_make_calendar()),
            summarizer=summarizer,
        )

        result = attributor.run(events[0])
        assert "异常摘要" in result.summary
        assert result.top_contributor
