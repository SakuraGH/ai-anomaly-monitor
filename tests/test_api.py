"""后端 API 接口测试（使用 FastAPI TestClient）。"""

from datetime import date
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture(scope="module")
def client():
    from fastapi.testclient import TestClient
    from src.main import app
    from src.api.deps import get_state

    state = get_state()
    state.init_all()

    with TestClient(app) as c:
        yield c


# ── 基础端点 ────────────────────────────────────────────────

class TestRoot:
    def test_root(self, client):
        resp = client.get("/")
        assert resp.status_code == 200
        data = resp.json()
        assert "AI 异常监控" in data["message"]

    def test_health(self, client):
        resp = client.get("/health")
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"


# ── 数据源 API ──────────────────────────────────────────────

class TestDatasourceAPI:
    def test_list(self, client):
        resp = client.get("/api/datasource")
        assert resp.status_code == 200
        assert "datasources" in resp.json()

    def test_add(self, client):
        resp = client.post("/api/datasource", json={
            "id": "test-ds", "name": "测试", "type": "csv",
        })
        assert resp.status_code == 200
        assert resp.json()["id"] == "test-ds"

    def test_test_connection(self, client):
        resp = client.post("/api/datasource/csv-1/test")
        assert resp.status_code == 200

    def test_test_connection_404(self, client):
        resp = client.post("/api/datasource/nope/test")
        assert resp.status_code == 404

    def test_delete(self, client):
        client.post("/api/datasource", json={"id": "del-me", "type": "csv"})
        resp = client.delete("/api/datasource/del-me")
        assert resp.status_code == 200


# ── 指标 API ────────────────────────────────────────────────

class TestMetricsAPI:
    def test_list(self, client):
        resp = client.get("/api/metrics")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["metrics"]) >= 1

    def test_get(self, client):
        resp = client.get("/api/metrics/reg_daily")
        assert resp.status_code == 200
        assert resp.json()["metric_name"] == "日注册量"

    def test_get_404(self, client):
        resp = client.get("/api/metrics/nonexistent")
        assert resp.status_code == 404

    def test_update(self, client):
        resp = client.put("/api/metrics/reg_daily", json={"owner": "新负责人"})
        assert resp.status_code == 200
        assert resp.json()["owner"] == "新负责人"


# ── 监控任务 API ────────────────────────────────────────────

class TestMonitorAPI:
    TARGET = "2026-06-12"

    def test_run_single(self, client):
        resp = client.post(f"/api/monitor/run/reg_daily?target_date={self.TARGET}")
        assert resp.status_code == 200
        data = resp.json()
        assert "anomalies" in data

    def test_run_pipeline(self, client):
        resp = client.post(f"/api/monitor/run?target_date={self.TARGET}")
        assert resp.status_code == 200
        data = resp.json()
        assert "anomalies" in data
        assert "attributions" in data

    def test_status(self, client):
        resp = client.get("/api/monitor/status")
        assert resp.status_code == 200
        data = resp.json()
        assert "jobs" in data
        assert "last_results" in data

    def test_list_anomalies(self, client):
        client.post(f"/api/monitor/run?target_date={self.TARGET}")
        resp = client.get("/api/anomalies")
        assert resp.status_code == 200
        data = resp.json()
        assert "items" in data
        assert "total" in data

    def test_list_anomalies_filtered(self, client):
        client.post(f"/api/monitor/run?target_date={self.TARGET}")
        resp = client.get(
            "/api/anomalies?severity=high&metric_id=reg_daily&page=1&page_size=5"
        )
        assert resp.status_code == 200

    def test_anomaly_detail(self, client):
        client.post(f"/api/monitor/run?target_date={self.TARGET}")
        resp = client.get("/api/anomalies/reg_daily")
        assert resp.status_code == 200
        data = resp.json()
        assert "anomaly" in data

    def test_anomaly_detail_404(self, client):
        resp = client.get("/api/anomalies/nonexistent")
        assert resp.status_code == 404


# ── 报告 API ────────────────────────────────────────────────

class TestReportAPI:
    TARGET = "2026-06-12"

    def test_list_reports(self, client):
        client.post(f"/api/monitor/run?target_date={self.TARGET}")
        resp = client.get("/api/reports")
        assert resp.status_code == 200
        data = resp.json()
        assert "items" in data

    def test_get_report(self, client):
        client.post(f"/api/monitor/run?target_date={self.TARGET}")
        resp = client.get("/api/reports/reg_daily")
        assert resp.status_code == 200
        data = resp.json()
        assert "attribution" in data
        assert "anomaly" in data

    def test_get_report_404(self, client):
        resp = client.get("/api/reports/nonexistent")
        assert resp.status_code == 404

    def test_submit_feedback(self, client):
        resp = client.post("/api/reports/reg_daily/feedback", json={
            "status": "correct", "note": "归因准确",
        })
        assert resp.status_code == 200
        assert resp.json()["status"] == "correct"


# ── 知识库 API ──────────────────────────────────────────────

class TestKnowledgeAPI:
    def test_list(self, client):
        resp = client.get("/api/knowledge")
        assert resp.status_code == 200

    def test_search(self, client):
        resp = client.get("/api/knowledge/search?q=百度SEM 注册下降")
        assert resp.status_code == 200
        data = resp.json()
        assert "query" in data
        assert "results" in data
        assert "disclaimer" in data

    def test_stats(self, client):
        resp = client.get("/api/knowledge/stats")
        assert resp.status_code == 200
        data = resp.json()
        assert "total_cases" in data


# ── API 文档 ─────────────────────────────────────────────────

class TestDocs:
    def test_openapi_json(self, client):
        resp = client.get("/openapi.json")
        assert resp.status_code == 200
        data = resp.json()
        assert "AI 异常监控" in data["info"]["title"]
        paths = data["paths"]
        assert "/api/metrics" in paths
        assert "/api/monitor/run" in paths
        assert "/api/knowledge/search" in paths
