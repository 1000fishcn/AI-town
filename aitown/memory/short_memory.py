"""短期记忆。

一轮对话 = 用户输入 + 模型输出。
达到 max_rounds 后，把短期对话交给 LLM 压缩。
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Mapping, Sequence

@dataclass
class ConversationTurn:
    """一轮短期对话。"""

    user_input: str
    model_output: str
    created_at: str = field(default_factory=lambda: datetime.now().isoformat(timespec="seconds"))

    def format(self, index: int) -> str:
        """格式化给 LLM 压缩用。"""

        return f"第 {index} 轮\n用户：{self.user_input}\n模型：{self.model_output}"


@dataclass
class CompressionResult:
    """LLM 对短期记忆的压缩结果。"""

    context_summary: str
    details: list[dict[str, Any]]
    summary: str
    keywords: list[str]
    long_term_memories: list[dict[str, Any]]
    raw: dict[str, Any]


class ShortMemoryBuffer:
    """保存最近 x 轮对话，并在满轮后生成压缩任务。"""

    def __init__(self, max_rounds: int = 10) -> None:
        self.max_rounds = max_rounds
        self.turns: list[ConversationTurn] = []
        self.last_context_summary = ""

    def add_turn(self, user_input: str, model_output: str) -> bool:
        """加入一轮对话；返回是否已经达到压缩轮数。"""

        self.turns.append(ConversationTurn(user_input=user_input, model_output=model_output))
        return self.is_full()

    def is_full(self) -> bool:
        """是否达到压缩轮数。"""

        return len(self.turns) >= self.max_rounds

    def clear(self) -> None:
        """清空短期记忆。"""

        self.turns.clear()

    def format_dialogue(self) -> str:
        """把短期对话格式化为文本。"""

        return "\n\n".join(turn.format(index) for index, turn in enumerate(self.turns, start=1))

    def build_compression_prompt(
        self,
        *,
        persona: str,
        existing_long_memory: str = "",
    ) -> str:
        """构造压缩短期记忆的提示词。"""

        from aitown.llm import load_prompt, render_prompt

        template = load_prompt("dialogue_memory_summary_prompt.md")
        return render_prompt(
            template,
            {
                "persona": persona,
                "existing_long_memory": existing_long_memory,
                "short_memory_summary": self.last_context_summary or "无",
                "round_count": self.max_rounds,
                "dialogue_rounds": self.format_dialogue(),
            },
        )

    def compress_with_llm(
        self,
        llm: Any,
        *,
        persona: str,
        existing_long_memory: str = "",
        clear_after: bool = True,
    ) -> CompressionResult:
        """调用 LangChain/LangGraph 里的聊天模型压缩短期记忆。"""

        from .update import ShortMemoryUpdater

        result = ShortMemoryUpdater().compress_with_llm(
            llm,
            persona=persona,
            existing_long_memory=existing_long_memory,
            short_memory_summary=self.last_context_summary,
            dialogue_rounds=self.format_dialogue(),
            round_count=self.max_rounds,
        )
        self.last_context_summary = result.context_summary
        if clear_after:
            self.clear()
        return result

    def context_for_next_dialogue(self) -> str:
        """返回可塞进下一轮对话提示词的压缩上下文。"""

        return self.last_context_summary


def parse_compression_result(text: str) -> CompressionResult:
    """解析 LLM 返回的压缩 JSON。"""

    data = _loads_json(text)
    summary = str(data.get("summary", ""))
    context_summary = str(data.get("context_summary") or summary)
    return CompressionResult(
        context_summary=context_summary,
        details=list(data.get("details", [])),
        summary=summary,
        keywords=list(data.get("keywords", [])),
        long_term_memories=list(data.get("long_term_memories", [])),
        raw=data,
    )


def _loads_json(text: str) -> dict[str, Any]:
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?", "", text).strip()
        text = re.sub(r"```$", "", text).strip()
    return json.loads(text)
