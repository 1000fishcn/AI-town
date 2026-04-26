"""没有 FAISS 时使用的 JSON 长期记忆兜底库。"""

from __future__ import annotations

import json
import re
import uuid
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable

from .long_memory import MemoryRecord, MemorySection, SECTION_NAMES


class JsonLongMemoryStore:
    """用 JSON 文件保存长期记忆，接口尽量贴近 LongMemoryStore。"""

    def __init__(self, storage_dir: str | Path = "aitown/memory/json_store") -> None:
        self.storage_dir = Path(storage_dir)
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        self.records_path = self.storage_dir / "records.json"
        self.records = self._load_records()

    def add_memory(
        self,
        *,
        owner_name: str,
        section: MemorySection,
        content: str,
        keywords: Iterable[str] | None = None,
        target_name: str | None = None,
        importance: int = 3,
        confidence: float = 0.7,
        source: str = "llm",
        metadata: dict[str, Any] | None = None,
    ) -> MemoryRecord:
        """新增一条长期记忆。"""

        now = datetime.now().isoformat(timespec="seconds")
        record = MemoryRecord(
            id=str(uuid.uuid4()),
            owner_name=owner_name,
            section=section,
            content=content.strip(),
            keywords=list(keywords or []),
            target_name=target_name,
            importance=max(1, min(5, int(importance))),
            confidence=max(0.0, min(1.0, float(confidence))),
            source=source,
            created_at=now,
            updated_at=now,
            metadata=metadata or {},
        )
        self.records.append(record)
        self._save()
        return record

    def update_memory(self, record_id: str, **changes: Any) -> MemoryRecord:
        """按 id 更新长期记忆。"""

        record = self.get(record_id)
        for key, value in changes.items():
            if value is not None and hasattr(record, key):
                setattr(record, key, value)
        record.updated_at = datetime.now().isoformat(timespec="seconds")
        self._save()
        return record

    def upsert_memory(
        self,
        *,
        owner_name: str,
        section: MemorySection,
        content: str,
        keywords: Iterable[str] | None = None,
        target_name: str | None = None,
        importance: int = 3,
        confidence: float = 0.7,
        source: str = "llm",
        metadata: dict[str, Any] | None = None,
        similar_threshold: float = 0.82,
    ) -> MemoryRecord:
        """查找相似记忆，存在就更新，不存在就新增。"""

        keyword_list = list(keywords or [])
        matches = self.search(
            owner_name=owner_name,
            query=" ".join([content, " ".join(keyword_list)]),
            section=section,
            target_name=target_name,
            top_k=1,
        )
        if matches and matches[0][1] >= similar_threshold:
            old_record = matches[0][0]
            merged_keywords = sorted(set(old_record.keywords) | set(keyword_list))
            return self.update_memory(
                old_record.id,
                content=content.strip(),
                keywords=merged_keywords,
                importance=max(old_record.importance, int(importance)),
                confidence=max(old_record.confidence, float(confidence)),
                source=source,
                metadata={**old_record.metadata, **(metadata or {})},
            )

        return self.add_memory(
            owner_name=owner_name,
            section=section,
            content=content,
            keywords=keyword_list,
            target_name=target_name,
            importance=importance,
            confidence=confidence,
            source=source,
            metadata=metadata,
        )

    def search(
        self,
        *,
        owner_name: str,
        query: str,
        section: MemorySection | None = None,
        target_name: str | None = None,
        top_k: int = 5,
    ) -> list[tuple[MemoryRecord, float]]:
        """按人名、二级结构和关键词检索长期记忆。"""

        query_tokens = set(_tokenize(query))
        results: list[tuple[MemoryRecord, float]] = []
        for record in self.records:
            if record.owner_name != owner_name:
                continue
            if section and record.section != section:
                continue
            if target_name and record.target_name != target_name:
                continue
            score = _score_record(record, query_tokens)
            if score > 0:
                results.append((record, score))

        results.sort(key=lambda item: item[1], reverse=True)
        return results[:top_k]

    def get(self, record_id: str) -> MemoryRecord:
        """按 id 获取一条长期记忆。"""

        for record in self.records:
            if record.id == record_id:
                return record
        raise KeyError(record_id)

    def structure(self, owner_name: str | None = None) -> dict[str, dict[str, list[dict[str, Any]]]]:
        """导出“人名 -> 二级结构 -> 记忆列表”的可读结构。"""

        result: dict[str, dict[str, list[dict[str, Any]]]] = {}
        for record in self.records:
            if owner_name and record.owner_name != owner_name:
                continue
            bucket = result.setdefault(record.owner_name, {key: [] for key in SECTION_NAMES})
            bucket[record.section].append(asdict(record))
        return result

    def _load_records(self) -> list[MemoryRecord]:
        if not self.records_path.exists():
            return []
        data = json.loads(self.records_path.read_text(encoding="utf-8"))
        return [MemoryRecord(**item) for item in data]

    def _save(self) -> None:
        self.records_path.write_text(
            json.dumps([asdict(record) for record in self.records], ensure_ascii=False, indent=2),
            encoding="utf-8",
        )


def _score_record(record: MemoryRecord, query_tokens: set[str]) -> float:
    """用关键词重合度算一个简单相关分。"""

    record_tokens = set(_tokenize(record.text_for_embedding()))
    if not query_tokens or not record_tokens:
        return 0.0
    overlap = len(query_tokens & record_tokens)
    if overlap == 0:
        return 0.0
    keyword_bonus = len(query_tokens & set(record.keywords)) * 0.15
    return min(1.0, overlap / max(len(query_tokens), 1) + keyword_bonus)


def _tokenize(text: str) -> list[str]:
    """切出中文单字和英文数字词。"""

    return re.findall(r"[A-Za-z0-9_]+|[\u4e00-\u9fff]", text.lower())
