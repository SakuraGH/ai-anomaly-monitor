from datetime import date
from typing import Any

import httpx
import pandas as pd

from .base import DataSource


class APISource(DataSource):
    """HTTP API 数据源适配器。

    config 示例:
        {"base_url": "https://api.example.com",
         "auth_type": "bearer",          # bearer / header / none
         "auth_token": "xxx",
         "timeout": 30}
    指标级 data_source 配置示例:
        {"type": "api",
         "endpoint": "/metrics/query",
         "date_field": "date",
         "value_field": "value",
         "method": "POST"}
    """

    def __init__(self, config: dict[str, Any]):
        super().__init__(config)
        self.base_url = config.get("base_url", "").rstrip("/")
        self.timeout = config.get("timeout", 30)
        self._client: httpx.Client | None = None

    @property
    def client(self) -> httpx.Client:
        if self._client is None:
            headers = {}
            auth_type = self.config.get("auth_type", "none")
            if auth_type == "bearer":
                headers["Authorization"] = f"Bearer {self.config['auth_token']}"
            elif auth_type == "header":
                headers[self.config.get("auth_header_name", "X-API-Key")] = (
                    self.config["auth_token"]
                )

            self._client = httpx.Client(
                base_url=self.base_url,
                headers=headers,
                timeout=self.timeout,
            )
        return self._client

    def _resolve_metric_config(
        self, metric_config: dict[str, Any] | None
    ) -> dict[str, str]:
        mc = metric_config or {}
        ds = mc.get("data_source", mc)
        return {
            "endpoint": ds.get("endpoint", "/metrics/query"),
            "date_field": ds.get("date_field", "date"),
            "value_field": ds.get("value_field", "value"),
            "method": ds.get("method", "POST"),
        }

    def _request(
        self,
        cfg: dict[str, str],
        params: dict[str, Any],
    ) -> list[dict]:
        method = cfg["method"].upper()
        endpoint = cfg["endpoint"]

        if method == "GET":
            resp = self.client.get(endpoint, params=params)
        else:
            resp = self.client.post(endpoint, json=params)

        resp.raise_for_status()
        data = resp.json()

        if isinstance(data, dict) and "data" in data:
            return data["data"]
        return data

    def query_metric(
        self,
        metric_id: str,
        start_date: date,
        end_date: date,
        metric_config: dict[str, Any] | None = None,
    ) -> pd.DataFrame:
        cfg = self._resolve_metric_config(metric_config)
        params = {
            "metric_id": metric_id,
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat(),
        }
        records = self._request(cfg, params)
        df = pd.DataFrame(records)

        date_field = cfg["date_field"]
        value_field = cfg["value_field"]

        if date_field in df.columns:
            df = df.rename(columns={date_field: "date", value_field: "value"})

        df["date"] = pd.to_datetime(df["date"]).dt.date
        return df[["date", "value"]].sort_values("date").reset_index(drop=True)

    def query_metric_by_dimension(
        self,
        metric_id: str,
        dimension: str,
        start_date: date,
        end_date: date,
        metric_config: dict[str, Any] | None = None,
    ) -> pd.DataFrame:
        cfg = self._resolve_metric_config(metric_config)
        params = {
            "metric_id": metric_id,
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat(),
            "dimension": dimension,
        }
        records = self._request(cfg, params)
        df = pd.DataFrame(records)

        date_field = cfg["date_field"]
        value_field = cfg["value_field"]

        if date_field in df.columns and date_field != "date":
            df = df.rename(columns={date_field: "date"})
        if value_field in df.columns and value_field != "value":
            df = df.rename(columns={value_field: "value"})

        df["date"] = pd.to_datetime(df["date"]).dt.date
        cols = ["date", dimension, "value"]
        return df[cols].sort_values(["date", dimension]).reset_index(drop=True)

    def test_connection(self) -> bool:
        try:
            resp = self.client.get("/health")
            return resp.status_code < 500
        except Exception:
            return False

    def close(self):
        if self._client is not None:
            self._client.close()
            self._client = None
