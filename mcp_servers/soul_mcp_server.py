"""
AIOS Soul MCP Server — stdio transport.

Exposes Soul data operations as structured MCP tools so Hermes can call them
directly (no bash command construction needed).

Run with the same Python environment used by AIOS:
    python mcp_servers/soul_mcp_server.py

Hermes registers this as mcp_servers.soul in config.yaml, so tool names
become: soul__get_user_soul, soul__ask_human, etc.
"""
from __future__ import annotations

import asyncio
import importlib.util
import json
import logging
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

logging.basicConfig(level=logging.INFO, stream=sys.stderr)
logger = logging.getLogger("aios_soul_mcp")

BASE_DIR = Path(__file__).resolve().parent.parent


def _load_soul_store():
    module_path = BASE_DIR / "tools" / "soul_store.py"
    spec = importlib.util.spec_from_file_location("_soul_store", module_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot load SoulStore from {module_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.SoulStore(str(BASE_DIR))


_store = _load_soul_store()


def _ask_human_ipc(question: str) -> str:
    """POST to OS View server IPC endpoint; falls back to default reply."""
    sid = os.environ.get("AIOS_CURRENT_SESSION_ID", "").strip()
    port = os.environ.get("AIOS_OSVIEW_PORT", "5001").strip() or "5001"
    if sid:
        url = f"http://127.0.0.1:{port}/api/_ipc/ask_user"
        payload = json.dumps({"session_id": sid, "question": question}).encode()
        req = urllib.request.Request(
            url, data=payload,
            headers={"Content-Type": "application/json"}, method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=320) as resp:
                data = json.loads(resp.read().decode() or "{}")
            return str(data.get("reply", "") or "")
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            logger.warning("OS View IPC unavailable (%s); falling back", exc)
    return os.environ.get("AIOS_SOUL_DEFAULT_REPLY", "你自己发挥").strip()


# --- MCP Server setup ---
from mcp.server import Server
from mcp.server.stdio import stdio_server
import mcp.types as types

server = Server("soul")


@server.list_tools()
async def list_tools() -> list[types.Tool]:
    return [
        types.Tool(
            name="get_user_soul",
            description="读取用户完整画像（个人信息 + 经历记录）",
            inputSchema={"type": "object", "properties": {}, "required": []},
        ),
        types.Tool(
            name="get_task_status",
            description="读取当前任务执行状态（task_status.md）",
            inputSchema={"type": "object", "properties": {}, "required": []},
        ),
        types.Tool(
            name="update_soul_profile",
            description="更新用户画像的某个字段。对于列表字段，传完整列表（含未变项）。",
            inputSchema={
                "type": "object",
                "properties": {
                    "key": {"type": "string", "description": "要更新的字段名"},
                    "value": {"type": "string", "description": "新值（JSON 或纯文本）"},
                    "confirm_protected": {
                        "type": "boolean", "default": False,
                        "description": "是否确认修改受保护字段（姓名/电话）",
                    },
                },
                "required": ["key", "value"],
            },
        ),
        types.Tool(
            name="append_experience",
            description="追加一条用户经历记录。传 JSON 字符串。",
            inputSchema={
                "type": "object",
                "properties": {
                    "experience_json": {
                        "type": "string",
                        "description": "经历JSON {\"名称\":\"...\",\"时间\":\"...\",\"内容\":\"...\"}",
                    },
                },
                "required": ["experience_json"],
            },
        ),
        types.Tool(
            name="ask_human",
            description="向用户提问并等待回答。会在小艺面板弹出聊天气泡。同一任务最多用1-2次。",
            inputSchema={
                "type": "object",
                "properties": {
                    "question": {"type": "string", "description": "要问用户的问题"},
                },
                "required": ["question"],
            },
        ),
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[types.TextContent]:
    try:
        if name == "get_user_soul":
            result = _store.get_user_soul()
        elif name == "get_task_status":
            result = _store.get_task_status()
        elif name == "update_soul_profile":
            result = _store.update_soul_profile(
                arguments["key"],
                arguments["value"],
                confirm_protected=arguments.get("confirm_protected", False),
            )
        elif name == "append_experience":
            result = _store.append_experience(arguments["experience_json"])
        elif name == "ask_human":
            result = _ask_human_ipc(arguments["question"])
        else:
            result = f"Unknown tool: {name}"
    except Exception as exc:
        result = f"Error: {exc}"
    return [types.TextContent(type="text", text=str(result))]


async def main():
    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream, write_stream, server.create_initialization_options()
        )


if __name__ == "__main__":
    asyncio.run(main())
