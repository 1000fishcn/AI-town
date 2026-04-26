"""长期记忆库。

长期记忆采用两级检索结构：
- 第一级：人名，也就是记忆属于哪个 NPC 或角色。
- 第二级：记忆类型，包括自我画像、其它 NPC 画像、用户画像。

向量检索默认使用 GPU 版 FAISS。索引保存到磁盘时会转成 CPU 索引格式，
这样下次启动可以重新构建或加载，不依赖 GPU 索引对象本身可序列化。
"""

from __future__ import annotations

import hashlib
import json
import math
import re
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Iterable, Literal, Sequence


MemorySection = Literal["self_profile", "npc_profile", "user_profile"]


SECTION_NAMES: dict[MemorySection, str] = {
    "self_profile": "职业、性格、爱好等自我画像",
    "npc_profile": "与其它人的关系、对其他人的看法、记忆等其它 NPC 画像",
    "user_profile": "对用户的看法、记忆等用户画像",
}


@dataclass
class MemoryRecord:
    """一条长期记忆。"""

    id: str
    owner_name: str
    section: MemorySection
    content: str
    keywords: list[str] = field(default_factory=list)
    target_name: str | None = None
    importance: int = 3
    confidence: float = 0.7
    source: str = "llm"
    created_at: str = field(default_factory=lambda: datetime.now().isoformat(timespec="seconds"))
    updated_at: str = field(default_factory=lambda: datetime.now().isoformat(timespec="seconds"))
    metadata: dict[str, Any] = field(default_factory=dict)

    def text_for_embedding(self) -> str:
        """把记忆拼成适合向量化的文本。"""

        return "\n".join(
            [
                f"所属人：{self.owner_name}",
                f"类别：{SECTION_NAMES[self.section]}",
                f"对象：{self.target_name or '无'}",
                f"内容：{self.content}",
                f"关键词：{'，'.join(self.keywords)}",
            ]
        )


class HashEmbedding:
    """本地哈希向量，先保证 FAISS 结构能跑起来。"""

    def __init__(self, dim: int = 384) -> None:
        self.dim = dim

    def encode(self, text: str) -> list[float]:
        """把文本转成固定维度向量。"""

        vector = [0.0] * self.dim
        for token in _tokenize(text):
            digest = hashlib.md5(token.encode("utf-8")).digest()
            index = int.from_bytes(digest[:4], "little") % self.dim
            sign = 1.0 if digest[4] % 2 == 0 else -1.0
            vector[index] += sign

        norm = math.sqrt(sum(value * value for value in vector))
        if norm > 0:
            vector = [value / norm for value in vector]
        return vector


class LongMemoryStore:
    """长期记忆 GPU FAISS 数据库。"""

    def __init__(
        self,
        storage_dir: str | Path = "aitown/memory/faiss_store",
        *,
        embedding_dim: int = 384,
        embedding_fn: Callable[[str], Sequence[float]] | None = None,
        use_gpu: bool = True,
        gpu_id: int = 0,
    ) -> None:
        self.storage_dir = Path(storage_dir)
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        self.records_path = self.storage_dir / "records.json"
        self.index_path = self.storage_dir / "memory.index"
        self.embedding_dim = embedding_dim
        self.embedding = embedding_fn or HashEmbedding(embedding_dim).encode
        self.use_gpu = use_gpu
        self.gpu_id = gpu_id
        self.records = self._load_records()
        self.index = self._build_index()

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
        """查找同结构相似记忆，能合并就更新，否则新增。"""

        keyword_list = list(keywords or [])
        query = " ".join([content, " ".join(keyword_list)])
        matches = self.search(
            owner_name=owner_name,
            query=query,
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
        """按人名、二级结构和查询文本检索长期记忆。"""

        if not self.records:
            return []

        vector = self._embed(query).reshape(1, -1)
        search_k = min(len(self.records), max(top_k * 8, top_k))
        scores, indexes = self.index.search(vector, search_k)
        results: list[tuple[MemoryRecord, float]] = []

        for score, index in zip(scores[0], indexes[0]):
            if index < 0:
                continue
            record = self.records[int(index)]
            if record.owner_name != owner_name:
                continue
            if section and record.section != section:
                continue
            if target_name and record.target_name != target_name:
                continue
            results.append((record, float(score)))
            if len(results) >= top_k:
                break

        return results

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
        self.index = self._build_index()
        faiss = _load_faiss()
        faiss.write_index(_index_to_cpu(faiss, self.index), str(self.index_path))

    def _build_index(self) -> Any:
        faiss = _load_faiss()
        np = _load_numpy()
        cpu_index = faiss.IndexFlatIP(self.embedding_dim)
        if self.records:
            vectors = np.ascontiguousarray(
                np.vstack([self._embed(record.text_for_embedding()) for record in self.records]),
                dtype=np.float32,
            )
            cpu_index.add(vectors)
        if not self.use_gpu:
            return cpu_index
        return _index_to_gpu(faiss, cpu_index, self.gpu_id)

    def _embed(self, text: str) -> Any:
        np = _load_numpy()
        vector = np.asarray(self.embedding(text), dtype=np.float32)
        if vector.shape != (self.embedding_dim,):
            raise ValueError(f"embedding 维度必须是 {self.embedding_dim}")
        norm = np.linalg.norm(vector)
        return vector / norm if norm > 0 else vector


def _load_faiss() -> Any:
    try:
        import faiss
    except ImportError as exc:
        raise RuntimeError("请先安装 faiss-gpu，长期记忆库需要 GPU 版 FAISS。") from exc
    return faiss


def _load_numpy() -> Any:
    try:
        import numpy as np
    except ImportError as exc:
        raise RuntimeError("请先安装可用的 numpy，FAISS 向量检索需要它。") from exc
    if not hasattr(np, "asarray") or not hasattr(np, "vstack"):
        raise RuntimeError("当前 numpy 不完整，请重新安装 numpy。")
    return np


def _index_to_gpu(faiss: Any, cpu_index: Any, gpu_id: int) -> Any:
    """把 CPU 索引转到指定 GPU。"""

    if not hasattr(faiss, "StandardGpuResources") or not hasattr(faiss, "index_cpu_to_gpu"):
        raise RuntimeError("当前 FAISS 不是 GPU 版本，请安装 faiss-gpu。")
    if hasattr(faiss, "get_num_gpus") and faiss.get_num_gpus() <= gpu_id:
        raise RuntimeError(f"没有可用的 GPU {gpu_id}，请检查 FAISS GPU 环境。")
    resources = faiss.StandardGpuResources()
    return faiss.index_cpu_to_gpu(resources, gpu_id, cpu_index)


def _index_to_cpu(faiss: Any, index: Any) -> Any:
    """保存到磁盘前转回 CPU 索引。"""

    if hasattr(faiss, "index_gpu_to_cpu"):
        try:
            return faiss.index_gpu_to_cpu(index)
        except Exception:
            return index
    return index


def _tokenize(text: str) -> list[str]:
    words = re.findall(r"[A-Za-z0-9_]+|[\u4e00-\u9fff]", text.lower())
    return words or [text]
