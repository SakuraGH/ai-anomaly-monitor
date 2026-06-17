from datetime import date, timedelta
from typing import Any

import pandas as pd

from src.data_source.base import DataSource
from src.data_source.csv_source import CSVSource
from src.data_source.database_source import DatabaseSource
from src.data_source.api_source import APISource
from src.models.metric import MetricDefinition


_SOURCE_CLASSES: dict[str, type[DataSource]] = {
    "csv": CSVSource,
    "database": DatabaseSource,
    "api": APISource,
}


class MetricLoader:
    """指标数据加载器：根据指标配置自动选择数据源，加载当前值和基线。"""

    def __init__(
        self,
        source_configs: dict[str, dict[str, Any]] | None = None,
        baseline_window_weeks: int = 4,
        project_root: str = ".",
    ):
        self.baseline_window_weeks = baseline_window_weeks
        self.project_root = project_root
        self._source_configs = source_configs or {}
        self._sources: dict[str, DataSource] = {}

    def _get_source(self, metric: MetricDefinition) -> DataSource:
        source_type = metric.data_source.type
        cache_key = f"{source_type}:{metric.metric_id}"

        if cache_key not in self._sources:
            cls = _SOURCE_CLASSES.get(source_type)
            if cls is None:
                raise ValueError(f"不支持的数据源类型: {source_type}")

            base_config = self._source_configs.get(source_type, {})

            if source_type == "csv":
                base_config.setdefault("base_dir", self.project_root)
            elif source_type == "database":
                base_config.setdefault("url", "sqlite:///data/anomaly_monitor.db")

            self._sources[cache_key] = cls(base_config)

        return self._sources[cache_key]

    def _metric_config_dict(self, metric: MetricDefinition) -> dict[str, Any]:
        return {"data_source": metric.data_source.model_dump()}

    def load_current(
        self,
        metric: MetricDefinition,
        target_date: date,
    ) -> pd.DataFrame:
        """加载指定日期的指标汇总值。返回单行 DataFrame: date, value"""
        source = self._get_source(metric)
        return source.query_metric(
            metric.metric_id,
            target_date,
            target_date,
            self._metric_config_dict(metric),
        )

    def load_baseline(
        self,
        metric: MetricDefinition,
        target_date: date,
        window_weeks: int | None = None,
    ) -> pd.DataFrame:
        """加载基线期数据（近 N 周同一星期几的数据）。

        例如 target_date 是周三，则取过去 4 个周三的数据。
        返回 DataFrame: date, value
        """
        weeks = window_weeks or self.baseline_window_weeks
        source = self._get_source(metric)
        cfg = self._metric_config_dict(metric)

        frames = []
        for w in range(1, weeks + 1):
            ref_date = target_date - timedelta(weeks=w)
            df = source.query_metric(
                metric.metric_id, ref_date, ref_date, cfg,
            )
            if not df.empty:
                frames.append(df)

        if not frames:
            return pd.DataFrame(columns=["date", "value"])
        return pd.concat(frames, ignore_index=True).sort_values("date").reset_index(drop=True)

    def load_history(
        self,
        metric: MetricDefinition,
        start_date: date,
        end_date: date,
    ) -> pd.DataFrame:
        """加载一段时间范围的每日汇总数据。返回 DataFrame: date, value"""
        source = self._get_source(metric)
        return source.query_metric(
            metric.metric_id, start_date, end_date,
            self._metric_config_dict(metric),
        )

    def load_by_dimension(
        self,
        metric: MetricDefinition,
        dimension: str,
        start_date: date,
        end_date: date,
    ) -> pd.DataFrame:
        """加载指标按某个维度拆分的每日数据。返回 DataFrame: date, {dimension}, value"""
        if dimension not in metric.dimension_names:
            raise ValueError(
                f"指标 '{metric.metric_id}' 不支持维度 '{dimension}'，"
                f"可用维度: {metric.dimension_names}"
            )
        source = self._get_source(metric)
        return source.query_metric_by_dimension(
            metric.metric_id, dimension, start_date, end_date,
            self._metric_config_dict(metric),
        )

    def load_current_by_dimension(
        self,
        metric: MetricDefinition,
        dimension: str,
        target_date: date,
    ) -> pd.DataFrame:
        """加载指定日期的维度拆分数据。"""
        return self.load_by_dimension(metric, dimension, target_date, target_date)

    def load_baseline_by_dimension(
        self,
        metric: MetricDefinition,
        dimension: str,
        target_date: date,
        window_weeks: int | None = None,
    ) -> pd.DataFrame:
        """加载基线期的维度拆分数据，并按维度值聚合为均值。

        返回 DataFrame: {dimension}, value（均值）
        """
        weeks = window_weeks or self.baseline_window_weeks
        source = self._get_source(metric)
        cfg = self._metric_config_dict(metric)

        frames = []
        for w in range(1, weeks + 1):
            ref_date = target_date - timedelta(weeks=w)
            df = source.query_metric_by_dimension(
                metric.metric_id, dimension, ref_date, ref_date, cfg,
            )
            if not df.empty:
                frames.append(df)

        if not frames:
            return pd.DataFrame(columns=[dimension, "value"])

        combined = pd.concat(frames, ignore_index=True)
        result = (
            combined.groupby(dimension)["value"]
            .mean()
            .reset_index()
        )
        return result
