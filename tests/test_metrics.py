"""指标口径层单元测试。"""

from datetime import date
from pathlib import Path

import pandas as pd
import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
CONFIG_PATH = PROJECT_ROOT / "config" / "metrics_registry.yaml"


# ── MetricDefinition 模型测试 ───────────────────────────────

class TestMetricDefinition:
    def test_create_from_dict(self):
        from src.models.metric import MetricDefinition

        data = {
            "metric_id": "test_m",
            "metric_name": "测试指标",
            "formula": "COUNT(*)",
            "data_source": {"type": "csv", "path": "test.csv"},
            "dimensions": [{"name": "channel", "label": "渠道", "values": ["A", "B"]}],
            "priority": "P0",
        }
        m = MetricDefinition(**data)
        assert m.metric_id == "test_m"
        assert m.metric_name == "测试指标"
        assert m.data_source.type == "csv"
        assert m.dimension_names == ["channel"]
        assert m.priority == "P0"

    def test_default_values(self):
        from src.models.metric import MetricDefinition

        m = MetricDefinition(
            metric_id="x",
            metric_name="X",
            data_source={"type": "csv"},
        )
        assert m.update_time == "08:00"
        assert m.baseline_type == "近4周同期均值"
        assert m.alert_threshold.change_rate == 0.10
        assert m.alert_threshold.z_score == 2.0
        assert m.dimension_names == []


# ── MetricRegistry 测试 ─────────────────────────────────────

class TestMetricRegistry:
    def test_load_from_yaml(self):
        from src.metrics.registry import MetricRegistry

        registry = MetricRegistry(CONFIG_PATH)
        assert len(registry) == 3

    def test_get_metric(self):
        from src.metrics.registry import MetricRegistry

        registry = MetricRegistry(CONFIG_PATH)
        m = registry.get_metric("reg_daily")
        assert m.metric_name == "日注册量"
        assert m.priority == "P0"
        assert m.owner == "增长组-张三"
        assert "channel" in m.dimension_names

    def test_get_metric_not_found(self):
        from src.metrics.registry import MetricRegistry

        registry = MetricRegistry(CONFIG_PATH)
        with pytest.raises(KeyError, match="不存在"):
            registry.get_metric("nonexistent")

    def test_list_metrics(self):
        from src.metrics.registry import MetricRegistry

        registry = MetricRegistry(CONFIG_PATH)
        metrics = registry.list_metrics()
        assert len(metrics) == 3
        ids = {m.metric_id for m in metrics}
        assert ids == {"reg_daily", "dau", "pay_success_rate"}

    def test_add_metric(self):
        from src.metrics.registry import MetricRegistry
        from src.models.metric import MetricDefinition

        registry = MetricRegistry(CONFIG_PATH)
        new_metric = MetricDefinition(
            metric_id="new_m",
            metric_name="新指标",
            data_source={"type": "csv", "path": "test.csv"},
        )
        registry.add_metric(new_metric)
        assert registry.has_metric("new_m")
        assert len(registry) == 4

    def test_add_duplicate_metric(self):
        from src.metrics.registry import MetricRegistry
        from src.models.metric import MetricDefinition

        registry = MetricRegistry(CONFIG_PATH)
        dup = MetricDefinition(
            metric_id="reg_daily",
            metric_name="重复",
            data_source={"type": "csv"},
        )
        with pytest.raises(ValueError, match="已存在"):
            registry.add_metric(dup)

    def test_update_metric(self):
        from src.metrics.registry import MetricRegistry

        registry = MetricRegistry(CONFIG_PATH)
        updated = registry.update_metric("reg_daily", {"owner": "新负责人"})
        assert updated.owner == "新负责人"
        assert registry.get_metric("reg_daily").owner == "新负责人"

    def test_delete_metric(self):
        from src.metrics.registry import MetricRegistry

        registry = MetricRegistry(CONFIG_PATH)
        registry.delete_metric("pay_success_rate")
        assert not registry.has_metric("pay_success_rate")
        assert len(registry) == 2

    def test_delete_nonexistent(self):
        from src.metrics.registry import MetricRegistry

        registry = MetricRegistry(CONFIG_PATH)
        with pytest.raises(KeyError, match="不存在"):
            registry.delete_metric("nope")

    def test_save_and_reload(self, tmp_path):
        from src.metrics.registry import MetricRegistry

        registry = MetricRegistry(CONFIG_PATH)
        save_path = tmp_path / "saved.yaml"
        registry.save_to_yaml(save_path)

        reloaded = MetricRegistry(save_path)
        assert len(reloaded) == 3
        m = reloaded.get_metric("reg_daily")
        assert m.metric_name == "日注册量"

    def test_has_metric(self):
        from src.metrics.registry import MetricRegistry

        registry = MetricRegistry(CONFIG_PATH)
        assert registry.has_metric("reg_daily") is True
        assert registry.has_metric("nonexistent") is False


# ── MetricLoader 测试 ───────────────────────────────────────

class TestMetricLoader:
    def _make_loader(self):
        from src.metrics.loader import MetricLoader
        return MetricLoader(project_root=str(PROJECT_ROOT))

    def _get_reg_metric(self):
        from src.metrics.registry import MetricRegistry
        registry = MetricRegistry(CONFIG_PATH)
        return registry.get_metric("reg_daily")

    def test_load_current(self):
        loader = self._make_loader()
        metric = self._get_reg_metric()
        df = loader.load_current(metric, date(2026, 6, 12))
        assert len(df) == 1
        assert df["date"].iloc[0] == date(2026, 6, 12)
        assert df["value"].iloc[0] > 0

    def test_load_baseline(self):
        loader = self._make_loader()
        metric = self._get_reg_metric()
        df = loader.load_baseline(metric, date(2026, 6, 12), window_weeks=4)
        assert len(df) <= 4
        assert len(df) > 0
        for d in df["date"]:
            assert d < date(2026, 6, 12)

    def test_load_history(self):
        loader = self._make_loader()
        metric = self._get_reg_metric()
        df = loader.load_history(metric, date(2026, 5, 1), date(2026, 5, 31))
        assert len(df) == 31
        assert set(df.columns) == {"date", "value"}

    def test_load_by_dimension(self):
        loader = self._make_loader()
        metric = self._get_reg_metric()
        df = loader.load_by_dimension(
            metric, "channel",
            date(2026, 6, 1), date(2026, 6, 5),
        )
        assert "channel" in df.columns
        channels = df["channel"].unique()
        assert "百度SEM" in channels
        assert "抖音" in channels

    def test_load_by_invalid_dimension(self):
        loader = self._make_loader()
        metric = self._get_reg_metric()
        with pytest.raises(ValueError, match="不支持维度"):
            loader.load_by_dimension(
                metric, "nonexistent",
                date(2026, 6, 1), date(2026, 6, 5),
            )

    def test_load_current_by_dimension(self):
        loader = self._make_loader()
        metric = self._get_reg_metric()
        df = loader.load_current_by_dimension(metric, "channel", date(2026, 6, 12))
        assert len(df) == 4  # 4个渠道
        total = df["value"].sum()
        assert total > 0

    def test_load_baseline_by_dimension(self):
        loader = self._make_loader()
        metric = self._get_reg_metric()
        df = loader.load_baseline_by_dimension(
            metric, "channel", date(2026, 6, 12), window_weeks=4,
        )
        assert "channel" in df.columns
        assert "value" in df.columns
        assert len(df) == 4  # 4个渠道的均值

    def test_baidu_sem_anomaly_detectable(self):
        """验证加载器能看到百度SEM的异常下降。"""
        loader = self._make_loader()
        metric = self._get_reg_metric()

        current = loader.load_current_by_dimension(
            metric, "channel", date(2026, 6, 12),
        )
        baseline = loader.load_baseline_by_dimension(
            metric, "channel", date(2026, 6, 12),
        )

        cur_baidu = current[current["channel"] == "百度SEM"]["value"].iloc[0]
        base_baidu = baseline[baseline["channel"] == "百度SEM"]["value"].iloc[0]

        drop = (base_baidu - cur_baidu) / base_baidu
        assert drop > 0.20, f"百度SEM下降应超过20%，实际: {drop:.1%}"
