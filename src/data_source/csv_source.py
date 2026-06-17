from datetime import date
from pathlib import Path
from typing import Any

import pandas as pd

from .base import DataSource


class CSVSource(DataSource):
    """CSV / Excel 文件数据源适配器。

    config 示例:
        {"base_dir": "data/"}          # 可选，文件路径的根目录
    指标级 data_source 配置示例:
        {"type": "csv", "path": "data/sample.csv",
         "date_column": "date", "value_column": "register_count"}
    """

    def __init__(self, config: dict[str, Any]):
        super().__init__(config)
        self.base_dir = Path(config.get("base_dir", "."))
        self._cache: dict[str, pd.DataFrame] = {}

    def _load_file(self, file_path: str) -> pd.DataFrame:
        if file_path in self._cache:
            return self._cache[file_path]

        full_path = self.base_dir / file_path
        suffix = full_path.suffix.lower()

        if suffix in (".xlsx", ".xls"):
            df = pd.read_excel(full_path)
        else:
            df = pd.read_csv(full_path, encoding="utf-8-sig")

        self._cache[file_path] = df
        return df

    def _resolve_metric_config(
        self, metric_config: dict[str, Any] | None
    ) -> tuple[str, str, str]:
        """从 metric_config 中提取文件路径、日期列和值列。"""
        mc = metric_config or {}
        ds = mc.get("data_source", mc)
        file_path = ds.get("path", "")
        date_col = ds.get("date_column", "date")
        value_col = ds.get("value_column", "value")
        return file_path, date_col, value_col

    def _filter_by_date(
        self, df: pd.DataFrame, date_col: str, start_date: date, end_date: date
    ) -> pd.DataFrame:
        df = df.copy()
        df[date_col] = pd.to_datetime(df[date_col]).dt.date
        mask = (df[date_col] >= start_date) & (df[date_col] <= end_date)
        return df[mask]

    def query_metric(
        self,
        metric_id: str,
        start_date: date,
        end_date: date,
        metric_config: dict[str, Any] | None = None,
    ) -> pd.DataFrame:
        file_path, date_col, value_col = self._resolve_metric_config(metric_config)
        df = self._load_file(file_path)

        if "metric_id" in df.columns:
            df = df[df["metric_id"] == metric_id]

        df = self._filter_by_date(df, date_col, start_date, end_date)

        result = (
            df.groupby(date_col)[value_col]
            .sum()
            .reset_index()
            .rename(columns={date_col: "date", value_col: "value"})
        )
        result = result.sort_values("date").reset_index(drop=True)
        return result

    def query_metric_by_dimension(
        self,
        metric_id: str,
        dimension: str,
        start_date: date,
        end_date: date,
        metric_config: dict[str, Any] | None = None,
    ) -> pd.DataFrame:
        file_path, date_col, value_col = self._resolve_metric_config(metric_config)
        df = self._load_file(file_path)

        if "metric_id" in df.columns:
            df = df[df["metric_id"] == metric_id]

        if dimension not in df.columns:
            raise ValueError(
                f"维度 '{dimension}' 不存在于数据中，可用列: {list(df.columns)}"
            )

        df = self._filter_by_date(df, date_col, start_date, end_date)

        result = (
            df.groupby([date_col, dimension])[value_col]
            .sum()
            .reset_index()
            .rename(columns={date_col: "date", value_col: "value"})
        )
        result = result.sort_values(["date", dimension]).reset_index(drop=True)
        return result

    def test_connection(self) -> bool:
        return self.base_dir.exists()

    def clear_cache(self):
        self._cache.clear()
