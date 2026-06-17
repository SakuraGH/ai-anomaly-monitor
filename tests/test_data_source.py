"""数据接入层单元测试。"""

import sqlite3
import tempfile
from datetime import date
from pathlib import Path

import pandas as pd
import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent


# ── CSV 适配器测试 ──────────────────────────────────────────

class TestCSVSource:
    def _make_source(self):
        from src.data_source.csv_source import CSVSource
        return CSVSource({"base_dir": str(PROJECT_ROOT)})

    def _metric_config(self):
        return {
            "data_source": {
                "type": "csv",
                "path": "data/sample_metrics.csv",
                "date_column": "date",
                "value_column": "register_count",
            }
        }

    def test_connection(self):
        source = self._make_source()
        assert source.test_connection() is True

    def test_connection_bad_dir(self):
        from src.data_source.csv_source import CSVSource
        source = CSVSource({"base_dir": "/nonexistent/path"})
        assert source.test_connection() is False

    def test_query_metric_returns_dataframe(self):
        source = self._make_source()
        df = source.query_metric(
            "reg_daily",
            date(2026, 5, 1),
            date(2026, 5, 31),
            self._metric_config(),
        )
        assert isinstance(df, pd.DataFrame)
        assert set(df.columns) == {"date", "value"}
        assert len(df) > 0

    def test_query_metric_date_range(self):
        source = self._make_source()
        df = source.query_metric(
            "reg_daily",
            date(2026, 5, 10),
            date(2026, 5, 15),
            self._metric_config(),
        )
        assert len(df) == 6
        assert df["date"].min() == date(2026, 5, 10)
        assert df["date"].max() == date(2026, 5, 15)

    def test_query_metric_sorted_by_date(self):
        source = self._make_source()
        df = source.query_metric(
            "reg_daily",
            date(2026, 5, 1),
            date(2026, 5, 31),
            self._metric_config(),
        )
        dates = df["date"].tolist()
        assert dates == sorted(dates)

    def test_query_metric_by_dimension_channel(self):
        source = self._make_source()
        df = source.query_metric_by_dimension(
            "reg_daily",
            "channel",
            date(2026, 6, 1),
            date(2026, 6, 12),
            self._metric_config(),
        )
        assert isinstance(df, pd.DataFrame)
        assert "channel" in df.columns
        assert "value" in df.columns
        channels = df["channel"].unique()
        assert "百度SEM" in channels
        assert "抖音" in channels

    def test_query_metric_by_dimension_region(self):
        source = self._make_source()
        df = source.query_metric_by_dimension(
            "reg_daily",
            "region",
            date(2026, 6, 1),
            date(2026, 6, 5),
            self._metric_config(),
        )
        regions = df["region"].unique()
        assert len(regions) == 5

    def test_query_metric_by_dimension_invalid(self):
        source = self._make_source()
        with pytest.raises(ValueError, match="维度.*不存在"):
            source.query_metric_by_dimension(
                "reg_daily",
                "nonexistent",
                date(2026, 6, 1),
                date(2026, 6, 5),
                self._metric_config(),
            )

    def test_baidu_sem_drop_visible(self):
        """验证最近3天百度SEM数据确实下降了。"""
        source = self._make_source()
        cfg = self._metric_config()

        normal = source.query_metric_by_dimension(
            "reg_daily", "channel",
            date(2026, 6, 1), date(2026, 6, 9), cfg,
        )
        anomaly = source.query_metric_by_dimension(
            "reg_daily", "channel",
            date(2026, 6, 10), date(2026, 6, 12), cfg,
        )

        normal_baidu = normal[normal["channel"] == "百度SEM"]["value"].mean()
        anomaly_baidu = anomaly[anomaly["channel"] == "百度SEM"]["value"].mean()

        drop_rate = (normal_baidu - anomaly_baidu) / normal_baidu
        assert drop_rate > 0.25, f"百度SEM下降幅度应超过25%，实际: {drop_rate:.1%}"

    def test_excel_file(self, tmp_path):
        """验证 Excel 文件能正常读取。"""
        from src.data_source.csv_source import CSVSource

        df = pd.DataFrame({
            "date": ["2026-06-01", "2026-06-02"],
            "metric_id": ["test", "test"],
            "value": [100, 200],
        })
        excel_path = tmp_path / "test.xlsx"
        df.to_excel(excel_path, index=False)

        source = CSVSource({"base_dir": str(tmp_path)})
        result = source.query_metric(
            "test",
            date(2026, 6, 1),
            date(2026, 6, 2),
            {"data_source": {
                "path": "test.xlsx",
                "date_column": "date",
                "value_column": "value",
            }},
        )
        assert len(result) == 2
        assert result["value"].sum() == 300


# ── 数据库适配器测试 ────────────────────────────────────────

class TestDatabaseSource:
    def _create_test_db(self, db_path: str):
        conn = sqlite3.connect(db_path)
        conn.execute(
            "CREATE TABLE metrics_daily "
            "(date TEXT, metric_id TEXT, channel TEXT, region TEXT, value REAL)"
        )
        rows = [
            ("2026-06-01", "test_m", "SEM", "华东", 100),
            ("2026-06-01", "test_m", "抖音", "华东", 50),
            ("2026-06-02", "test_m", "SEM", "华东", 120),
            ("2026-06-02", "test_m", "抖音", "华东", 60),
            ("2026-06-03", "test_m", "SEM", "华南", 80),
        ]
        conn.executemany(
            "INSERT INTO metrics_daily VALUES (?, ?, ?, ?, ?)", rows
        )
        conn.commit()
        conn.close()

    def _metric_config(self):
        return {
            "data_source": {
                "table": "metrics_daily",
                "date_column": "date",
                "value_column": "value",
                "metric_id_column": "metric_id",
            }
        }

    def test_connection(self, tmp_path):
        from src.data_source.database_source import DatabaseSource

        db_path = str(tmp_path / "test.db")
        self._create_test_db(db_path)
        source = DatabaseSource({"url": f"sqlite:///{db_path}"})
        assert source.test_connection() is True
        source.close()

    def test_connection_bad_url(self):
        from src.data_source.database_source import DatabaseSource

        source = DatabaseSource({"url": "sqlite:///nonexistent/bad/path.db"})
        assert source.test_connection() is False

    def test_query_metric(self, tmp_path):
        from src.data_source.database_source import DatabaseSource

        db_path = str(tmp_path / "test.db")
        self._create_test_db(db_path)
        source = DatabaseSource({"url": f"sqlite:///{db_path}"})

        df = source.query_metric(
            "test_m",
            date(2026, 6, 1),
            date(2026, 6, 3),
            self._metric_config(),
        )
        assert len(df) == 3
        assert df[df["date"] == date(2026, 6, 1)]["value"].iloc[0] == 150
        source.close()

    def test_query_by_dimension(self, tmp_path):
        from src.data_source.database_source import DatabaseSource

        db_path = str(tmp_path / "test.db")
        self._create_test_db(db_path)
        source = DatabaseSource({"url": f"sqlite:///{db_path}"})

        df = source.query_metric_by_dimension(
            "test_m",
            "channel",
            date(2026, 6, 1),
            date(2026, 6, 3),
            self._metric_config(),
        )
        assert "channel" in df.columns
        assert set(df["channel"].unique()) == {"SEM", "抖音"}
        source.close()


# ── API 适配器测试 ──────────────────────────────────────────

class TestAPISource:
    def test_init(self):
        from src.data_source.api_source import APISource

        source = APISource({
            "base_url": "https://api.example.com",
            "auth_type": "bearer",
            "auth_token": "test-token",
        })
        assert source.base_url == "https://api.example.com"

    def test_connection_unreachable(self):
        from src.data_source.api_source import APISource

        source = APISource({
            "base_url": "http://127.0.0.1:19999",
            "auth_type": "none",
            "timeout": 1,
        })
        assert source.test_connection() is False
