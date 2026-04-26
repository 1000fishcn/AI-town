"""单 Agent 命令行聊天入口。"""

from __future__ import annotations

from aitown.memory import LongMemoryStore, ShortMemoryBuffer

from .single_agent import AgentPersona, SingleAgent, create_qwen_llm


def main() -> int:
    """启动一个简单命令行对话。"""

    llm = create_qwen_llm()
    agent = SingleAgent(
        persona=AgentPersona(name="小艾"),
        llm=llm,
        long_memory=LongMemoryStore(),
        short_memory=ShortMemoryBuffer(max_rounds=10),
    )

    print("输入 /exit 结束对话。")
    while True:
        user_input = input("你：").strip()
        if user_input in {"/exit", "exit", "退出"}:
            break
        if not user_input:
            continue
        print(f"{agent.persona.name}：{agent.chat(user_input)}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
