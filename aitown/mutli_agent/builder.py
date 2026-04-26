"""根据用户描述批量创建多个 Agent。"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any, Callable, Iterable, Mapping, Sequence

from aitown.llm import load_prompt, render_prompt
from aitown.memory import LongMemoryStore, ShortMemoryBuffer
from aitown.simpleagent import AgentPersona, SingleAgent, create_single_agent


PERSONA_FIELDS = (
    "name",
    "identity",
    "personality",
    "hobbies",
    "speaking_style",
    "relationship_to_user",
    "background",
)


@dataclass
class AgentBuildResult:
    """批量创建 Agent 的结果。"""

    personas: list[AgentPersona]
    agents: list[SingleAgent]
    raw_persona_json: dict[str, Any]


class MultiAgentBuilder:
    """把用户描述交给 LLM 抽取画像，再创建多个 SingleAgent。"""

    def __init__(
        self,
        *,
        llm: Any,
        long_memory_factory: Callable[[AgentPersona], LongMemoryStore],
        short_memory_rounds: int = 20,
        memory_top_k: int = 6,
    ) -> None:
        self.llm = llm
        self.long_memory_factory = long_memory_factory
        self.short_memory_rounds = short_memory_rounds
        self.memory_top_k = memory_top_k

    def build(
        self,
        *,
        agent_count: int,
        descriptions: Sequence[str] | Mapping[str, str],
    ) -> AgentBuildResult:
        """生成多个 Agent。"""

        prompt = build_persona_generation_prompt(
            agent_count=agent_count,
            descriptions=descriptions,
        )
        response = self.llm.invoke(prompt)
        raw_text = str(getattr(response, "content", response))
        raw_json = parse_persona_json(raw_text)
        personas = personas_from_json(raw_json, agent_count=agent_count)
        agents = [
            create_single_agent(
                persona=persona,
                llm=self.llm,
                long_memory=self.long_memory_factory(persona),
                short_memory_rounds=self.short_memory_rounds,
                memory_top_k=self.memory_top_k,
            )
            for persona in personas
        ]
        return AgentBuildResult(personas=personas, agents=agents, raw_persona_json=raw_json)


def create_agents_from_descriptions(
    *,
    llm: Any,
    agent_count: int,
    descriptions: Sequence[str] | Mapping[str, str],
    long_memory_factory: Callable[[AgentPersona], LongMemoryStore] | None = None,
    short_memory_rounds: int = 20,
    memory_top_k: int = 6,
) -> AgentBuildResult:
    """便捷函数：从用户描述直接创建多个 Agent。"""

    factory = long_memory_factory or _default_long_memory_factory
    return MultiAgentBuilder(
        llm=llm,
        long_memory_factory=factory,
        short_memory_rounds=short_memory_rounds,
        memory_top_k=memory_top_k,
    ).build(agent_count=agent_count, descriptions=descriptions)


def build_persona_generation_prompt(
    *,
    agent_count: int,
    descriptions: Sequence[str] | Mapping[str, str],
) -> str:
    """拼接交给 LLM 的多 Agent 画像抽取提示词。"""

    template = load_prompt("multi_agent_persona_prompt.md")
    return render_prompt(
        template,
        {
            "agent_count": agent_count,
            "agent_descriptions": format_agent_descriptions(descriptions),
        },
    )


def format_agent_descriptions(descriptions: Sequence[str] | Mapping[str, str]) -> str:
    """把用户输入的多个智能体描述格式化成提示词文本。"""

    if isinstance(descriptions, Mapping):
        items = [f"{index}. {name}：{description}" for index, (name, description) in enumerate(descriptions.items(), start=1)]
    else:
        items = [f"{index}. {description}" for index, description in enumerate(descriptions, start=1)]
    return "\n".join(items)


def parse_persona_json(text: str) -> dict[str, Any]:
    """解析 LLM 返回的画像 JSON。"""

    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?", "", cleaned).strip()
        cleaned = re.sub(r"```$", "", cleaned).strip()
    return json.loads(cleaned)


def personas_from_json(data: Mapping[str, Any], *, agent_count: int) -> list[AgentPersona]:
    """把画像 JSON 转成 AgentPersona 列表。"""

    raw_agents = list(data.get("agents", []))
    personas: list[AgentPersona] = []
    for index in range(agent_count):
        raw_persona = dict(raw_agents[index]) if index < len(raw_agents) and isinstance(raw_agents[index], Mapping) else {}
        normalized = {field: str(raw_persona.get(field) or "") for field in PERSONA_FIELDS}
        name = normalized["name"] or f"agent_{index + 1}"
        personas.append(
            AgentPersona(
                name=name,
                identity=normalized["identity"],
                personality=normalized["personality"],
                hobbies=normalized["hobbies"],
                speaking_style=normalized["speaking_style"],
                relationship_to_user=normalized["relationship_to_user"],
                background=normalized["background"],
            )
        )
    return personas


def _default_long_memory_factory(persona: AgentPersona) -> LongMemoryStore:
    """默认每个 Agent 一个独立长期记忆目录，避免互相检索到。"""

    safe_name = re.sub(r"[^\w\u4e00-\u9fff-]+", "_", persona.name).strip("_") or "agent"
    return LongMemoryStore(storage_dir=f"aitown/memory/faiss_store/{safe_name}")
