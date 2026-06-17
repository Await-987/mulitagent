"""
AgentManager — 管理多个 HermesAgent，提供扫描、批量启停、统一观察流。
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import AsyncIterator

from .agent import Event, HermesAgent
from ..runtime import DEFAULT_CONFIG, HermesRuntimeConfig

logger = logging.getLogger(__name__)


@dataclass
class AgentInfo:
    company: str
    role: str
    employee_id: str
    home: Path

    @property
    def label(self) -> str:
        return f"{self.company}/{self.role}/{self.employee_id}"

    @property
    def namespace(self) -> str:
        return self.company

    @property
    def profile(self) -> str:
        return self.role

    @property
    def instance_id(self) -> str:
        return self.employee_id


class AgentManager:
    """多 agent 编排器。"""

    def __init__(
        self,
        base_dir: Path | None = None,
        *,
        config: HermesRuntimeConfig | None = None,
        namespace: str = "default",
    ):
        self.config = config or DEFAULT_CONFIG
        self.namespace = namespace
        self.base_dir = Path(base_dir) if base_dir else self.config.companies_dir
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self._agents: dict[str, HermesAgent] = {}  # label -> agent

    # ---- 发现 / 创建 --------------------------------------------------
    def list_on_disk(self) -> list[AgentInfo]:
        """扫磁盘上已存在的数字员工目录。"""
        infos: list[AgentInfo] = []
        if not self.base_dir.exists():
            return infos
        if self.config.company_scoped_layout:
            company = self.namespace
            for role_dir in sorted(self.base_dir.iterdir()):
                if not role_dir.is_dir():
                    continue
                for emp_dir in sorted(role_dir.iterdir()):
                    if not emp_dir.is_dir():
                        continue
                    if not (emp_dir / "SOUL.md").exists():
                        continue
                    infos.append(AgentInfo(
                        company=company,
                        role=role_dir.name,
                        employee_id=emp_dir.name,
                        home=emp_dir.resolve(),
                    ))
            return infos
        for company_dir in sorted(self.base_dir.iterdir()):
            if not company_dir.is_dir():
                continue
            for role_dir in sorted(company_dir.iterdir()):
                if not role_dir.is_dir():
                    continue
                for emp_dir in sorted(role_dir.iterdir()):
                    if not emp_dir.is_dir():
                        continue
                    if not (emp_dir / "SOUL.md").exists():
                        continue
                    infos.append(AgentInfo(
                        company=company_dir.name,
                        role=role_dir.name,
                        employee_id=emp_dir.name,
                        home=emp_dir.resolve(),
                    ))
        return infos

    def list_running(self) -> list[str]:
        return list(self._agents.keys())

    def create(self, *args, **kwargs) -> HermesAgent:
        kwargs.setdefault("base_dir", self.base_dir)
        kwargs.setdefault("config", self.config)
        agent = HermesAgent.create(*args, **kwargs)
        return agent

    def load(self, *args, **kwargs) -> HermesAgent:
        kwargs.setdefault("base_dir", self.base_dir)
        kwargs.setdefault("config", self.config)
        return HermesAgent.load(*args, **kwargs)

    def create_or_load(self, *args, **kwargs) -> HermesAgent:
        kwargs.setdefault("base_dir", self.base_dir)
        kwargs.setdefault("config", self.config)
        return HermesAgent.create_or_load(*args, **kwargs)

    # ---- 启动 / 停止 --------------------------------------------------
    async def start(self, agent: HermesAgent) -> HermesAgent:
        await agent.start()
        self._agents[agent.label] = agent
        return agent

    async def stop(self, agent: HermesAgent | str) -> None:
        label = agent if isinstance(agent, str) else agent.label
        a = self._agents.pop(label, None)
        if a is not None:
            await a.stop()

    async def stop_all(self) -> None:
        await asyncio.gather(*(a.stop() for a in list(self._agents.values())), return_exceptions=True)
        self._agents.clear()

    # ---- 观察：把多个 agent 的事件流聚合到一个 async for ---------------
    async def watch(
        self,
        *agents: HermesAgent,
    ) -> AsyncIterator[tuple[str, Event]]:
        """并发聚合多个 agent 的事件流。

        用法：
            t1 = asyncio.create_task(run_task(agent_a, "任务 A"))
            t2 = asyncio.create_task(run_task(agent_b, "任务 B"))
            ...
            其实更推荐直接在业务代码里用 asyncio.gather + per-agent async for。

        本方法适合：已经在别处发送了 prompt 的多个 agent 想统一看输出时。
        但因为 send() 返回的是 per-call 迭代器，一般场景下直接用
        `asyncio.gather(consume(a), consume(b))` 即可，无需调本方法。
        """
        raise NotImplementedError(
            "watch() 是占位方法。每个 send() 本身就是独立的异步迭代器——"
            "多 agent 并发观察请用 asyncio.gather(consume(a), consume(b))。"
            "参考 examples/demo_multi.py"
        )
        yield  # unreachable
