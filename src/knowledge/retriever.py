"""相似案例检索：根据当前异常描述检索历史相似案例。"""

from dataclasses import dataclass, field

from src.models.anomaly_event import AnomalyEvent
from src.models.attribution_result import AttributionResult
from src.models.knowledge_record import KnowledgeRecord

from .store import KnowledgeStore

DISCLAIMER = "⚠️ 历史案例仅供参考，业务环境可能不同，不可直接套用结论。"


@dataclass
class SearchResult:
    """单条检索结果。"""
    record: KnowledgeRecord
    similarity: float

    @property
    def is_high_match(self) -> bool:
        return self.similarity > 0.75


@dataclass
class SearchResults:
    """检索结果集。"""
    query: str
    results: list[SearchResult] = field(default_factory=list)
    disclaimer: str = DISCLAIMER

    @property
    def top_record(self) -> KnowledgeRecord | None:
        if not self.results:
            return None
        return self.results[0].record

    def high_matches(self) -> list[SearchResult]:
        return [r for r in self.results if r.is_high_match]


class KnowledgeRetriever:
    """知识库检索器：根据异常描述语义检索历史相似案例。"""

    def __init__(self, store: KnowledgeStore, search_top_k: int = 3):
        self.store = store
        self.top_k = search_top_k

    def search(
        self,
        query: str,
        top_k: int | None = None,
    ) -> SearchResults:
        """根据异常描述文本检索相似案例。

        返回 SearchResults，包含相似度评分和免责声明。
        """
        k = top_k or self.top_k
        k = min(k, self.store.count())

        if k == 0:
            return SearchResults(query=query)

        raw = self.store._collection.query(
            query_texts=[query],
            n_results=k,
            include=["documents", "metadatas", "distances"],
        )

        results = []
        for i, case_id in enumerate(raw["ids"][0]):
            record = self.store._metadata_to_record(
                case_id,
                raw["metadatas"][0][i],
                raw["documents"][0][i] if raw["documents"] else "",
            )
            distance = raw["distances"][0][i]
            similarity = 1.0 - float(distance)
            results.append(SearchResult(record=record, similarity=similarity))

        return SearchResults(query=query, results=results)

    def search_from_anomaly(
        self,
        anomaly: AnomalyEvent,
        attribution: AttributionResult | None = None,
        top_k: int | None = None,
    ) -> SearchResults:
        """从异常事件构建查询，检索相似案例。"""
        parts = [
            f"指标:{anomaly.metric_name}",
            anomaly.message,
        ]
        if attribution:
            parts.append(attribution.summary)
            if attribution.top_contributor:
                parts.append(f"主要贡献: {attribution.top_contributor}")
            for level in attribution.drill_levels:
                for item in level.items:
                    if abs(item.contribution_pct) > 0.10:
                        parts.append(
                            f"{item.dimension}={item.dimension_value}"
                            f"贡献{item.contribution_pct:.0%}"
                        )

        query = " | ".join(filter(None, parts))
        return self.search(query, top_k)
