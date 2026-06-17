"""知识库存储：基于 ChromaDB 的向量存储，自动向量化异常描述用于检索。"""

import uuid
from datetime import datetime as dt
from pathlib import Path
from typing import Any

import chromadb
from chromadb.config import Settings

from src.models.knowledge_record import FeedbackStatus, KnowledgeRecord


class KnowledgeStore:
    """ChromaDB 向量知识库存储。

    每条异常案例在入库时自动向量化其 search_text，
    后续可通过语义相似度检索历史案例。
    """

    COLLECTION_NAME = "anomaly_cases"

    def __init__(self, db_path: str | Path = "data/knowledge_db",
                 ephemeral: bool = False):
        self.db_path = str(db_path)
        self._ephemeral = ephemeral

        if ephemeral:
            self._client = chromadb.Client(
                settings=Settings(anonymized_telemetry=False),
            )
        else:
            Path(self.db_path).mkdir(parents=True, exist_ok=True)
            self._client = chromadb.PersistentClient(
                path=self.db_path,
                settings=Settings(anonymized_telemetry=False),
            )
        self._collection = self._client.get_or_create_collection(
            name=self.COLLECTION_NAME,
            metadata={"hnsw:space": "cosine"},
        )

    def save(self, record: KnowledgeRecord) -> str:
        """存储一条知识库记录，自动向量化并写入 ChromaDB。

        返回 case_id。
        """
        if not record.case_id:
            record.case_id = uuid.uuid4().hex[:16]
        if record.created_at is None:
            record.created_at = dt.now()

        search_text = record.search_text
        metadata = self._record_to_metadata(record)

        self._collection.add(
            ids=[record.case_id],
            documents=[search_text],
            metadatas=[metadata],
        )
        return record.case_id

    def get(self, case_id: str) -> KnowledgeRecord | None:
        """根据 case_id 获取一条记录。"""
        result = self._collection.get(ids=[case_id])
        if not result["ids"]:
            return None
        return self._metadata_to_record(
            result["ids"][0],
            result["metadatas"][0],
            result["documents"][0],
        )

    def list_all(
        self, limit: int = 50, offset: int = 0
    ) -> list[KnowledgeRecord]:
        """列出所有记录。"""
        result = self._collection.get(
            limit=limit,
            offset=offset,
            include=["documents", "metadatas"],
        )
        records = []
        for i, case_id in enumerate(result["ids"]):
            records.append(
                self._metadata_to_record(
                    case_id,
                    result["metadatas"][i],
                    result["documents"][i] if result["documents"] else "",
                )
            )
        return records

    def update_feedback(
        self,
        case_id: str,
        status: FeedbackStatus,
        note: str = "",
    ) -> KnowledgeRecord | None:
        """更新一条记录的反馈状态。"""
        record = self.get(case_id)
        if record is None:
            return None

        record.feedback = status
        record.feedback_note = note

        self._collection.update(
            ids=[case_id],
            metadatas=[self._record_to_metadata(record)],
        )
        return record

    def delete(self, case_id: str) -> bool:
        try:
            self._collection.delete(ids=[case_id])
            return True
        except Exception:
            return False

    def count(self) -> int:
        return self._collection.count()

    def get_stats(self) -> dict[str, int]:
        """获取知识库统计。"""
        total = self.count()
        if total == 0:
            return {
                "total": 0, "correct": 0,
                "wrong": 0, "partial": 0, "pending": 0,
            }

        records = self.list_all(limit=total)
        stats = {"total": total, "correct": 0, "wrong": 0, "partial": 0, "pending": 0}
        for r in records:
            key = r.feedback.value
            if key in stats:
                stats[key] += 1
        return stats

    def seed_from_json(self, json_path: str | Path) -> list[str]:
        """从 JSON 文件导入种子数据。"""
        import json

        path = Path(json_path)
        with open(path, encoding="utf-8") as f:
            data = json.load(f)

        ids = []
        for item in data:
            record = KnowledgeRecord(
                case_id=item.get("case_id", ""),
                date=dt.strptime(item["date"], "%Y-%m-%d").date() if item.get("date") else None,
                metric_name=item.get("metric", ""),
                anomaly_description=item.get("anomaly_description", ""),
                root_cause=item.get("root_cause", ""),
                evidence_chain=item.get("evidence_chain", []),
                action_taken=item.get("action_taken", ""),
                recovery=item.get("recovery", ""),
                tags=item.get("tags", []),
            )
            ids.append(self.save(record))
        return ids

    def _record_to_metadata(self, record: KnowledgeRecord) -> dict[str, Any]:
        return {
            "date": record.date.isoformat() if record.date else "",
            "metric_id": record.metric_id,
            "metric_name": record.metric_name,
            "anomaly_description": record.anomaly_description[:500],
            "root_cause": record.root_cause[:500],
            "action_taken": record.action_taken[:500],
            "recovery": record.recovery[:500],
            "tags": ",".join(record.tags),
            "feedback": record.feedback.value,
            "source_run_id": record.source_run_id,
        }

    def _metadata_to_record(
        self, case_id: str, meta: dict[str, Any], document: str,
    ) -> KnowledgeRecord:
        return KnowledgeRecord(
            case_id=case_id,
            date=dt.strptime(meta["date"], "%Y-%m-%d").date() if meta.get("date") else None,
            metric_id=meta.get("metric_id", ""),
            metric_name=meta.get("metric_name", ""),
            anomaly_description=meta.get("anomaly_description", ""),
            anomaly_detail=document or "",
            root_cause=meta.get("root_cause", ""),
            action_taken=meta.get("action_taken", ""),
            recovery=meta.get("recovery", ""),
            tags=[t for t in meta.get("tags", "").split(",") if t],
            feedback=FeedbackStatus(meta.get("feedback", "pending")),
            source_run_id=meta.get("source_run_id", ""),
        )
