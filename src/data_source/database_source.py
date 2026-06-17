from datetime import date
from typing import Any

import pandas as pd
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine


from .base import DataSource


class DatabaseSource(DataSource):
    """数据库数据源适配器（MySQL / PostgreSQL / SQLite）。

    config 示例:
        {"url": "sqlite:///data/app.db"}
    指标级 data_source 配置示例:
        {"type": "database",
         "table": "metrics_daily",
         "date_column": "dt",
         "value_column": "value",
         "metric_id_column": "metric_id"}
    """

    def __init__(self, config: dict[str, Any]):
        super().__init__(config)
        self._engine: Engine | None = None

    @property
    def engine(self) -> Engine:
        if self._engine is None:
            self._engine = create_engine(self.config["url"])
        return self._engine

    def _resolve_metric_config(
        self, metric_config: dict[str, Any] | None
    ) -> dict[str, str]:
        mc = metric_config or {}
        ds = mc.get("data_source", mc)
        return {
            "table": ds.get("table", "metrics"),
            "date_column": ds.get("date_column", "date"),
            "value_column": ds.get("value_column", "value"),
            "metric_id_column": ds.get("metric_id_column", "metric_id"),
        }

    def query_metric(
        self,
        metric_id: str,
        start_date: date,
        end_date: date,
        metric_config: dict[str, Any] | None = None,
    ) -> pd.DataFrame:
        cfg = self._resolve_metric_config(metric_config)
        sql = text(
            f"SELECT {cfg['date_column']} AS date, "
            f"SUM({cfg['value_column']}) AS value "
            f"FROM {cfg['table']} "
            f"WHERE {cfg['metric_id_column']} = :metric_id "
            f"  AND {cfg['date_column']} >= :start_date "
            f"  AND {cfg['date_column']} <= :end_date "
            f"GROUP BY {cfg['date_column']} "
            f"ORDER BY {cfg['date_column']}"
        )
        with self.engine.connect() as conn:
            df = pd.read_sql(
                sql,
                conn,
                params={
                    "metric_id": metric_id,
                    "start_date": start_date.isoformat(),
                    "end_date": end_date.isoformat(),
                },
            )
        df["date"] = pd.to_datetime(df["date"]).dt.date
        return df

    def query_metric_by_dimension(
        self,
        metric_id: str,
        dimension: str,
        start_date: date,
        end_date: date,
        metric_config: dict[str, Any] | None = None,
    ) -> pd.DataFrame:
        cfg = self._resolve_metric_config(metric_config)
        sql = text(
            f"SELECT {cfg['date_column']} AS date, "
            f"{dimension}, "
            f"SUM({cfg['value_column']}) AS value "
            f"FROM {cfg['table']} "
            f"WHERE {cfg['metric_id_column']} = :metric_id "
            f"  AND {cfg['date_column']} >= :start_date "
            f"  AND {cfg['date_column']} <= :end_date "
            f"GROUP BY {cfg['date_column']}, {dimension} "
            f"ORDER BY {cfg['date_column']}, {dimension}"
        )
        with self.engine.connect() as conn:
            df = pd.read_sql(
                sql,
                conn,
                params={
                    "metric_id": metric_id,
                    "start_date": start_date.isoformat(),
                    "end_date": end_date.isoformat(),
                },
            )
        df["date"] = pd.to_datetime(df["date"]).dt.date
        return df

    def test_connection(self) -> bool:
        try:
            with self.engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            return True
        except Exception:
            return False

    def close(self):
        if self._engine is not None:
            self._engine.dispose()
            self._engine = None
