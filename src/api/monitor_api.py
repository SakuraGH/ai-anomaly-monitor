"""监控任务与异常查询 API。"""

from datetime import date

from fastapi import APIRouter, HTTPException, Query

from .deps import get_state

router = APIRouter(prefix="/api", tags=["监控任务"])


@router.post("/monitor/run")
def run_monitor_pipeline(target_date: str | None = None):
    state = get_state()
    dt = date.fromisoformat(target_date) if target_date else None
    result = state.orchestrator.run_pipeline(dt)
    return result.model_dump()


@router.post("/monitor/run/{metric_id}")
def run_single_metric(metric_id: str, target_date: str | None = None):
    state = get_state()
    dt = date.fromisoformat(target_date) if target_date else None
    result = state.orchestrator.run_single(metric_id, dt)
    return result.model_dump()


@router.get("/monitor/status")
def get_monitor_status():
    state = get_state()
    jobs = state.scheduler.jobs
    next_times = state.scheduler.next_fire_times
    last_results = state.orchestrator.store.list(limit=5)
    return {
        "scheduler_running": True,
        "jobs": jobs,
        "next_fire_times": {k: str(v) for k, v in next_times.items()},
        "last_results": [r.model_dump() for r in last_results],
    }


@router.get("/anomalies")
def list_anomalies(
    severity: str | None = Query(None),
    metric_id: str | None = Query(None),
    start_date: str | None = Query(None),
    end_date: str | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    state = get_state()
    all_results = state.orchestrator.store.list(limit=200)

    anomalies = []
    for r in all_results:
        for anomaly in r.anomalies:
            if severity and anomaly.severity.value != severity:
                continue
            if metric_id and anomaly.metric_id != metric_id:
                continue
            if start_date and str(anomaly.event_date) < start_date:
                continue
            if end_date and str(anomaly.event_date) > end_date:
                continue
            anomalies.append({
                **anomaly.model_dump(),
                "run_id": r.run_id,
            })

    total = len(anomalies)
    start = (page - 1) * page_size
    items = anomalies[start:start + page_size]

    return {"total": total, "page": page, "page_size": page_size, "items": items}


@router.get("/anomalies/{anomaly_id}")
def get_anomaly_detail(anomaly_id: str):
    """按 metric_id 查找最新异常（简化：anomaly_id 传 metric_id）。"""
    state = get_state()
    all_results = state.orchestrator.store.list(limit=100)
    for r in reversed(all_results):
        for anomaly in r.anomalies:
            if anomaly.metric_id == anomaly_id:
                attribution = r.attributions.get(anomaly_id)
                return {
                    "anomaly": anomaly.model_dump(),
                    "attribution": attribution.model_dump() if attribution else None,
                    "run_id": r.run_id,
                }
    raise HTTPException(404, f"未找到指标 '{anomaly_id}' 的异常记录")
