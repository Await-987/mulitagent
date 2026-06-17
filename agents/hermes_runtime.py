from __future__ import annotations

import json
import os
import shutil
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import yaml
from camel.agents.chat_agent import ChatAgent
from camel.messages.base import BaseMessage
from camel.toolkits import NoteTakingToolkit, ToolkitMessageIntegration
from hermes_platform import HermesPlatform

from tools import (
    ContactorsToolkit,
    NotesRetrievalToolkit,
    PhotosToolkit,
    SoulToolkit,
    UIHumanToolkit,
    XiaoHongShuToolkit,
    XiechengToolkit,
)
from .backend_model import backend_model
from .backend_model import QWEN_API_KEY, QWEN_BASE_URL, QWEN_MODEL_TYPE
from .message import send_message_to_user

BASE_DIR = Path(__file__).resolve().parent.parent
DEFAULT_AIOS_HERMES_RUNTIME_DIR = BASE_DIR / "runtime" / "hermes"
SOUL_JSON_PATH = BASE_DIR / "mock_data" / "soul" / "soul.json"
EXPERIENCES_JSON_PATH = BASE_DIR / "mock_data" / "soul" / "experiences.json"

WORKING_DIRECTORY = os.environ.get("CAMEL_WORKDIR") or os.path.abspath("working_dir/")
SOUL_MCP_SERVER = BASE_DIR / "mcp_servers" / "soul_mcp_server.py"


class AIOSHermesAgent:
    def __init__(
        self,
        *,
        role: str,
        employee_id: str,
        system_message: str,
        company: str | None = None,
    ):
        self.company = company or "aios"
        self.role = role
        self.employee_id = employee_id
        self.system_message = system_message
        runtime_dir = os.environ.get("AIOS_HERMES_RUNTIME_DIR") or str(DEFAULT_AIOS_HERMES_RUNTIME_DIR)
        agents_dir = str(Path(runtime_dir) / "agents")
        self._platform = HermesPlatform(
            namespace=self.company,
            hermes_home=os.environ.get("AIOS_HERMES_HOME"),
            hermes_agent_root=os.environ.get("AIOS_HERMES_AGENT_ROOT"),
            python_executable=sys.executable,
            runtime_dir=runtime_dir,
            profiles_dir=agents_dir,
            instances_dir=agents_dir,
        )
        self._agent = self._platform.create_or_load_agent(
            profile=role,
            instance_id=employee_id,
            soul=self._build_employee_soul(system_message),
            user_md=self._build_user_md(),
            memory_md=self._build_memory_md(),
            create_role_if_missing=True,
        )
        self._started = False

    async def start(self):
        if not self._started:
            started_at = time.monotonic()
            self._sync_employee_home()
            self._sync_runtime_config()
            self._sync_runtime_auth()
            await self._agent.start()
            self._started = True
            self._debug(f"started in {time.monotonic() - started_at:.1f}s")
        return self

    async def run(self, task: str) -> str:
        await self.start()
        return await self._ask_with_trace(task)

    async def stop(self):
        if self._started:
            await self._agent.stop()
            self._started = False

    @staticmethod
    def _load_user_profile() -> dict:
        with SOUL_JSON_PATH.open(encoding="utf-8") as f:
            return json.load(f)

    @staticmethod
    def _load_experiences() -> list[dict]:
        with EXPERIENCES_JSON_PATH.open(encoding="utf-8") as f:
            return json.load(f)

    @staticmethod
    def _build_employee_soul(system_message: str) -> str:
        return (
            "# AIOS Soul Agent\n\n"
            "你是 AIOS 的 Soul Agent。你的职责是基于用户档案和长期经历补全任务上下文，"
            "并在任务执行完成后帮助更新用户画像。你不是执行层 agent，不直接完成 Workforce 的业务操作。\n\n"
            "## 可用工具\n\n"
            "你有以下 MCP 工具可以直接调用（不需要 terminal）：\n\n"
            "- `soul__get_user_soul` — 读取用户完整画像（个人信息 + 经历记录）\n"
            "- `soul__get_task_status` — 读取当前任务执行状态\n"
            "- `soul__update_soul_profile` — 更新用户画像字段 (key, value)\n"
            "- `soul__append_experience` — 追加用户经历记录\n"
            "- `soul__ask_human` — 向用户提问并等待回答（弹出聊天气泡）\n\n"
            "## 与用户交互（重要）\n\n"
            "你要主动理解和丰富任务，不要机械转发用户原话。需要澄清或补足关键信息时，"
            "直接调用 `soul__ask_human` 工具。\n"
            "- 对发布小红书、发送消息、下单/预订、删除数据、修改长期画像等外部可见或持久化动作，"
            "handoff 前必须先问用户一句：概括你准备让 AIOS 做什么，并询问是否有内容、语气、素材或限制需要调整。\n"
            "- 对创作类任务，如果主题、受众、语气、素材选择、是否带图等关键信息缺失且无法从用户画像推断，"
            "先问一个合并问题。\n"
            "- 同一个任务最多问 1–2 次。能从 soul__get_user_soul 推断的偏好不要问。\n"
            "- 如果用户明确说「不用问」「直接发」「你自己发挥」，或返回空，按合理默认值继续，不要反复追问。\n"
            "- 最终输出必须只包含给 Workforce 的 enriched task，不包含问号。\n\n"
            "## 规则\n\n"
            "- 在对话中学到的用户偏好、习惯等信息，用 Hermes 内置 memory tool 保存到 USER.md。\n"
            "- 如果用户给出的任务还不够让 Workforce 稳定执行，先通过 soul__ask_human 补齐高影响信息；"
            "不要因为任务动词明确就直接 handoff。\n"
            "- 最终 handoff 输出必须是 enriched task。\n\n"
            "## Operating Rules\n\n"
            f"{system_message.strip()}\n"
        )

    @classmethod
    def _build_user_md(cls) -> str:
        profile = cls._load_user_profile()
        preferences = profile.get("偏好", [])
        habits = profile.get("习惯", [])
        lines = [
            "# 当前服务对象",
            "",
            f"- 姓名：{profile.get('姓名', '未知')}",
            f"- 身份：{profile.get('社会身份', '未知')}",
            f"- 居住地：{profile.get('居住地', '未知')}",
            f"- 性格：{profile.get('性格', '未知')}",
            "",
            "## 稳定偏好",
        ]
        lines.extend(f"- {item}" for item in preferences[:6])
        lines.extend([
            "",
            "## 行为习惯",
        ])
        lines.extend(f"- {item}" for item in habits[:6])
        lines.extend([
            "",
            "## 说明",
            "- 这是当前用户的稳定背景摘要。更动态的任务上下文、完整画像字段和最新经历应通过工具进一步读取。",
        ])
        return "\n".join(lines) + "\n"

    @classmethod
    def _build_memory_md(cls) -> str:
        profile = cls._load_user_profile()
        experiences = cls._load_experiences()
        lines = [
            "# 长期记忆摘要",
            "",
            "## 关键长期偏好",
        ]
        for item in profile.get("偏好", [])[:4]:
            lines.append(f"- {item}")
        lines.extend([
            "",
            "## 关键经历",
        ])
        for item in experiences[-4:]:
            name = item.get("名称", "未命名经历")
            when = item.get("时间", "时间未知")
            content = item.get("内容", "")
            lines.append(f"- {when} · {name}：{content}")
        lines.extend([
            "",
            "## 说明",
            "- 这里保留长期稳定的记忆摘要，详细结构化画像与完整经历列表以 Python 工具读取结果为准。",
        ])
        return "\n".join(lines) + "\n"

    def _sync_employee_home(self) -> None:
        home = self._agent.home
        # SOUL.md is code-driven instructions — always overwrite
        (home / "SOUL.md").write_text(self._build_employee_soul(self.system_message), encoding="utf-8")
        # USER.md/MEMORY.md: only seed on first creation.
        # Hermes's built-in memory tool manages these after that.
        memories_dir = home / "memories"
        memories_dir.mkdir(parents=True, exist_ok=True)
        user_md = memories_dir / "USER.md"
        memory_md = memories_dir / "MEMORY.md"
        if not user_md.exists():
            user_md.write_text(self._build_user_md(), encoding="utf-8")
        if not memory_md.exists():
            memory_md.write_text(self._build_memory_md(), encoding="utf-8")
        # Remove legacy SKILL.md-based tool bridge if present
        legacy_skill = home / "skills" / "aios_soul_tool_bridge"
        if legacy_skill.exists():
            shutil.rmtree(legacy_skill, ignore_errors=True)

    def _sync_runtime_config(self) -> None:
        config_path = self._agent.home / "config.yaml"
        if not config_path.exists():
            return
        cfg = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}

        model_cfg = cfg.setdefault("model", {})
        model_cfg["default"] = QWEN_MODEL_TYPE
        model_cfg["model"] = QWEN_MODEL_TYPE
        model_cfg["provider"] = "custom"
        model_cfg["base_url"] = QWEN_BASE_URL
        model_cfg["api_key"] = QWEN_API_KEY
        model_cfg["context_length"] = int(os.environ.get("AIOS_HERMES_CONTEXT_LENGTH", "500000"))
        model_cfg["max_tokens"] = int(os.environ.get("AIOS_HERMES_MODEL_MAX_TOKENS", "4096"))

        custom_provider = {
            "name": QWEN_MODEL_TYPE,
            "base_url": QWEN_BASE_URL,
            "api_key": QWEN_API_KEY,
            "model": QWEN_MODEL_TYPE,
        }
        cfg["custom_providers"] = [custom_provider]

        agent_cfg = cfg.setdefault("agent", {})
        agent_cfg["max_turns"] = int(os.environ.get("AIOS_HERMES_MAX_TURNS", "12"))
        agent_cfg["gateway_timeout"] = int(os.environ.get("AIOS_HERMES_GATEWAY_TIMEOUT", "300"))
        agent_cfg["gateway_timeout_warning"] = int(
            os.environ.get("AIOS_HERMES_GATEWAY_TIMEOUT_WARNING", "120")
        )
        agent_cfg["reasoning_effort"] = os.environ.get("AIOS_HERMES_REASONING_EFFORT", "low")

        # Plan A: Hermes built-in memory manages USER.md/MEMORY.md after initial seed
        memory_cfg = cfg.setdefault("memory", {})
        memory_cfg["memory_enabled"] = True
        memory_cfg["user_profile_enabled"] = True

        auxiliary_cfg = cfg.setdefault("auxiliary", {})
        for name in (
            "vision",
            "web_extract",
            "compression",
            "session_search",
            "skills_hub",
            "approval",
            "mcp",
            "flush_memories",
            "title_generation",
        ):
            aux = auxiliary_cfg.setdefault(name, {})
            aux["provider"] = "custom"
            aux["model"] = QWEN_MODEL_TYPE
            aux["base_url"] = QWEN_BASE_URL
            aux["api_key"] = QWEN_API_KEY
        compression_cfg = auxiliary_cfg.setdefault("compression", {})
        compression_cfg["context_length"] = int(os.environ.get("AIOS_HERMES_CONTEXT_LENGTH", "500000"))
        title_cfg = auxiliary_cfg.setdefault("title_generation", {})
        title_cfg["timeout"] = int(os.environ.get("AIOS_HERMES_TITLE_TIMEOUT", "8"))

        # Inject MCP server for Soul tools
        mcp_cfg = cfg.setdefault("mcp_servers", {})
        mcp_cfg["soul"] = {
            "command": str(self._platform.config.python_executable),
            "args": [str(SOUL_MCP_SERVER)],
            "env": {
                "AIOS_CURRENT_SESSION_ID": "${AIOS_CURRENT_SESSION_ID}",
                "AIOS_OSVIEW_PORT": "${AIOS_OSVIEW_PORT}",
                "AIOS_SOUL_DEFAULT_REPLY": os.environ.get("AIOS_SOUL_DEFAULT_REPLY", "你自己发挥"),
            },
            "timeout": 320,
        }

        config_path.write_text(
            yaml.safe_dump(cfg, allow_unicode=True, sort_keys=False), encoding="utf-8"
        )

    def _sync_runtime_auth(self) -> None:
        credential = {
            "id": "aios-qwen36",
            "label": "model_config",
            "auth_type": "api_key",
            "priority": 0,
            "source": "model_config",
            "access_token": QWEN_API_KEY,
            "last_status": "ok",
            "last_status_at": None,
            "last_error_code": None,
            "last_error_reason": None,
            "last_error_message": None,
            "last_error_reset_at": None,
            "base_url": QWEN_BASE_URL,
            "request_count": 0,
        }
        auth = {
            "version": 1,
            "providers": {},
            "active_provider": None,
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "credential_pool": {
                f"custom:{QWEN_MODEL_TYPE}": [credential],
            },
        }
        for auth_path in {
            self._agent.home / "auth.json",
            self._agent.home.parent / "auth.json",
        }:
            auth_path.parent.mkdir(parents=True, exist_ok=True)
            auth_path.write_text(
                json.dumps(auth, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )

    async def _ask_with_trace(self, task: str) -> str:
        started_at = time.monotonic()
        chunks: list[str] = []
        events: list[dict] = []
        self._debug(f"prompt started: {task[:120]}")

        async for ev in self._agent.send(task):
            elapsed = time.monotonic() - started_at
            record = {
                "seconds": round(elapsed, 3),
                "kind": ev.kind,
                "text": self._truncate(ev.text),
                "data": self._compact_data(ev.data),
            }
            events.append(record)
            self._debug(f"+{elapsed:.1f}s {ev.kind}: {self._truncate(ev.text, 160)}")

            if ev.kind == "text" and ev.text:
                chunks.append(ev.text)
            elif ev.kind == "fatal":
                self._write_event_trace(task, events, time.monotonic() - started_at)
                detail = ev.text or str(ev.data) or "Hermes agent failed"
                raise RuntimeError(detail)

        reply = "".join(chunks).strip()
        self._write_event_trace(task, events, time.monotonic() - started_at, reply=reply)
        return reply

    def _write_event_trace(
        self,
        task: str,
        events: list[dict],
        total_seconds: float,
        *,
        reply: str = "",
    ) -> None:
        trace = {
            "task": task,
            "total_seconds": round(total_seconds, 3),
            "event_count": len(events),
            "reply_preview": self._truncate(reply, 1000),
            "events": events,
        }
        trace_path = self._agent.home / "logs" / "aios_hermes_events.json"
        trace_path.parent.mkdir(parents=True, exist_ok=True)
        trace_path.write_text(json.dumps(trace, ensure_ascii=False, indent=2), encoding="utf-8")

    @staticmethod
    def _compact_data(data: dict) -> dict:
        compact: dict = {}
        for key, value in data.items():
            compact[key] = AIOSHermesAgent._truncate(str(value), 500)
        return compact

    @staticmethod
    def _truncate(text: str, limit: int = 300) -> str:
        if not text:
            return ""
        return text if len(text) <= limit else text[:limit] + "...<truncated>"

    def _debug(self, message: str) -> None:
        if os.environ.get("AIOS_HERMES_DEBUG", "").strip() in {"1", "true", "True", "yes"}:
            print(f"[AIOS Hermes {self.role}/{self.employee_id}] {message}")


class AIOSHermesSoulAgent(AIOSHermesAgent):
    def __init__(self, *, employee_id: str, system_message: str, company: str | None = None):
        super().__init__(
            company=company,
            role="soul_agent",
            employee_id=employee_id,
            system_message=system_message,
        )
        self._fallback_system_message = system_message
        self._fallback_agent: ChatAgent | None = None
        self._fallback_mode = self._load_fallback_mode()

    @staticmethod
    def _load_fallback_mode() -> str:
        mode = os.environ.get("AIOS_HERMES_FALLBACK", "on_error").strip().lower()
        allowed_modes = {"never", "on_error", "on_empty", "always"}
        if mode not in allowed_modes:
            raise ValueError(
                "AIOS_HERMES_FALLBACK must be one of: "
                f"{', '.join(sorted(allowed_modes))}; got {mode!r}"
            )
        return mode

    @property
    def fallback_agent(self) -> ChatAgent:
        if self._fallback_agent is None:
            self._fallback_agent = self._build_fallback_agent(self._fallback_system_message)
        return self._fallback_agent

    def _build_fallback_agent(self, system_message: str) -> ChatAgent:
        message_integration = ToolkitMessageIntegration(message_handler=send_message_to_user)

        soul_toolkit = message_integration.register_toolkits(SoulToolkit())
        note_toolkit = message_integration.register_toolkits(
            NoteTakingToolkit(working_directory=WORKING_DIRECTORY)
        )
        contactors_toolkit = message_integration.register_toolkits(ContactorsToolkit())
        notes_retrieval_toolkit = message_integration.register_toolkits(NotesRetrievalToolkit())
        photos_toolkit = message_integration.register_toolkits(PhotosToolkit())
        xiecheng_toolkit = message_integration.register_toolkits(XiechengToolkit())
        xiaohongshu_toolkit = message_integration.register_toolkits(XiaoHongShuToolkit())
        human_ask = message_integration.register_functions([UIHumanToolkit().ask_human_via_console])

        tools = [
            *soul_toolkit.get_tools(),
            *human_ask,
            *note_toolkit.get_tools(),
            *contactors_toolkit.get_soul_tools(),
            *notes_retrieval_toolkit.get_soul_tools(),
            *photos_toolkit.get_soul_tools(),
            *xiecheng_toolkit.get_soul_tools(),
            *xiaohongshu_toolkit.get_soul_tools(),
        ]

        return ChatAgent(
            system_message=BaseMessage.make_assistant_message(
                role_name="Soul Agent",
                content=system_message,
            ),
            model=backend_model(),
            tools=tools,
        )

    async def run(self, task: str) -> str:
        hermes_started_at = time.monotonic()
        hermes_reply = ""
        hermes_error = ""
        fallback_reply = ""
        fallback_seconds = 0.0

        try:
            hermes_reply = await super().run(task)
        except Exception as exc:
            hermes_error = f"{type(exc).__name__}: {exc}"
            if self._fallback_mode not in {"on_error", "always"}:
                self._write_runtime_trace(
                    task,
                    hermes_reply,
                    fallback_reply,
                    hermes_error=hermes_error,
                    hermes_seconds=time.monotonic() - hermes_started_at,
                    fallback_seconds=fallback_seconds,
                    fallback_mode=self._fallback_mode,
                )
                raise

        hermes_seconds = time.monotonic() - hermes_started_at
        should_fallback = (
            self._fallback_mode == "always"
            or (self._fallback_mode == "on_error" and bool(hermes_error))
            or (self._fallback_mode == "on_empty" and not hermes_reply.strip())
        )
        if should_fallback:
            fallback_started_at = time.monotonic()
            fallback_reply = self._get_response_content(self.fallback_agent.step(task))
            fallback_seconds = time.monotonic() - fallback_started_at

        self._write_runtime_trace(
            task,
            hermes_reply,
            fallback_reply,
            hermes_error=hermes_error,
            hermes_seconds=hermes_seconds,
            fallback_seconds=fallback_seconds,
            fallback_mode=self._fallback_mode,
        )
        return fallback_reply or hermes_reply

    @staticmethod
    def _get_response_content(result) -> str:
        if result.msg is not None and result.msg.content.strip():
            return result.msg.content
        for msg in reversed(result.msgs):
            content = (msg.content or "").strip()
            if content and not content.startswith("{") and not content.startswith("["):
                return content
        return ""

    def _write_runtime_trace(
        self,
        task: str,
        hermes_reply: str,
        fallback_reply: str,
        *,
        hermes_error: str = "",
        hermes_seconds: float = 0.0,
        fallback_seconds: float = 0.0,
        fallback_mode: str = "",
    ) -> None:
        trace = {
            "task": task,
            "fallback_mode": fallback_mode,
            "hermes_seconds": round(hermes_seconds, 3),
            "fallback_seconds": round(fallback_seconds, 3),
            "hermes_error": hermes_error,
            "hermes_reply": hermes_reply,
            "python_reply": fallback_reply,
        }
        trace_path = self._agent.home / "logs" / "aios_soul_trace.json"
        trace_path.parent.mkdir(parents=True, exist_ok=True)
        trace_path.write_text(json.dumps(trace, ensure_ascii=False, indent=2), encoding="utf-8")
