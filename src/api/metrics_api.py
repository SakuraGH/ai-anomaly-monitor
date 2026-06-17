"""指标管理 API。"""

from fastapi import APIRouter, HTTPException

from src.models.metric import MetricDefinition
from .deps import get_state

router = APIRouter(prefix="/api/metrics", tags=["指标管理"])


@router.get("")
def list_metrics():
    state = get_state()
    metrics = state.registry.list_metrics()
    return {"metrics": [m.model_dump() for m in metrics]}


@router.get("/{metric_id}")
def get_metric(metric_id: str):
    state = get_state()
    try:
        m = state.registry.get_metric(metric_id)
        return m.model_dump()
    except KeyError:
        raise HTTPException(404, f"指标 '{metric_id}' 不存在")


@router.post("")
def add_metric(data: dict):
    state = get_state()
    try:
        metric = MetricDefinition(**data)
        state.registry.add_metric(metric)
        return metric.model_dump()
    except ValueError as e:
        raise HTTPException(400, str(e))


@router.put("/{metric_id}")
def update_metric(metric_id: str, data: dict):
    state = get_state()
    try:
        updated = state.registry.update_metric(metric_id, data)
        return updated.model_dump()
    except KeyError:
        raise HTTPException(404, f"指标 '{metric_id}' 不存在")
