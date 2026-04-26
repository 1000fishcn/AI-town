"""长期记忆更新程序。"""

from __future__ import annotations

import json
from typing import Any, Mapping

from aitown.llm import load_prompt, render_prompt

from .long_memory import LongMemoryStore, MemoryRecord, MemorySection
from .short_memory import CompressionResult, parse_compression_result


SECTION_ALIASES: dict[str, MemorySection] = {
    "self_profile": "self_profile",
    "profile": "self_profile",
    "职业": "self_profile",
    "性格": "self_profile",
    "爱好": "self_profile",
    "npc_profile": "npc_profile",
    "relationship": "npc_profile",
    "other_npc": "npc_profile",
    "关系": "npc_profile",
    "其它npc": "npc_profile",
    "其他npc": "npc_profile",
    "user_profile": "user_profile",
    "user": "user_profile",
    "用户": "user_profile",
}


class ShortMemoryUpdater:
    """负责把历史短期总结和最新 x 轮对话送给 LLM 压缩。"""

    def build_prompt(
        self,
        *,
        persona: str,
        existing_long_memory: str,
        short_memory_summary: str,
        dialogue_rounds: str,
        round_count: int,
    ) -> str:
        """拼接短期记忆压缩提示词。"""

        template = load_prompt("dialogue_memory_summary_prompt.md")
        return render_prompt(
            template,
            {
                "persona": persona,
                "existing_long_memory": existing_long_memory or "无",
                "short_memory_summary": short_memory_summary or "无",
                "dialogue_rounds": dialogue_rounds or "无",
                "round_count": round_count,
            },
        )

    def compress_with_llm(
        self,
        llm: Any,
        *,
        persona: str,
        existing_long_memory: str,
        short_memory_summary: str,
        dialogue_rounds: str,
        round_count: int,
    ) -> CompressionResult:
        """调用 LLM 压缩短期记忆，并解析返回 JSON。"""

        prompt = self.build_prompt(
            persona=persona,
            existing_long_memory=existing_long_memory,
            short_memory_summary=short_memory_summary,
            dialogue_rounds=dialogue_rounds,
            round_count=round_count,
        )
        response = llm.invoke(prompt)
        text = getattr(response, "content", response)
        return parse_compression_result(str(text))


class LongMemoryUpdater:
    """把 LLM 返回的长期记忆 JSON 写入 FAISS 长期记忆库。"""

    def __init__(self, store: LongMemoryStore) -> None:
        self.store = store

    def update_from_compression(
        self,
        *,
        owner_name: str,
        compression: CompressionResult,
    ) -> list[MemoryRecord]:
        """从短期记忆压缩结果更新长期记忆。"""

        return self.update_from_llm_json(owner_name=owner_name, data=compression.raw)

    def update_from_llm_json(
        self,
        *,
        owner_name: str,
        data: str | Mapping[str, Any],
    ) -> list[MemoryRecord]:
        """接受 LLM 返回的 JSON，并按“人名 -> 二级结构”查找更新。"""

        payload = json.loads(data) if isinstance(data, str) else dict(data)
        items = payload.get("long_term_memories", [])
        updated: list[MemoryRecord] = []
        for item in items:
            record = self._update_one(owner_name=owner_name, item=dict(item))
            if record:
                updated.append(record)
        return updated

    def _update_one(self, *, owner_name: str, item: dict[str, Any]) -> MemoryRecord | None:
        content = str(item.get("content", "")).strip()
        if not content:
            return None

        section = normalize_section(str(item.get("section") or item.get("category") or "other"))
        target_name = item.get("target_name")
        if section == "user_profile" and not target_name:
            target_name = "用户"

        return self.store.upsert_memory(
            owner_name=str(item.get("owner_name") or owner_name),
            section=section,
            target_name=str(target_name) if target_name else None,
            content=content,
            keywords=item.get("keywords", []),
            importance=item.get("importance", 3),
            confidence=item.get("confidence", 0.7),
            source="llm",
            metadata={
                "evidence": item.get("evidence", ""),
                "raw": item,
            },
        )


def normalize_section(value: str) -> MemorySection:
    """把 LLM 返回的类别归一化为长期记忆二级结构。"""

    key = value.strip().lower()
    return SECTION_ALIASES.get(key, "npc_profile")
