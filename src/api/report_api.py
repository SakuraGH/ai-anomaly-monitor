"""归因报告 API。"""

from fastapi import APIRouter, HTTPException

from src.models.knowledge_record import FeedbackStatus

from .deps import get_state

router = APIRouter(prefix="/api/reports", tags=["归因报告"])


@router.get("")
def list_reports(page: int = 1, page_size: int = 20):
    state = get_state()
    all_results = state.orchestrator.store.list(limit=200)

    reports = []
    for r in reversed(all_results):
        for mid, attr in r.attributions.items():
            anomaly = next(
                (a for a in r.anomalies if a.metric_id == mid), None,
            )
            reports.append({
                "run_id": r.run_id,
                "run_time": str(r.run_time) if r.run_time else None,
                "metric_id": mid,
                "anomaly": anomaly.model_dump() if anomaly else None,
                "summary": attr.summary if attr.summary else "",
            })

    total = len(reports)
    start = (page - 1) * page_size
    return {
        "total": total, "page": page,
        "items": reports[start:start + page_size],
    }


@router.get("/{metric_id}")
def get_report(metric_id: str):
    state = get_state()
    all_results = state.orchestrator.store.list(limit=100)
    for r in reversed(all_results):
        if metric_id in r.attributions:
            attr = r.attributions[metric_id]
            anomaly = next(
                (a for a in r.anomalies if a.metric_id == metric_id), None,
            )
            return {
                "run_id": r.run_id,
                "attribution": attr.model_dump(),
                "anomaly": anomaly.model_dump() if anomaly else None,
            }
    raise HTTPException(404, f"未找到指标 '{metric_id}' 的归因报告")


@router.post("/{metric_id}/feedback")
def submit_feedback(metric_id: str, data: dict):
    state = get_state()
    status_str = data.get("status", "pending")
    note = data.get("note", "")

    try:
        status = FeedbackStatus(status_str)
    except ValueError:
        raise HTTPException(400, f"无效的反馈状态: {status_str}")

    return {
        "metric_id": metric_id,
        "status": status.value,
        "note": note,
        "message": "反馈已记录",
    }
