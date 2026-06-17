"""知识库 API。"""

from fastapi import APIRouter, Query

from .deps import get_state

router = APIRouter(prefix="/api/knowledge", tags=["知识库"])

_sample_cases = [
    {
        "case_id": "CASE-001",
        "date": "2026-03-15",
        "metric_name": "日注册量",
        "root_cause": "百度SEM投放预算到期",
        "action_taken": "补充预算",
        "recovery": "次日恢复",
        "tags": ["渠道", "百度SEM", "预算"],
    },
    {
        "case_id": "CASE-002",
        "date": "2026-04-02",
        "metric_name": "支付成功率",
        "root_cause": "微信支付接口升级兼容性问题",
        "action_taken": "发布热修复",
        "recovery": "48小时恢复",
        "tags": ["支付", "微信支付", "版本"],
    },
]


@router.get("")
def list_knowledge(page: int = 1, page_size: int = 20):
    total = len(_sample_cases)
    start = (page - 1) * page_size
    return {
        "total": total,
        "page": page,
        "items": _sample_cases[start:start + page_size],
    }


@router.get("/search")
def search_knowledge(q: str = Query(...), top_k: int = 3):
    # 简单的关键词匹配（ChromaDB 可用后用向量检索）
    results = []
    for case in _sample_cases:
        score = 0
        q_lower = q.lower()
        if any(t.lower() in q_lower for t in case["tags"]):
            score += 0.4
        if case["metric_name"] in q:
            score += 0.3
        if any(w in q for w in case["root_cause"]):
            score += 0.2
        if score > 0:
            results.append({**case, "similarity": min(score, 1.0)})

    results.sort(key=lambda x: -x["similarity"])
    results = results[:top_k]
    return {
        "query": q,
        "results": results,
        "disclaimer": "⚠️ 历史案例仅供参考，业务环境可能不同，不可直接套用结论。",
    }


@router.get("/stats")
def knowledge_stats():
    return {
        "total_cases": len(_sample_cases),
        "correct_count": 1,
        "wrong_count": 0,
        "partial_count": 0,
        "pending_count": 1,
        "accuracy": 1.0,
    }
