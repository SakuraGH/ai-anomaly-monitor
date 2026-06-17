"""知识库 RAG 单元测试。"""

from datetime import date
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent

# ChromaDB 需要下载嵌入模型（79MB），首次运行较慢
# 模型代码已在 store.py / retriever.py / feedback.py 中实现
# 本测试覆盖：模型、Prompt、规则逻辑

CHROMADB_AVAILABLE = False
try:
    import chromadb  # noqa: F401
    # 检查嵌入模型是否已下载
    from pathlib import Path as _P
    model_path = _P.home() / ".cache" / "chroma" / "onnx_models" / "all-MiniLM-L6-v2"
    if list(model_path.glob("*.onnx")) if model_path.exists() else False:
        CHROMADB_AVAILABLE = True
except ImportError:
    pass


def _make_sample_record(case_id="CASE-001"):
    from src.models.knowledge_record import KnowledgeRecord
    return KnowledgeRecord(
        case_id=case_id,
        date=date(2026, 3, 15),
        metric_id="reg_daily",
        metric_name="日注册量",
        anomaly_description="日注册量下降22%，主要来自百度SEM渠道",
        anomaly_detail="百度SEM注册量下降65%，贡献整体下降的78%",
        root_cause="百度SEM投放预算到期，账户自动暂停",
        evidence_chain=[
            "百度SEM注册量下降65%，贡献整体下降的78%",
            "百度SEM曝光量下降72%",
            "点击率和转化率正常",
            "确认百度账户余额为0",
        ],
        action_taken="补充百度账户预算，恢复关键词投放",
        recovery="恢复预算后次日注册量回到正常水平",
        tags=["渠道", "百度SEM", "预算", "注册量"],
    )


# ── KnowledgeRecord 模型测试 ─────────────────────────────────

class TestKnowledgeRecord:
    def test_search_text(self):
        record = _make_sample_record()
        text = record.search_text
        assert "日注册量" in text
        assert "百度SEM" in text
        assert "预算" in text

    def test_feedback_default(self):
        from src.models.knowledge_record import FeedbackStatus
        record = _make_sample_record()
        assert record.feedback == FeedbackStatus.PENDING

    def test_knowledge_stats_accuracy(self):
        from src.models.knowledge_record import KnowledgeStats
        stats = KnowledgeStats(
            total_cases=10, correct_count=7,
            wrong_count=2, partial_count=1,
        )
        assert stats.accuracy == pytest.approx(0.7, abs=0.01)

    def test_knowledge_stats_zero(self):
        from src.models.knowledge_record import KnowledgeStats
        stats = KnowledgeStats()
        assert stats.accuracy == 0.0


# ── KnowledgeStore 测试（仅逻辑，不依赖 ChromaDB）─────────────

class TestKnowledgeStore:
    def test_model_initialization(self):
        from src.knowledge.store import KnowledgeStore
        # 使用 ephemeral=True 不写磁盘
        store = KnowledgeStore(ephemeral=True)
        assert store.count() == 0

    @pytest.mark.skipif(not CHROMADB_AVAILABLE,
                        reason="ChromaDB 嵌入模型未下载")
    def test_save_and_get_requires_model(self):
        from src.knowledge.store import KnowledgeStore
        store = KnowledgeStore(ephemeral=True)
        record = _make_sample_record("T-001")
        cid = store.save(record)
        assert cid == "T-001"
        retrieved = store.get(cid)
        assert retrieved is not None
        assert retrieved.metric_name == "日注册量"


# ── KnowledgeRetriever 测试 ──────────────────────────────────

class TestKnowledgeRetriever:
    def test_search_result_model(self):
        from src.knowledge.retriever import SearchResult, SearchResults
        record = _make_sample_record()
        sr = SearchResult(record=record, similarity=0.85)
        assert sr.is_high_match is True
        assert sr.similarity == 0.85

        sr2 = SearchResult(record=record, similarity=0.5)
        assert sr2.is_high_match is False

    def test_search_results_empty(self):
        from src.knowledge.retriever import SearchResults
        results = SearchResults(query="test")
        assert len(results.results) == 0
        assert results.top_record is None
        assert results.high_matches() == []

    def test_disclaimer(self):
        from src.knowledge.retriever import DISCLAIMER
        assert "仅供参考" in DISCLAIMER


# ── FeedbackManager 测试 ─────────────────────────────────────

class TestFeedbackManager:
    def test_model_creation(self):
        from src.knowledge.store import KnowledgeStore
        from src.knowledge.feedback import FeedbackManager

        store = KnowledgeStore(ephemeral=True)
        mgr = FeedbackManager(store)
        assert mgr is not None
        assert len(mgr.records_pending_review()) == 0


# ── FeedbackRecord / FeedbackStatus 模型测试 ─────────────────

class TestFeedbackModels:
    def test_feedback_record(self):
        from src.models.knowledge_record import FeedbackRecord, FeedbackStatus
        fb = FeedbackRecord(
            case_id="C1",
            status=FeedbackStatus.CORRECT,
            note="准确",
        )
        assert fb.status == FeedbackStatus.CORRECT
        assert fb.note == "准确"

    def test_feedback_status_values(self):
        from src.models.knowledge_record import FeedbackStatus
        assert FeedbackStatus.CORRECT.value == "correct"
        assert FeedbackStatus.WRONG.value == "wrong"
        assert FeedbackStatus.PARTIAL.value == "partial"
        assert FeedbackStatus.PENDING.value == "pending"
