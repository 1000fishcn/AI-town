"""单个 Agent 的交互逻辑。

流程：
1. 接收用户输入。
2. 按用户输入检索相关长期记忆。
3. 拼接人格提示词、长期记忆、短期总结、最近未压缩对话和当前输入。
4. 调用 LLM 得到回复。
5. 把本轮对话写入短期记忆。
6. 短期记忆达到 x 轮后，调用 LLM 压缩，并把长期记忆候选写入 FAISS。
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Iterable, TypedDict

from aitown.llm import QwenAPIConfig, create_qwen_chat_llm, load_prompt, render_prompt
from aitown.memory import LongMemoryStore, LongMemoryUpdater, MemoryRecord, ShortMemoryBuffer


@dataclass(frozen=True)
class AgentPersona:
    """Agent 的自我画像。"""

    name: str
    identity: str = "AI 小镇居民"
    personality: str = "温和、自然、好奇"
    hobbies: str = "聊天、观察小镇、记录生活"
    speaking_style: str = "口语化，回复简短"
    relationship_to_user: str = "熟悉的朋友"
    background: str = "住在 AI 小镇，喜欢和用户自然交流"

    def describe(self) -> str:
        """压缩记忆时给 LLM 看的简短画像。"""

        return (
            f"{self.name}，{self.identity}。性格：{self.personality}。"
            f"爱好：{self.hobbies}。说话风格：{self.speaking_style}。"
            f"和用户的关系：{self.relationship_to_user}。背景：{self.background}。"
        )


class AgentState(TypedDict, total=False):
    """LangGraph 节点之间传递的状态。"""

    user_input: str
    response: str


class SingleAgent:
    """带长期记忆和短期记忆管理的单 Agent。"""

    def __init__(
        self,
        *,
        persona: AgentPersona,
        llm: Any,
        long_memory: LongMemoryStore,
        short_memory: ShortMemoryBuffer | None = None,
        memory_top_k: int = 6,
    ) -> None:
        self.persona = persona
        self.llm = llm
        self.long_memory = long_memory
        self.short_memory = short_memory or ShortMemoryBuffer(max_rounds=20)
        self.memory_updater = LongMemoryUpdater(long_memory)
        self.memory_top_k = memory_top_k

    def chat(self, user_input: str) -> str:
        """处理一轮用户输入，并返回模型回复。"""

        memories = self.search_long_memory(user_input)
        prompt = self.build_prompt(user_input=user_input, memories=memories)
        response = self.llm.invoke(prompt)
        answer = _message_content(response)

        should_compress = self.short_memory.add_turn(user_input, answer)
        if should_compress:
            self.try_compress_and_update_long_memory()

        return answer

    def try_compress_and_update_long_memory(self) -> bool:
        """尝试压缩短期记忆并更新长期记忆；失败时不影响本轮回复。"""

        try:
            self.compress_and_update_long_memory()
        except Exception:
            return False
        return True

    def build_graph(self) -> Any:
        """构建一个最小 LangGraph，节点里复用 chat 流程。"""

        from langgraph.graph import END, StateGraph

        graph = StateGraph(AgentState)
        graph.add_node("chat", self._chat_node)
        graph.set_entry_point("chat")
        graph.add_edge("chat", END)
        return graph.compile()

    def _chat_node(self, state: AgentState) -> AgentState:
        """LangGraph 节点：输入 user_input，输出 response。"""

        user_input = state["user_input"]
        return {"user_input": user_input, "response": self.chat(user_input)}

    def search_long_memory(self, user_input: str) -> list[tuple[MemoryRecord, float]]:
        """检索当前输入需要用到的长期记忆。"""

        return self.long_memory.search(
            owner_name=self.persona.name,
            query=user_input,
            top_k=self.memory_top_k,
        )

    def build_prompt(self, *, user_input: str, memories: Iterable[tuple[MemoryRecord, float]]) -> str:
        """拼接最终送入 LLM 的人格提示词。"""

        template = load_prompt("persona_chat_prompt.md")
        return render_prompt(
            template,
            {
                "name": self.persona.name,
                "identity": self.persona.identity,
                "personality": self.persona.personality,
                "hobbies": self.persona.hobbies,
                "speaking_style": self.persona.speaking_style,
                "relationship_to_user": self.persona.relationship_to_user,
                "background": self.persona.background,
                "long_memory": self.format_long_memory(memories),
                "short_memory_summary": self.short_memory.context_for_next_dialogue() or "无",
                "recent_dialogue": self.short_memory.format_dialogue() or "无",
                "current_time": datetime.now().isoformat(timespec="seconds"),
                "user_message": user_input,
            },
        )

    def compress_and_update_long_memory(self) -> None:
        """短期记忆满 x 轮后，压缩短期记忆并更新长期记忆。"""

        existing_memory = self.format_long_memory(
            self.long_memory.search(
                owner_name=self.persona.name,
                query=self.short_memory.format_dialogue(),
                top_k=self.memory_top_k,
            )
        )
        compression = self.short_memory.compress_with_llm(
            self.llm,
            persona=self.persona.describe(),
            existing_long_memory=existing_memory,
            clear_after=True,
        )
        self.memory_updater.update_from_compression(
            owner_name=self.persona.name,
            compression=compression,
        )

    def format_long_memory(self, memories: Iterable[tuple[MemoryRecord, float]]) -> str:
        """把检索到的长期记忆整理成提示词片段。"""

        lines: list[str] = []
        for index, (record, score) in enumerate(memories, start=1):
            target = f"，对象：{record.target_name}" if record.target_name else ""
            keywords = f"，关键词：{'、'.join(record.keywords)}" if record.keywords else ""
            lines.append(
                f"{index}. [{record.section}{target}] {record.content}"
                f"{keywords}，重要性：{record.importance}，相关度：{score:.3f}"
            )
        return "\n".join(lines) if lines else "无"


def create_qwen_llm() -> Any:
    """创建千问聊天模型，供 LangGraph 节点使用。"""

    config = QwenAPIConfig.from_env()
    try:
        from langchain_openai import ChatOpenAI
    except ImportError:
        return create_qwen_chat_llm(config)
    return ChatOpenAI(**config.langchain_kwargs())


def create_single_agent(
    *,
    persona: AgentPersona,
    llm: Any,
    long_memory: LongMemoryStore,
    short_memory_rounds: int = 20,
    memory_top_k: int = 6,
) -> SingleAgent:
    """创建一个带独立短期记忆的单 Agent。"""

    return SingleAgent(
        persona=persona,
        llm=llm,
        long_memory=long_memory,
        short_memory=ShortMemoryBuffer(max_rounds=short_memory_rounds),
        memory_top_k=memory_top_k,
    )


def _message_content(message: Any) -> str:
    """兼容 LangChain 消息对象和普通字符串。"""

    return str(getattr(message, "content", message)).strip()
