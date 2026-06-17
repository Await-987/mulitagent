"""
HermesAgent — 一个数字员工 = 一个 ACP 子进程 + 独立的 HERMES_HOME。

设计要点
--------
1. 子进程 = `python -m acp_adapter`，由本地 venv 启动，HERMES_HOME 指向
   companies/<company>/<role>/<employee>/。完全跟系统 ~/.hermes 隔离。
2. 通过 acp.ClientSideConnection 跟子进程通信（JSON-RPC over stdio）。
3. 每次 send(text) 返回一个异步迭代器，流式 yield 结构化事件：
   text / thought / tool_start / tool_progress / plan / usage / done / error …
4. Client 端权限请求默认自动放行（can be overridden via permission_policy）。
"""

from __future__ import annotations

import asyncio
import logging
import os
import shutil
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, AsyncIterator, Awaitable, Callable, Iterable

import yaml

from ..runtime import DEFAULT_CONFIG, HermesRuntimeConfig
from ..world import HermesWorld, STANDARD_SUBDIRS

# --- 路径常量：仅保留向后兼容读法，运行时以 HermesRuntimeConfig 为准 ----
PROJECT_ROOT = DEFAULT_CONFIG.hermes_home
HERMES_AGENT_ROOT = DEFAULT_CONFIG.hermes_agent_root
VENV_PYTHON = DEFAULT_CONFIG.python_executable
BASE_CONFIG = DEFAULT_CONFIG.outer_config
COMPANIES_ROOT = DEFAULT_CONFIG.companies_dir
TEMPLATES_DIR = Path(__file__).resolve().parent / "templates"

logger = logging.getLogger(__name__)


def _copy_path(src: Path, dst: Path) -> None:
    if src.is_dir():
        shutil.copytree(
            src,
            dst,
            dirs_exist_ok=True,
            ignore=shutil.ignore_patterns("*.lock", "__pycache__"),
        )
    else:
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)


def _agent_home(
    base_dir: Path,
    company: str,
    role: str,
    employee_id: str,
    *,
    config: HermesRuntimeConfig,
) -> Path:
    if config.company_scoped_layout:
        return (base_dir / role / employee_id).resolve()
    return (base_dir / company / role / employee_id).resolve()


def _ensure_employee_skeleton(home: Path) -> None:
    for sub in WORLD_STANDARD_SUBDIRS or ("memories", "logs", "sessions", "skills"):
        (home / sub).mkdir(parents=True, exist_ok=True)


def _seed_employee_home_from_world(
    home: Path,
    world_home: Path,
    *,
    config_overrides: dict | None,
    soul: str | None,
    soul_extra: str | None,
    user_md: str | None,
    memory_md: str | None,
    company: str,
    employee_id: str,
    role_key: str,
    role_display: str | None,
    role_description: str | None,
) -> None:
    _ensure_employee_skeleton(home)

    for rel in (".env", "auth.json", "skills"):
        src = world_home / rel
        if src.exists():
            _copy_path(src, home / rel)

    config_src = world_home / "config.yaml"
    if not config_src.exists():
        raise FileNotFoundError(f"world role config not found: {config_src}")
    base_cfg = yaml.safe_load(config_src.read_text(encoding="utf-8")) or {}
    if config_overrides:
        base_cfg = _deep_merge(base_cfg, config_overrides)
    (home / "config.yaml").write_text(
        yaml.safe_dump(base_cfg, allow_unicode=True, sort_keys=False), encoding="utf-8"
    )

    soul_src = world_home / "SOUL.md"
    if soul is None:
        if soul_src.exists():
            soul = soul_src.read_text(encoding="utf-8")
        else:
            rd, desc = HermesAgent._resolve_role(role_key, role_display, role_description)
            tpl = (TEMPLATES_DIR / "SOUL.md.tpl").read_text(encoding="utf-8")
            soul = tpl.format(
                company=company,
                role_display=rd,
                employee_id=employee_id,
                role_description=desc,
            )
    if soul_extra:
        soul = soul.rstrip() + "\n\n[EXTRA]\n" + soul_extra.strip() + "\n"
    (home / "SOUL.md").write_text(soul, encoding="utf-8")

    world_user = world_home / "memories" / "USER.md"
    if user_md is None:
        if world_user.exists():
            user_md = world_user.read_text(encoding="utf-8")
        else:
            rd, _ = HermesAgent._resolve_role(role_key, role_display, role_description)
            tpl = (TEMPLATES_DIR / "USER.md.tpl").read_text(encoding="utf-8")
            user_md = tpl.format(company=company, role_display=rd, employee_id=employee_id)
    (home / "memories" / "USER.md").write_text(user_md, encoding="utf-8")

    world_memory = world_home / "memories" / "MEMORY.md"
    if memory_md is None:
        if world_memory.exists():
            memory_md = world_memory.read_text(encoding="utf-8")
        else:
            memory_md = (TEMPLATES_DIR / "MEMORY.md.tpl").read_text(encoding="utf-8")
    (home / "memories" / "MEMORY.md").write_text(memory_md, encoding="utf-8")

@dataclass
class Event:
    """一条从 agent 流回来的结构化消息。

    kind 对应 ACP 的 session_update 类型：
      - "text"           助手正文文本块（最常见）
      - "thought"        思考内容（reasoning）
      - "user_echo"      用户消息回显
      - "tool_start"     工具开始执行
      - "tool_progress"  工具执行中 / 完成
      - "plan"           计划更新
      - "usage"          token/turn 统计
      - "mode"           模式切换
      - "info"           session 级信息
      - "available_commands" 可用斜杠命令
      - "done"           本次 prompt 结束
      - "error"          流内错误（非致命）
      - "fatal"          致命错误，agent 已失联
    """

    kind: str
    text: str = ""
    data: dict[str, Any] = field(default_factory=dict)


# --- 权限策略 --------------------------------------------------------------

PermissionPolicy = Callable[[dict[str, Any]], Awaitable[str]]
# 返回 option_id；特殊值 "__deny__" = 拒绝


async def _auto_allow_once(request: dict[str, Any]) -> str:
    """默认策略：放行"allow_once"/"allow"，否则选第一个允许项，都没有则拒绝。"""
    for opt in request.get("options", []):
        kind = opt.get("kind", "")
        if kind in ("allow_once", "allow_always"):
            return opt["option_id"]
    for opt in request.get("options", []):
        if "allow" in opt.get("kind", ""):
            return opt["option_id"]
    return "__deny__"


WORLD_STANDARD_SUBDIRS: tuple[str, ...] = tuple(STANDARD_SUBDIRS)


def _load_world_role_home(world_role: str, *, config: HermesRuntimeConfig) -> Path:
    hw = HermesWorld.load(world_role, config=config)
    return Path(hw.home)


def _create_world_role_home(
    world_role: str,
    *,
    soul: str | None,
    user_md: str | None,
    memory_md: str | None,
    config: HermesRuntimeConfig,
) -> Path:
    hw = HermesWorld.create(
        world_role,
        soul=soul,
        overwrite=False,
        install_launcher=False,
        include_skills=True,
        config=config,
    )
    if user_md is not None:
        (Path(hw.home) / "memories" / "USER.md").write_text(user_md, encoding="utf-8")
    if memory_md is not None:
        (Path(hw.home) / "memories" / "MEMORY.md").write_text(memory_md, encoding="utf-8")
    return Path(hw.home)


def _resolve_world_role_home(
    world_role: str,
    *,
    create_role_if_missing: bool,
    soul: str | None,
    user_md: str | None,
    memory_md: str | None,
    config: HermesRuntimeConfig,
) -> Path:
    try:
        return _load_world_role_home(world_role, config=config)
    except FileNotFoundError:
        if not create_role_if_missing:
            raise FileNotFoundError(
                f"role template not found: {world_role}. "
                f"Create roles_dir/{world_role} first, or call HermesAgent.create(..., "
                f"create_role_if_missing=True, soul=..., user_md=..., memory_md=...)."
            )
        if soul is None or user_md is None or memory_md is None:
            raise FileNotFoundError(
                f"role template not found: {world_role}. "
                f"create_role_if_missing=True requires soul, user_md, and memory_md."
            )
        return _create_world_role_home(
            world_role,
            soul=soul,
            user_md=user_md,
            memory_md=memory_md,
            config=config,
        )


# --- HermesAgent -----------------------------------------------------------

class HermesAgent:
    """一个数字员工。用法：

        agent = await HermesAgent.create(
            company="avataria",
            role="full_stack_coder",
            employee_id="alice",
            soul_extra="特别擅长 Python 后端",
        )
        await agent.start()
        async for ev in agent.send("写个 fibonacci"):
            print(ev.kind, ev.text)
        await agent.stop()
    """

    # ------------------------------------------------------------------
    # 构造 / 工厂
    # ------------------------------------------------------------------
    def __init__(
        self,
        company: str,
        role: str,
        employee_id: str,
        *,
        base_dir: Path | None = None,
        config: HermesRuntimeConfig | None = None,
        permission_policy: PermissionPolicy | None = None,
    ):
        self.config = config or DEFAULT_CONFIG
        self.company = company
        self.role = role
        self.employee_id = employee_id
        self.base_dir = Path(base_dir) if base_dir else self.config.companies_dir
        self.home = _agent_home(
            self.base_dir,
            company,
            role,
            employee_id,
            config=self.config,
        )
        self.permission_policy = permission_policy or _auto_allow_once

        self._proc: asyncio.subprocess.Process | None = None
        self._conn = None
        self._stderr_task: asyncio.Task | None = None
        self._session_id: str | None = None
        # 活跃的事件队列：一个 send() 会占一个
        self._active_queue: asyncio.Queue[Event] | None = None
        self._lock = asyncio.Lock()

        # 安全断言：home 必须在 base_dir 下
        if not str(self.home).startswith(str(self.base_dir.resolve()) + os.sep):
            raise RuntimeError(
                f"拒绝启动：agent home ({self.home}) 不在 base_dir ({self.base_dir}) 下。"
            )
        if self.home == self.config.hermes_home.resolve():
            raise RuntimeError(f"拒绝启动：agent home 不能是 HERMES_HOME：{self.home}")

    @property
    def label(self) -> str:
        return f"{self.company}/{self.role}/{self.employee_id}"

    # ------------------------------------------------------------------
    # 磁盘初始化
    # ------------------------------------------------------------------
    @classmethod
    def create(
        cls,
        company: str,
        role: str,
        employee_id: str,
        *,
        soul: str | None = None,
        soul_extra: str | None = None,
        user_md: str | None = None,
        memory_md: str | None = None,
        role_display: str | None = None,
        role_description: str | None = None,
        world_role: str | None = None,
        config_overrides: dict | None = None,
        create_role_if_missing: bool = False,
        base_dir: Path | None = None,
        config: HermesRuntimeConfig | None = None,
        overwrite: bool = False,
        permission_policy: PermissionPolicy | None = None,
    ) -> "HermesAgent":
        """在磁盘上落一份新员工。不启动子进程。"""
        cfg = config or DEFAULT_CONFIG
        agent = cls(
            company,
            role,
            employee_id,
            base_dir=base_dir,
            config=cfg,
            permission_policy=permission_policy,
        )
        resolved_world_role = world_role or role
        world_home = _resolve_world_role_home(
            resolved_world_role,
            create_role_if_missing=create_role_if_missing,
            soul=soul,
            user_md=user_md,
            memory_md=memory_md,
            config=cfg,
        )
        role_key = resolved_world_role

        if agent.home.exists() and not overwrite:
            raise FileExistsError(
                f"agent already exists: {agent.home}（传 overwrite=True 可覆盖）"
            )

        agent.home.mkdir(parents=True, exist_ok=True)
        _seed_employee_home_from_world(
            agent.home,
            world_home,
            config_overrides=config_overrides,
            soul=soul,
            soul_extra=soul_extra,
            user_md=user_md,
            memory_md=memory_md,
            company=company,
            employee_id=employee_id,
            role_key=role_key,
            role_display=role_display,
            role_description=role_description,
        )

        logger.info("Created agent at %s from world role %s", agent.home, resolved_world_role)
        return agent

    @classmethod
    def load(
        cls,
        company: str,
        role: str,
        employee_id: str,
        *,
        base_dir: Path | None = None,
        config: HermesRuntimeConfig | None = None,
        permission_policy: PermissionPolicy | None = None,
    ) -> "HermesAgent":
        agent = cls(
            company,
            role,
            employee_id,
            base_dir=base_dir,
            config=config,
            permission_policy=permission_policy,
        )
        if not agent.home.exists():
            raise FileNotFoundError(f"agent not found: {agent.home}")
        return agent

    @classmethod
    def create_or_load(cls, *args, **kwargs) -> "HermesAgent":
        """存在就 load，不存在就 create。create 参数全部透传。"""
        company = kwargs.get("company") or args[0]
        role = kwargs.get("role") or args[1]
        employee_id = kwargs.get("employee_id") or args[2]
        base_dir = kwargs.get("base_dir")
        config = kwargs.get("config") or DEFAULT_CONFIG
        home = _agent_home(
            Path(base_dir) if base_dir else config.companies_dir,
            company,
            role,
            employee_id,
            config=config,
        )
        if home.exists():
            return cls.load(
                company, role, employee_id,
                base_dir=base_dir,
                config=config,
                permission_policy=kwargs.get("permission_policy"),
            )
        return cls.create(*args, **kwargs)

    @staticmethod
    def _resolve_role(role: str, role_display: str | None, role_description: str | None):
        if role_display and role_description:
            return role_display, role_description
        roles_file = TEMPLATES_DIR / "roles.yaml"
        roles = yaml.safe_load(roles_file.read_text(encoding="utf-8")) or {}
        r = roles.get(role, {})
        return (
            role_display or r.get("display") or role.replace("_", " ").title(),
            role_description or r.get("description") or f"{role} 岗位的日常职责。",
        )

    # ------------------------------------------------------------------
    # 运行时：启动 / 停止
    # ------------------------------------------------------------------
    async def start(self, *, protocol_version: int = 1) -> None:
        """spawn ACP subprocess + 建立连接 + new_session。"""
        if self._proc is not None:
            return

        # 懒加载 acp。迁移期可从 Hermes runtime 的 Python 环境补齐依赖。
        self.config.ensure_python_site_packages()
        try:
            import acp
            from acp.schema import Implementation, ClientCapabilities
        except ModuleNotFoundError as exc:
            raise RuntimeError(
                "当前 Python 环境无法导入 agent-client-protocol/acp。"
                "请用 Hermes 的 Python 运行 AIOS，或把 Hermes/ACP 依赖安装到当前环境。"
                f" Hermes Python: {self.config.python_executable}"
            ) from exc

        env = self._build_env()

        self._proc = await asyncio.create_subprocess_exec(
            str(self.config.python_executable), "-m", "acp_adapter",
            cwd=str(self.config.hermes_agent_root),
            env=env,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            limit=50 * 1024 * 1024,
        )
        assert self._proc.stdin is not None and self._proc.stdout is not None and self._proc.stderr is not None

        # 把子进程 stderr 写到 agent 自己的 logs/acp.stderr.log
        self._stderr_task = asyncio.create_task(
            self._drain_stderr(self._proc.stderr, self.home / "logs" / "acp.stderr.log"),
            name=f"stderr[{self.label}]",
        )

        # ACP 客户端连接: input_stream=写给 agent, output_stream=读 agent
        # connect_to_agent 内部会起接收 loop (listening=True)
        client = _AgentClient(self)
        self._conn = acp.connect_to_agent(
            client,
            self._proc.stdin,
            self._proc.stdout,
        )

        # initialize
        await self._conn.initialize(
            protocol_version=protocol_version,
            client_capabilities=ClientCapabilities(),
            client_info=Implementation(name="hermes-orchestrator", version="0.1.0"),
        )

        # new_session —— cwd 就用 agent 自己的 home，让 agent 的工作目录也隔离
        resp = await self._conn.new_session(cwd=str(self.home))
        self._session_id = resp.session_id
        logger.info("[%s] session started: %s", self.label, self._session_id)

    async def stop(self) -> None:
        if self._proc is None:
            return
        try:
            if self._conn is not None:
                try:
                    await asyncio.wait_for(self._conn.close(), timeout=2.0)
                except Exception:
                    pass
            self._proc.terminate()
            try:
                await asyncio.wait_for(self._proc.wait(), timeout=3.0)
            except asyncio.TimeoutError:
                self._proc.kill()
                await self._proc.wait()
        finally:
            self._proc = None
            self._conn = None
            if self._stderr_task:
                self._stderr_task.cancel()
                self._stderr_task = None
            self._session_id = None
            logger.info("[%s] stopped", self.label)

    async def __aenter__(self):
        await self.start()
        return self

    async def __aexit__(self, *exc):
        await self.stop()

    # ------------------------------------------------------------------
    # 核心：发 prompt & 流式拿事件
    # ------------------------------------------------------------------
    async def send(self, text: str) -> AsyncIterator[Event]:
        """发送一条 prompt，返回异步迭代器流式 yield 事件。

        用法：
            async for ev in agent.send("写个登录接口"):
                print(ev.kind, ev.text)
        """
        if self._proc is None or self._conn is None or self._session_id is None:
            raise RuntimeError(f"agent {self.label} not started — 先 await agent.start()")

        from acp.schema import TextContentBlock

        async with self._lock:
            if self._active_queue is not None:
                raise RuntimeError(f"agent {self.label} 正在处理另一条 prompt，先 await 完再发下一条")
            queue: asyncio.Queue[Event] = asyncio.Queue()
            self._active_queue = queue

        async def _run_prompt():
            try:
                resp = await self._conn.prompt(
                    prompt=[TextContentBlock(type="text", text=text)],
                    session_id=self._session_id,
                )
                # prompt() 返回后，尾部 session_update 通知可能还在 dispatcher
                # 队列里没处理完。这里做一个"静默窗口"：只要还有新事件进入队列，
                # 就继续等；连续 50ms 没新事件视为真的 done。
                import time
                settle = 0.05
                last_seen = time.monotonic()
                prev_size = queue.qsize()
                while time.monotonic() - last_seen < settle:
                    await asyncio.sleep(0.01)
                    now_size = queue.qsize()
                    if now_size != prev_size:
                        prev_size = now_size
                        last_seen = time.monotonic()
                await queue.put(Event("done", data={"stop_reason": str(resp.stop_reason)}))
            except Exception as e:  # noqa: BLE001
                await queue.put(Event("fatal", text=f"{type(e).__name__}: {e}"))
            finally:
                # 哨兵：None 表示流结束
                await queue.put(None)  # type: ignore[arg-type]

        prompt_task = asyncio.create_task(_run_prompt(), name=f"prompt[{self.label}]")

        try:
            while True:
                ev = await queue.get()
                if ev is None:
                    break
                yield ev
        finally:
            async with self._lock:
                self._active_queue = None
            if not prompt_task.done():
                prompt_task.cancel()
                try:
                    await prompt_task
                except (asyncio.CancelledError, Exception):
                    pass

    async def ask(self, text: str) -> str:
        """Send one prompt and return the joined assistant text."""
        chunks: list[str] = []
        async for ev in self.send(text):
            if ev.kind == "text" and ev.text:
                chunks.append(ev.text)
            elif ev.kind == "fatal":
                detail = ev.text or str(ev.data) or "Hermes agent failed"
                raise RuntimeError(detail)
        return "".join(chunks).strip()

    async def cancel(self) -> None:
        """取消当前正在跑的 prompt。"""
        if self._conn is None or self._session_id is None:
            return
        try:
            await self._conn.cancel(self._session_id)
        except Exception:
            logger.debug("[%s] cancel failed", self.label, exc_info=True)

    # ------------------------------------------------------------------
    # 内部：env 构造 + stderr 引流 + client 事件回调入口
    # ------------------------------------------------------------------
    def _build_env(self) -> dict[str, str]:
        """构造子进程 env：
        - 硬绑定 HERMES_HOME 到 agent home
        - 清掉继承自父进程的 HERMES_* 避免污染
        - 最小化 HOME（子进程读写不要碰用户 home）
        """
        return self.config.env_for(self.home)

    async def _drain_stderr(self, reader: asyncio.StreamReader, dest: Path) -> None:
        dest.parent.mkdir(parents=True, exist_ok=True)
        # 用 append 模式，重启时不清空
        with dest.open("ab") as f:
            while True:
                line = await reader.readline()
                if not line:
                    break
                f.write(line)
                f.flush()

    # called by _AgentClient when ACP session_update arrives
    async def _push_event(self, ev: Event) -> None:
        q = self._active_queue
        if q is not None:
            await q.put(ev)
        else:
            # 没有活跃 send() 的时候忽略（如初始化阶段的 available_commands）
            logger.debug("[%s] drop event (no active queue): %s", self.label, ev.kind)


# --- ACP Client 适配：把 session_update 翻译成 Event ----------------------

class _AgentClient:
    """实现 acp.Client 协议。session_update / request_permission 在这里落到 HermesAgent。"""

    def __init__(self, agent: HermesAgent):
        self._agent = agent

    def on_connect(self, conn: Any) -> None:
        pass

    # ---- 事件入口 -----------------------------------------------------
    async def session_update(self, session_id: str, update: Any, **kwargs: Any) -> None:
        ev = _translate_update(update)
        if ev is not None:
            await self._agent._push_event(ev)

    # ---- 权限请求 -----------------------------------------------------
    async def request_permission(self, options, session_id, tool_call, **kwargs):
        from acp.schema import (
            RequestPermissionResponse,
            AllowedOutcome,
            DeniedOutcome,
            SelectedPermissionOutcome,
        )
        # 扁平化供 policy 消费
        req = {
            "session_id": session_id,
            "tool_call": _to_dict(tool_call),
            "options": [_to_dict(o) for o in options],
        }
        choice = await self._agent.permission_policy(req)
        # 推 event 让观察者能看见
        await self._agent._push_event(Event(
            "tool_progress",
            text=f"[permission] {req['tool_call'].get('title', '?')} -> {choice}",
            data={"phase": "permission", "choice": choice, "request": req},
        ))
        if choice == "__deny__":
            return RequestPermissionResponse(outcome=DeniedOutcome(outcome="denied"))
        return RequestPermissionResponse(
            outcome=AllowedOutcome(outcome="selected", option_id=choice)
        )

    # ---- 不实现的可选方法（返回 None 让 ACP 层报"not supported"）-----
    # 但某些方法是必需的（文件/终端），我们给空实现
    async def write_text_file(self, **kwargs): return None
    async def read_text_file(self, **kwargs):
        from acp.schema import ReadTextFileResponse
        return ReadTextFileResponse(content="")
    async def create_terminal(self, **kwargs): return None
    async def terminal_output(self, **kwargs): return None
    async def release_terminal(self, **kwargs): return None
    async def wait_for_terminal_exit(self, **kwargs): return None
    async def kill_terminal(self, **kwargs): return None
    async def ext_method(self, method, params): return {}
    async def ext_notification(self, method, params): return None


# --- 工具函数 -------------------------------------------------------------

def _to_dict(x: Any) -> dict:
    if hasattr(x, "model_dump"):
        return x.model_dump(by_alias=True, exclude_none=True)
    if isinstance(x, dict):
        return x
    return {"value": str(x)}


def _translate_update(update: Any) -> Event | None:
    """把 ACP session_update 对象转成我们的 Event。"""
    d = _to_dict(update)
    kind = d.get("sessionUpdate") or d.get("session_update") or "unknown"

    # 文本类
    if kind in ("agent_message_chunk", "user_message_chunk", "agent_thought_chunk"):
        content = d.get("content", {})
        text = ""
        if isinstance(content, dict):
            text = content.get("text") or content.get("data") or ""
        mapping = {
            "agent_message_chunk": "text",
            "user_message_chunk": "user_echo",
            "agent_thought_chunk": "thought",
        }
        return Event(mapping[kind], text=text, data=d)

    if kind == "tool_call":
        return Event(
            "tool_start",
            text=d.get("title", d.get("tool_name", "tool")),
            data=d,
        )

    if kind == "tool_call_update":
        return Event(
            "tool_progress",
            text=d.get("status", "") or d.get("title", ""),
            data=d,
        )

    if kind == "plan":
        entries = d.get("entries", [])
        text = "\n".join(f"- {e.get('content','')}" for e in entries)
        return Event("plan", text=text, data=d)

    if kind == "usage_update":
        u = d
        text = f"tokens in/out: {u.get('input_tokens','?')}/{u.get('output_tokens','?')}"
        return Event("usage", text=text, data=d)

    if kind == "current_mode_update":
        return Event("mode", text=d.get("current_mode_id", ""), data=d)

    if kind == "session_info_update":
        return Event("info", text="", data=d)

    if kind == "available_commands_update":
        cmds = [c.get("name", "") for c in d.get("available_commands", [])]
        return Event("available_commands", text=", ".join(cmds), data=d)

    if kind == "config_option_update":
        return Event("info", text=f"config: {d.get('config_id','?')}", data=d)

    # 未识别的也透传一个 info 事件
    return Event("info", text=f"[{kind}]", data=d)


def _deep_merge(base: dict, override: dict) -> dict:
    out = dict(base)
    for k, v in override.items():
        if k in out and isinstance(out[k], dict) and isinstance(v, dict):
            out[k] = _deep_merge(out[k], v)
        else:
            out[k] = v
    return out
