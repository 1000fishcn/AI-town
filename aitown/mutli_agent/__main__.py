"""真实千问多 Agent 命令行交互入口。"""

from __future__ import annotations

import importlib.util
import re
from pathlib import Path
from typing import Callable

from aitown.memory import JsonLongMemoryStore, LongMemoryStore
from aitown.simpleagent import AgentPersona, SingleAgent, create_qwen_llm

from .builder import create_agents_from_descriptions


def main() -> int:
    """启动完整流程：输入描述、生成 Agent、选择 Agent 对话。"""

    print("真实千问多 Agent 流程")
    print("输入 /exit 结束，输入 /agents 查看列表，输入 /agent 序号 切换聊天对象。")

    llm = create_qwen_llm()
    count = _read_positive_int("请输入智能体数量：")
    descriptions = _read_descriptions(count)
    short_memory_rounds = _read_optional_int("短期记忆压缩轮数 x（默认 10）：", default=10)
    memory_factory = _build_long_memory_factory()

    print("正在调用千问生成智能体画像...")
    result = create_agents_from_descriptions(
        llm=llm,
        agent_count=count,
        descriptions=descriptions,
        long_memory_factory=memory_factory,
        short_memory_rounds=short_memory_rounds,
    )

    _print_personas(result.personas)
    _chat_loop(result.agents)
    return 0


def _read_positive_int(prompt: str) -> int:
    """读取正整数。"""

    while True:
        value = input(prompt).strip()
        if value.isdigit() and int(value) > 0:
            return int(value)
        print("请输入大于 0 的数字。")


def _read_optional_int(prompt: str, *, default: int) -> int:
    """读取可选正整数。"""

    value = input(prompt).strip()
    if not value:
        return default
    if value.isdigit() and int(value) > 0:
        return int(value)
    print(f"输入无效，使用默认值 {default}。")
    return default


def _read_descriptions(count: int) -> list[str]:
    """读取每个智能体的描述。"""

    descriptions: list[str] = []
    for index in range(count):
        descriptions.append(input(f"请输入第 {index + 1} 个智能体描述：").strip())
    return descriptions


def _build_long_memory_factory() -> Callable[[AgentPersona], LongMemoryStore | JsonLongMemoryStore]:
    """创建长期记忆工厂；没有 faiss-gpu 时自动使用 JSON 兜底。"""

    use_faiss_gpu = _can_use_faiss_gpu()
    if not use_faiss_gpu:
        print("未检测到 faiss-gpu，本次先使用 JSON 长期记忆兜底。")

    def factory(persona: AgentPersona) -> LongMemoryStore | JsonLongMemoryStore:
        safe_name = _safe_name(persona.name)
        if use_faiss_gpu:
            try:
                return LongMemoryStore(storage_dir=Path("aitown/memory/faiss_store") / safe_name)
            except RuntimeError:
                pass
        return JsonLongMemoryStore(storage_dir=Path("aitown/memory/json_store") / safe_name)

    return factory


def _can_use_faiss_gpu() -> bool:
    """判断当前环境是否能使用 GPU 版 FAISS。"""

    if importlib.util.find_spec("faiss") is None:
        return False
    try:
        import faiss
    except ImportError:
        return False
    return hasattr(faiss, "StandardGpuResources") and hasattr(faiss, "index_cpu_to_gpu")


def _safe_name(name: str) -> str:
    """把角色名转成安全目录名。"""

    return re.sub(r"[^\w\u4e00-\u9fff-]+", "_", name).strip("_") or "agent"


def _print_personas(personas: list[AgentPersona]) -> None:
    """打印千问生成的智能体画像。"""

    print("\n已创建智能体：")
    for index, persona in enumerate(personas, start=1):
        print(f"{index}. {persona.name}")
        print(f"   身份：{persona.identity or '未填写'}")
        print(f"   性格：{persona.personality or '未填写'}")
        print(f"   爱好：{persona.hobbies or '未填写'}")
        print(f"   说话风格：{persona.speaking_style or '未填写'}")
        print(f"   和用户的关系：{persona.relationship_to_user or '未填写'}")
        print(f"   背景：{persona.background or '未填写'}")


def _chat_loop(agents: list[SingleAgent]) -> None:
    """进入多 Agent 对话循环。"""

    current_index = 0
    while True:
        current_agent = agents[current_index]
        user_input = input(f"\n你 -> {current_agent.persona.name}：").strip()
        if user_input in {"/exit", "exit", "退出"}:
            break
        if user_input == "/agents":
            _print_agent_list(agents, current_index)
            continue
        if user_input.startswith("/agent"):
            current_index = _switch_agent(user_input, agents, current_index)
            continue
        if not user_input:
            continue

        print("千问生成中...")
        answer = current_agent.chat(user_input)
        print(f"{current_agent.persona.name}：{answer}")


def _print_agent_list(agents: list[SingleAgent], current_index: int) -> None:
    """打印当前可聊天的 Agent 列表。"""

    for index, agent in enumerate(agents, start=1):
        marker = "当前" if index - 1 == current_index else "可选"
        print(f"{index}. {agent.persona.name}（{marker}）")


def _switch_agent(command: str, agents: list[SingleAgent], current_index: int) -> int:
    """根据 /agent 序号 切换当前 Agent。"""

    parts = command.split()
    if len(parts) != 2 or not parts[1].isdigit():
        _print_agent_list(agents, current_index)
        return current_index

    next_index = int(parts[1]) - 1
    if 0 <= next_index < len(agents):
        print(f"已切换到 {agents[next_index].persona.name}。")
        return next_index

    print("没有这个序号。")
    return current_index


if __name__ == "__main__":
    raise SystemExit(main())
