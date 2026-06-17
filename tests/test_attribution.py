"""归因下钻层单元测试。"""

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


def _get_reg_metric():
    return _make_registry().get_metric("reg_daily")


def _make_anomaly_event():
    from src.detection.detector import AnomalyDetector
    detector = AnomalyDetector(_make_registry(), _make_loader(), _make_calendar())
    return detector.detect("reg_daily", TARGET_DATE)


# ── ContributionItem / DrillDownLevel 模型测试 ──────────────

class TestModels:
    def test_contribution_item_change_rate(self):
        from src.models.attribution_result import ContributionItem
        item = ContributionItem(
            dimension="channel",
            dimension_value="百度SEM",
            current_value=200,
            baseline_value=350,
            change_amount=-150,
            contribution_pct=0.60,
        )
        assert item.change_rate == pytest.approx(-150 / 350, abs=0.01)

    def test_contribution_item_zero_baseline(self):
        from src.models.attribution_result import ContributionItem
        item = ContributionItem(
            dimension="channel",
            dimension_value="新渠道",
            current_value=100,
            baseline_value=0,
            change_amount=100,
            contribution_pct=0.10,
        )
        assert item.change_rate == 0.0

    def test_attribution_result_creation(self):
        from src.models.attribution_result import AttributionResult
        r = AttributionResult(
            metric_id="reg_daily",
            metric_name="日注册量",
            event_date=TARGET_DATE,
            current_value=700,
            baseline_value=860,
            change_rate=-0.186,
        )
        assert r.metric_id == "reg_daily"
        assert r.drill_levels == []


# ── dimension_drill 单维度贡献度测试 ────────────────────────

class TestDimensionDrill:
    def test_drill_by_channel(self):
        from src.attribution.dimension_drill import drill_by_dimension
        metric = _get_reg_metric()
        loader = _make_loader()

        level = drill_by_dimension(metric, "channel", TARGET_DATE, loader)

        assert level.dimension == "channel"
        assert len(level.items) > 0
        assert level.total_change < 0  # 总体下降

    def test_baidu_sem_top_contributor(self):
        """百度SEM应是贡献最大的下降因素。"""
        from src.attribution.dimension_drill import drill_by_dimension
        metric = _get_reg_metric()
        loader = _make_loader()

        level = drill_by_dimension(metric, "channel", TARGET_DATE, loader)

        top = level.items[0]
        assert top.dimension_value == "百度SEM"
        assert top.contribution_pct > 0.40, (
            f"百度SEM贡献应超过40%，实际: {top.contribution_pct:.0%}"
        )

    def test_baidu_sem_contribution_dominant(self):
        """百度SEM应是最大的下降贡献者（>40%）。

        由于其他渠道的随机波动可能抵消部分变化，
        百度SEM贡献占比可能超过100%，这在业务中很正常。
        """
        from src.attribution.dimension_drill import drill_by_dimension
        metric = _get_reg_metric()
        loader = _make_loader()

        level = drill_by_dimension(metric, "channel", TARGET_DATE, loader)
        baidu = next(i for i in level.items if i.dimension_value == "百度SEM")
        assert baidu.contribution_pct > 0.40
        assert baidu.change_amount < 0  # 确认是下降

    def test_contribution_sums_to_100(self):
        """所有维度值的贡献占比之和应为100%（top_n足够大时）。"""
        from src.attribution.dimension_drill import drill_by_dimension
        metric = _get_reg_metric()
        loader = _make_loader()

        level = drill_by_dimension(metric, "channel", TARGET_DATE, loader, top_n=10)
        total = sum(item.contribution_pct for item in level.items)
        assert total == pytest.approx(1.0, abs=0.05)

    def test_drill_by_region(self):
        from src.attribution.dimension_drill import drill_by_dimension
        metric = _get_reg_metric()
        loader = _make_loader()

        level = drill_by_dimension(metric, "region", TARGET_DATE, loader)
        assert level.dimension == "region"
        assert len(level.items) == 5  # 5个地域

    def test_drill_by_device(self):
        from src.attribution.dimension_drill import drill_by_dimension
        metric = _get_reg_metric()
        loader = _make_loader()

        level = drill_by_dimension(metric, "device", TARGET_DATE, loader)
        assert level.dimension == "device"
        assert len(level.items) == 3  # 3种设备

    def test_drill_all_dimensions(self):
        from src.attribution.dimension_drill import drill_all_dimensions
        metric = _get_reg_metric()
        loader = _make_loader()

        levels = drill_all_dimensions(metric, TARGET_DATE, loader)
        assert len(levels) == 3  # channel, region, device
        dims = {l.dimension for l in levels}
        assert dims == {"channel", "region", "device"}

    def test_items_sorted_by_abs_contribution(self):
        from src.attribution.dimension_drill import drill_by_dimension
        metric = _get_reg_metric()
        loader = _make_loader()

        level = drill_by_dimension(metric, "channel", TARGET_DATE, loader)
        pcts = [abs(item.contribution_pct) for item in level.items]
        assert pcts == sorted(pcts, reverse=True)


# ── multi_level_drill 多层下钻测试 ──────────────────────────

class TestMultiLevelDrill:
    def test_multi_level_from_channel(self):
        """从渠道维度的 top1（百度SEM）出发，继续按地域和设备下钻。"""
        from src.attribution.dimension_drill import drill_by_dimension
        from src.attribution.multi_level_drill import multi_level_drill

        metric = _get_reg_metric()
        loader = _make_loader()

        first_level = drill_by_dimension(metric, "channel", TARGET_DATE, loader)
        deeper = multi_level_drill(
            metric, TARGET_DATE, loader, first_level, max_depth=3,
        )

        assert len(deeper) > 0
        # 第二层应该是 region 或 device（排除已用的 channel）
        for level in deeper:
            assert level.dimension != "channel"
            assert "channel" in level.filter_context
            assert level.filter_context["channel"] == "百度SEM"

    def test_multi_level_has_filter_context(self):
        from src.attribution.dimension_drill import drill_by_dimension
        from src.attribution.multi_level_drill import multi_level_drill

        metric = _get_reg_metric()
        loader = _make_loader()

        first_level = drill_by_dimension(metric, "channel", TARGET_DATE, loader)
        deeper = multi_level_drill(metric, TARGET_DATE, loader, first_level)

        if len(deeper) >= 2:
            # 第三层应包含两个过滤条件
            assert len(deeper[1].filter_context) == 2

    def test_multi_level_respects_max_depth(self):
        from src.attribution.dimension_drill import drill_by_dimension
        from src.attribution.multi_level_drill import multi_level_drill

        metric = _get_reg_metric()
        loader = _make_loader()

        first_level = drill_by_dimension(metric, "channel", TARGET_DATE, loader)
        deeper = multi_level_drill(
            metric, TARGET_DATE, loader, first_level, max_depth=1,
        )
        # max_depth=1 时不再继续（第一层不算在内，remaining最多0层）
        # 实际上 max_depth-1=0 所以 deeper 可能为空
        assert len(deeper) == 0


# ── evidence_collector 证据收集测试 ──────────────────────────

class TestEvidenceCollector:
    def _make_attribution_result(self):
        from src.attribution.dimension_drill import drill_by_dimension
        from src.models.attribution_result import AttributionResult

        metric = _get_reg_metric()
        loader = _make_loader()
        level = drill_by_dimension(metric, "channel", TARGET_DATE, loader)

        return AttributionResult(
            metric_id="reg_daily",
            metric_name="日注册量",
            event_date=TARGET_DATE,
            current_value=700,
            baseline_value=860,
            change_rate=-0.186,
            drill_levels=[level],
        )

    def test_collect_basic(self):
        from src.attribution.evidence_collector import EvidenceCollector

        anomaly = _make_anomaly_event()
        assert anomaly is not None
        attribution = self._make_attribution_result()

        collector = EvidenceCollector(calendar=_make_calendar())
        pack = collector.collect(anomaly, attribution)

        assert pack.metric_id == "reg_daily"
        assert len(pack.items) > 0

    def test_metric_evidence_present(self):
        from src.attribution.evidence_collector import EvidenceCollector

        anomaly = _make_anomaly_event()
        attribution = self._make_attribution_result()
        collector = EvidenceCollector(calendar=_make_calendar())
        pack = collector.collect(anomaly, attribution)

        metric_items = [i for i in pack.items if i.source == "metric"]
        assert len(metric_items) >= 1
        assert any("日注册量" in i.content for i in metric_items)

    def test_attribution_evidence_present(self):
        from src.attribution.evidence_collector import EvidenceCollector

        anomaly = _make_anomaly_event()
        attribution = self._make_attribution_result()
        collector = EvidenceCollector(calendar=_make_calendar())
        pack = collector.collect(anomaly, attribution)

        attr_items = [i for i in pack.items if i.source == "attribution"]
        assert len(attr_items) > 0
        assert any("百度SEM" in i.content for i in attr_items)

    def test_all_evidence_verified(self):
        from src.attribution.evidence_collector import EvidenceCollector

        anomaly = _make_anomaly_event()
        attribution = self._make_attribution_result()
        collector = EvidenceCollector(calendar=_make_calendar())
        pack = collector.collect(anomaly, attribution)

        for item in pack.items:
            assert item.verified is True

    def test_no_calendar_still_works(self):
        from src.attribution.evidence_collector import EvidenceCollector

        anomaly = _make_anomaly_event()
        attribution = self._make_attribution_result()
        collector = EvidenceCollector(calendar=None)
        pack = collector.collect(anomaly, attribution)

        assert len(pack.items) > 0
        calendar_items = [i for i in pack.items if i.source == "calendar"]
        assert len(calendar_items) == 0
