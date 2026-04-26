"""给 Godot 调用的 FastAPI 后端。"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from threading import Lock
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from aitown.memory import JsonLongMemoryStore, LongMemoryStore
from aitown.simpleagent import AgentPersona, SingleAgent, create_qwen_llm


class AgentCreateRequest(BaseModel):
    """Godot 创建 NPC 时传入的画像。"""

    agent_id: str | None = Field(default=None, description="Godot 里的 NPC 唯一 ID")
    name: str = Field(description="NPC 名字")
    identity: str = ""
    personality: str = ""
    hobbies: str = ""
    speaking_style: str = ""
    relationship_to_user: str = ""
    background: str = ""
    short_memory_rounds: int = Field(default=10, ge=1, le=100)
    memory_top_k: int = Field(default=6, ge=1, le=20)


class AgentInfo(BaseModel):
    """返回给 Godot 的 NPC 信息。"""

    agent_id: str
    name: str
    identity: str
    personality: str
    hobbies: str
    speaking_style: str
    relationship_to_user: str
    background: str
    memory_backend: str


class ChatRequest(BaseModel):
    """Godot 发送的一轮对话。"""

    agent_id: str = Field(description="要交互的 NPC 唯一 ID")
    user_message: str = Field(description="玩家输入")


class ChatResponse(BaseModel):
    """返回给 Godot 的 NPC 回复。"""

    agent_id: str
    agent_name: str
    reply: str


@dataclass
class ManagedAgent:
    """运行中的 Agent 和它的并发锁。"""

    agent_id: str
    agent: SingleAgent
    memory_backend: str
    lock: Lock


class AgentRegistry:
    """保存当前后端进程里的所有 NPC。"""

    def __init__(self) -> None:
        self.llm: Any | None = None
        self.agents: dict[str, ManagedAgent] = {}
        self.lock = Lock()

    def get_llm(self) -> Any:
        """懒加载千问模型，避免服务启动时就发起模型相关初始化。"""

        with self.lock:
            if self.llm is None:
                self.llm = create_qwen_llm()
            return self.llm

    def create_agent(self, request: AgentCreateRequest) -> AgentInfo:
        """按 Godot 传来的画像创建或覆盖一个 NPC。"""

        agent_id = _normalize_agent_id(request.agent_id or request.name)
        persona = AgentPersona(
            name=request.name,
            identity=request.identity,
            personality=request.personality,
            hobbies=request.hobbies,
            speaking_style=request.speaking_style,
            relationship_to_user=request.relationship_to_user,
            background=request.background,
        )
        long_memory, memory_backend = _create_long_memory(agent_id)
        agent = SingleAgent(
            persona=persona,
            llm=self.get_llm(),
            long_memory=long_memory,
            memory_top_k=request.memory_top_k,
        )
        agent.short_memory.max_rounds = request.short_memory_rounds

        with self.lock:
            self.agents[agent_id] = ManagedAgent(
                agent_id=agent_id,
                agent=agent,
                memory_backend=memory_backend,
                lock=Lock(),
            )
        return _agent_info(self.agents[agent_id])

    def list_agents(self) -> list[AgentInfo]:
        """返回当前已注册的 NPC。"""

        with self.lock:
            return [_agent_info(item) for item in self.agents.values()]

    def chat(self, request: ChatRequest) -> ChatResponse:
        """调用指定 NPC 进行一轮对话。"""

        managed = self.get_agent(request.agent_id)
        message = request.user_message.strip()
        if not message:
            raise HTTPException(status_code=400, detail="user_message 不能为空")

        with managed.lock:
            reply = managed.agent.chat(message)

        return ChatResponse(
            agent_id=managed.agent_id,
            agent_name=managed.agent.persona.name,
            reply=reply,
        )

    def get_agent(self, agent_id: str) -> ManagedAgent:
        """按 agent_id 获取 NPC。"""

        normalized_id = _normalize_agent_id(agent_id)
        with self.lock:
            managed = self.agents.get(normalized_id)
        if managed is None:
            raise HTTPException(status_code=404, detail=f"没有找到 agent_id={agent_id} 的 NPC")
        return managed


registry = AgentRegistry()
app = FastAPI(title="AI Town Godot 后端", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health() -> dict[str, str]:
    """Godot 启动时检查后端是否在线。"""

    return {"status": "ok"}


@app.post("/agents", response_model=AgentInfo)
def create_agent(request: AgentCreateRequest) -> AgentInfo:
    """创建或覆盖一个 NPC。"""

    return registry.create_agent(request)


@app.get("/agents", response_model=list[AgentInfo])
def list_agents() -> list[AgentInfo]:
    """查看当前已经创建的 NPC。"""

    return registry.list_agents()


@app.post("/chat", response_model=ChatResponse)
def chat(request: ChatRequest) -> ChatResponse:
    """Godot 用这个接口发送玩家输入，并拿到 NPC 回复。"""

    return registry.chat(request)


def _create_long_memory(agent_id: str) -> tuple[LongMemoryStore | JsonLongMemoryStore, str]:
    """为每个 NPC 创建独立长期记忆目录。"""

    storage_dir = Path("aitown/memory/faiss_store/api") / agent_id
    try:
        return LongMemoryStore(storage_dir=storage_dir), "faiss_gpu"
    except RuntimeError:
        return JsonLongMemoryStore(storage_dir=Path("aitown/memory/json_store/api") / agent_id), "json"


def _agent_info(managed: ManagedAgent) -> AgentInfo:
    """把内部 Agent 转成 API 返回格式。"""

    persona = managed.agent.persona
    return AgentInfo(
        agent_id=managed.agent_id,
        name=persona.name,
        identity=persona.identity,
        personality=persona.personality,
        hobbies=persona.hobbies,
        speaking_style=persona.speaking_style,
        relationship_to_user=persona.relationship_to_user,
        background=persona.background,
        memory_backend=managed.memory_backend,
    )


def _normalize_agent_id(value: str) -> str:
    """把 Godot 传来的 ID 转成安全目录名。"""

    normalized = re.sub(r"[^\w\u4e00-\u9fff-]+", "_", value.strip()).strip("_")
    if not normalized:
        raise HTTPException(status_code=400, detail="agent_id 或 name 不能为空")
    return normalized
