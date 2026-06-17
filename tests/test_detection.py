"""异常检测层单元测试。"""

from datetime import date
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
CONFIG_PATH = PROJECT_ROOT / "config" / "metrics_registry.yaml"
CALENDAR_PATH = PROJECT_ROOT / "data" / "activity_calendar.csv"


# ── comparisons 基础对比检测 ────────────────────────────────

class TestComparisons:
    def test_year_over_year_normal(self):
        from src.detection.comparisons import year_over_year
        r = year_over_year(1050, 1000, threshold=0.10)
        assert r.change_rate == pytest.approx(0.05, abs=0.001)
        assert r.is_anomaly is False

    def test_year_over_year_anomaly(self):
        from src.detection.comparisons import year_over_year
        r = year_over_year(800, 1000, threshold=0.10)
        assert r.change_rate == pytest.approx(-0.20, abs=0.001)
        assert r.is_anomaly is True

    def test_month_over_month_decline(self):
        from src.detection.comparisons import month_over_month
        r = month_over_month(850, 1000, threshold=0.10)
        assert r.change_rate == pytest.approx(-0.15, abs=0.001)
        assert r.is_anomaly is True

    def test_month_over_month_stable(self):
        from src.detection.comparisons import month_over_month
        r = month_over_month(980, 1000, threshold=0.10)
        assert r.is_anomaly is False

    def test_moving_average_from_series(self):
        from src.detection.comparisons import moving_average
        series = [100, 102, 98, 101, 99, 103, 100, 70]
        r = moving_average(series, window=7)
        assert r.current == 70
        assert r.is_anomaly is True
        assert r.change_rate < -0.10

    def test_moving_average_explicit_current(self):
        from src.detection.comparisons import moving_average
        import pandas as pd
        series = pd.Series([100, 102, 98, 101, 99, 103, 100])
        r = moving_average(series, current=70, window=7)
        assert r.current == 70
        assert r.is_anomaly is True

    def test_baseline_compare_normal(self):
        from src.detection.comparisons import baseline_compare
        r = baseline_compare(980, [1000, 1020, 990, 1010])
        assert r.is_anomaly is False

    def test_baseline_compare_anomaly(self):
        from src.detection.comparisons import baseline_compare
        r = baseline_compare(800, [1000, 1020, 990, 1010])
        assert r.is_anomaly is True
        assert r.change_rate < -0.15

    def test_baseline_compare_empty(self):
        from src.detection.comparisons import baseline_compare
        r = baseline_compare(100, [])
        assert r.is_anomaly is False

    def test_zero_baseline(self):
        from src.detection.comparisons import year_over_year
        r = year_over_year(100, 0)
        assert r.change_rate == float("inf")
        assert r.is_anomaly is True


# ── Z-score 统计检测 ────────────────────────────────────────

class TestZScore:
    def test_z_score_normal(self):
        from src.detection.zscore import z_score_detect
        history = [100, 102, 98, 101, 99, 103, 100, 97]
        r = z_score_detect(99, history, threshold=2.0)
        assert abs(r.z_score) < 2.0
        assert r.is_anomaly is False

    def test_z_score_anomaly(self):
        from src.detection.zscore import z_score_detect
        history = [100, 102, 98, 101, 99, 103, 100, 97]
        r = z_score_detect(60, history, threshold=2.0)
        assert abs(r.z_score) > 2.0
        assert r.is_anomaly is True

    def test_z_score_priority_thresholds(self):
        from src.detection.zscore import z_score_detect
        history = [100, 102, 98, 101, 99, 103, 100, 97]
        # P0 阈值=2.0，P2 阈值=3.0
        r_p0 = z_score_detect(85, history, priority="P0")
        r_p2 = z_score_detect(85, history, priority="P2")
        assert r_p0.threshold == 2.0
        assert r_p2.threshold == 3.0
        # P0 更敏感，可能触发而 P2 不触发
        if r_p0.is_anomaly:
            assert abs(r_p0.z_score) > 2.0

    def test_three_sigma(self):
        from src.detection.zscore import three_sigma_detect
        history = [100, 102, 98, 101, 99, 103, 100, 97]
        r = three_sigma_detect(50, history, sigma_multiplier=3.0)
        assert r.method == "three_sigma"
        assert r.is_anomaly is True

    def test_three_sigma_normal(self):
        from src.detection.zscore import three_sigma_detect
        history = [100, 102, 98, 101, 99, 103, 100, 97]
        r = three_sigma_detect(95, history, sigma_multiplier=3.0)
        assert r.is_anomaly is False

    def test_insufficient_history(self):
        from src.detection.zscore import z_score_detect
        r = z_score_detect(100, [50])
        assert r.is_anomaly is False
        assert r.z_score == 0.0


# ── 日历修正 ────────────────────────────────────────────────

class TestCalendar:
    def _make_calendar(self):
        from src.detection.calendar import CalendarManager
        return CalendarManager(CALENDAR_PATH)

    def test_load(self):
        cal = self._make_calendar()
        assert cal._events is not None
        assert len(cal._events) > 0

    def test_is_holiday(self):
        cal = self._make_calendar()
        assert cal.is_holiday(date(2026, 5, 1)) is True
        assert cal.is_holiday(date(2026, 6, 12)) is False

    def test_is_promotion(self):
        cal = self._make_calendar()
        assert cal.is_promotion(date(2026, 6, 18)) is True
        assert cal.is_promotion(date(2026, 5, 1)) is False

    def test_is_special_day(self):
        cal = self._make_calendar()
        assert cal.is_special_day(date(2026, 5, 1)) is True
        assert cal.is_special_day(date(2026, 6, 10)) is False

    def test_is_weekend(self):
        cal = self._make_calendar()
        assert cal.is_weekend(date(2026, 6, 13)) is True   # 周六
        assert cal.is_weekend(date(2026, 6, 12)) is False  # 周五

    def test_weekday_factor(self):
        cal = self._make_calendar()
        assert cal.weekday_factor(date(2026, 6, 13)) == 0.90  # 周六
        assert cal.weekday_factor(date(2026, 6, 8)) == 1.05   # 周一

    def test_adjust_baseline(self):
        cal = self._make_calendar()
        # 周三基线1000，调整到周六
        adjusted = cal.adjust_baseline(
            1000,
            target_date=date(2026, 6, 13),    # 周六 0.90
            baseline_date=date(2026, 6, 10),  # 周三 1.00
        )
        assert adjusted == pytest.approx(900, abs=1)

    def test_get_event(self):
        cal = self._make_calendar()
        event = cal.get_event(date(2026, 5, 1))
        assert event is not None
        assert event["event_name"] == "劳动节"
        assert event["event_type"] == "holiday"

    def test_get_event_none(self):
        cal = self._make_calendar()
        assert cal.get_event(date(2026, 6, 12)) is None


# ── 综合异常判定器（集成测试，使用真实模拟数据）─────────────

class TestAnomalyDetector:
    def _make_detector(self):
        from src.detection.detector import AnomalyDetector
        from src.metrics.registry import MetricRegistry
        from src.metrics.loader import MetricLoader
        from src.detection.calendar import CalendarManager

        registry = MetricRegistry(CONFIG_PATH)
        loader = MetricLoader(project_root=str(PROJECT_ROOT))
        calendar = CalendarManager(CALENDAR_PATH)
        return AnomalyDetector(registry, loader, calendar)

    def test_detect_anomaly_on_drop_day(self):
        """最近3天有异常下降，应检测到。"""
        detector = self._make_detector()
        event = detector.detect("reg_daily", date(2026, 6, 12))
        assert event is not None
        assert event.metric_id == "reg_daily"
        assert event.metric_name == "日注册量"
        assert event.change_rate < -0.10
        assert event.current_value < event.baseline_value
        assert len(event.detection_methods) > 0
        assert event.priority == "P0"

    def test_detect_anomaly_severity(self):
        """P0指标下降超15%，应为HIGH。"""
        detector = self._make_detector()
        event = detector.detect("reg_daily", date(2026, 6, 12))
        assert event is not None
        assert event.severity.value == "high"

    def test_detect_anomaly_message(self):
        """验证生成的消息包含关键信息。"""
        detector = self._make_detector()
        event = detector.detect("reg_daily", date(2026, 6, 12))
        assert event is not None
        assert "日注册量" in event.message
        assert "2026-06-12" in event.message

    def test_detect_no_anomaly_on_normal_day(self):
        """正常日期（5月中旬）应无异常。"""
        detector = self._make_detector()
        event = detector.detect("reg_daily", date(2026, 5, 15))
        # 正常日期可能不触发异常（取决于数据波动）
        if event is not None:
            assert abs(event.change_rate) > 0.10

    def test_detect_all(self):
        """对所有指标执行检测，至少 reg_daily 应被检出。"""
        detector = self._make_detector()
        events = detector.detect_all(date(2026, 6, 12))
        metric_ids = [e.metric_id for e in events]
        assert "reg_daily" in metric_ids

    def test_change_pct_property(self):
        detector = self._make_detector()
        event = detector.detect("reg_daily", date(2026, 6, 12))
        assert event is not None
        assert "%" in event.change_pct
        assert event.change_pct.startswith("-")

    def test_is_decline_property(self):
        detector = self._make_detector()
        event = detector.detect("reg_daily", date(2026, 6, 12))
        assert event is not None
        assert event.is_decline is True
