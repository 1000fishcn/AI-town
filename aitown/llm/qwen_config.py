"""千问模型配置和提示词工具。"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence


QWEN_BASE_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1"
PROMPT_DIR = Path(__file__).with_name("prompts")


@dataclass(frozen=True)
class QwenAPIConfig:
    """LangGraph 里创建千问聊天模型时用的配置。"""

    api_key: str | None
    model: str = "qwen-plus"
    base_url: str = QWEN_BASE_URL
    temperature: float = 0.7
    max_tokens: int = 512

    @classmethod
    def from_env(cls, env_file: str | Path = ".env") -> "QwenAPIConfig":
        """从 .env 和环境变量读取配置。"""

        load_dotenv(env_file)
        return cls(
            api_key=os.getenv("DASHSCOPE_API_KEY") or os.getenv("LLM_API_KEY"),
            model=os.getenv("QWEN_MODEL") or os.getenv("LLM_MODEL_ID") or cls.model,
            base_url=os.getenv("QWEN_BASE_URL") or os.getenv("LLM_BASE_URL") or cls.base_url,
            temperature=float(os.getenv("QWEN_TEMPERATURE", cls.temperature)),
            max_tokens=int(os.getenv("QWEN_MAX_TOKENS", cls.max_tokens)),
        )

    def langchain_kwargs(self) -> dict[str, Any]:
        """传给 langchain_openai.ChatOpenAI 的参数。"""

        return {
            "model": self.model,
            "api_key": self.api_key,
            "base_url": self.base_url,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
        }

    def openai_client_kwargs(self) -> dict[str, str | None]:
        """传给 openai.OpenAI 的参数。"""

        return {
            "api_key": self.api_key,
            "base_url": self.base_url,
        }


@dataclass(frozen=True)
class QwenChatMessage:
    """统一成带 content 字段的消息对象。"""

    content: str


class QwenChatLLM:
    """用 openai SDK 调用千问聊天模型。"""

    def __init__(self, config: QwenAPIConfig | None = None) -> None:
        from openai import OpenAI

        self.config = config or QwenAPIConfig.from_env()
        self.client = OpenAI(**self.config.openai_client_kwargs())

    def invoke(self, prompt: str | Sequence[Mapping[str, str]]) -> QwenChatMessage:
        """兼容 LangChain 的 invoke 调用方式。"""

        messages = list(prompt) if not isinstance(prompt, str) else [{"role": "user", "content": prompt}]
        response = self.client.chat.completions.create(
            model=self.config.model,
            messages=messages,
            temperature=self.config.temperature,
            max_tokens=self.config.max_tokens,
        )
        return QwenChatMessage(content=response.choices[0].message.content or "")


def create_qwen_chat_llm(config: QwenAPIConfig | None = None) -> QwenChatLLM:
    """创建真实千问聊天模型。"""

    return QwenChatLLM(config=config)


def load_dotenv(env_file: str | Path = ".env") -> None:
    """读取简单的 .env 文件。"""

    path = Path(env_file)
    if not path.exists():
        return

    for line in path.read_text(encoding="utf-8").splitlines():
        if not line or line.lstrip().startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        os.environ.setdefault(key, value)


def load_prompt(filename: str) -> str:
    """读取 prompts 文件夹里的提示词。"""

    return (PROMPT_DIR / filename).read_text(encoding="utf-8")


def render_prompt(template: str, values: Mapping[str, Any]) -> str:
    """替换提示词里的 {变量名}。"""

    def replace(match: re.Match[str]) -> str:
        key = match.group(1)
        return str(values.get(key, "{" + key + "}"))

    return re.sub(r"\{([A-Za-z_][A-Za-z0-9_]*)\}", replace, template)


def build_qwen_messages(
    *,
    system_prompt: str,
    user_content: str,
    history: Sequence[Mapping[str, str]] | None = None,
) -> list[dict[str, str]]:
    """构造聊天模型使用的消息列表。"""

    messages = [{"role": "system", "content": system_prompt}]
    if history:
        messages.extend(dict(item) for item in history)
    messages.append({"role": "user", "content": user_content})
    return messages
