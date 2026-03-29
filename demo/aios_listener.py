import asyncio
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from aios_demo import main as aios_main
from tools.communication_recorder import record_message

_ORCA_PORT  = int(os.environ.get("ORCA_PORT", 5001))
_SERVER_URL = os.environ.get("ORCA_SERVER_URL", f"http://127.0.0.1:{_ORCA_PORT}")


def _try_queue_pending_d2d(
    task: str,
    display_sender: str = "",
    display_content: str = "",
) -> bool:
    """
    POST the incoming D2D message to the OS View server as a pending task.
    The user will see a confirm dialog and decide whether to let 小艺 handle it.
    Returns True if the server accepted it (so local execution can be skipped).
    """
    try:
        import urllib.request, urllib.error
        payload = json.dumps({
            "task": task,
            "display_sender": display_sender,
            "display_content": display_content,
        }).encode()
        req = urllib.request.Request(
            f"{_SERVER_URL}/api/d2d/pending",
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=5) as resp:
            return resp.status == 200
    except Exception:
        return False


def _load_listen_address() -> tuple[str, int]:
    soul_path = (
        Path(__file__).resolve().parent.parent / "mock_data" / "soul" / "soul.json"
    )
    with open(soul_path, encoding="utf-8") as f:
        soul = json.load(f)
    aios_phone: str = soul.get("aios_phone_number")
    host, port_str = aios_phone.rsplit(":", 1)
    return host, int(port_str)


async def handle_incoming(
    reader: asyncio.StreamReader, writer: asyncio.StreamWriter
) -> None:
    peer = writer.get_extra_info("peername")
    print(f"\n[AIOS Listener] Incoming connection from {peer}")

    lines: list[str] = []
    async for line in reader:
        stripped = line.decode("utf-8").strip()
        if stripped == "END":
            break
        lines.append(stripped)

    writer.close()
    await writer.wait_closed()

    if not lines:
        print("[AIOS Listener] Empty message — ignoring.")
        return

    try:
        message: dict = json.loads("".join(lines))
    except json.JSONDecodeError:
        print("[AIOS Listener] Malformed JSON — ignoring.")
        return

    msg_type: str = message.get("type", "")

    if msg_type in ("message", "request"):
        # Standard incoming message (new "message" type or legacy "request" type)
        sender = message.get("sender", "Unknown")
        content = message.get("content", "")
        # Resolve sender phone: new format uses "sender_phone", legacy uses response_host:response_port
        sender_phone = message.get("sender_phone", "")
        if not sender_phone:
            rh = message.get("response_host", "")
            rp = message.get("response_port", "")
            if rh and rp:
                sender_phone = f"{rh}:{rp}"
        print(f"[AIOS Listener] Message from {sender!r}: {content}")

        # Record incoming message to conversation history immediately
        if sender_phone:
            record_message(
                contactor_name=sender,
                phone_number=sender_phone,
                sender=sender,
                content=content,
            )

        task = (
            f'Received an incoming D2D message from contact "{sender}": "{content}". '
            f'The sender "{sender}" has phone number {sender_phone}. '
            f"Decide whether and how to respond based on the content and context."
        )
        display_sender, display_content = sender, content

    elif msg_type == "response":
        # Legacy one-way notification format
        data = message.get("data", "")
        sender = message.get("sender", "Unknown")
        sender_phone = message.get("sender_phone", "")
        print(f"[AIOS Listener] One-way notification from {sender!r}: {data}")

        if sender_phone:
            record_message(
                contactor_name=sender,
                phone_number=sender_phone,
                sender=sender,
                content=data,
            )

        task = (
            f'Received a one-way D2D notification from "{sender}": "{data}". '
            f"No reply is expected. Take any appropriate action."
        )
        display_sender, display_content = sender, data

    else:
        print(f"[AIOS Listener] Unknown message type {msg_type!r} — ignoring.")
        return

    print("[AIOS Listener] Routing to AIOS system...")
    # Try to queue the D2D message on the OS View server for user confirmation.
    # The user will see a confirm dialog and decide whether to let 小艺 handle it.
    # Fall back to direct local execution if the server is not reachable.
    if not _try_queue_pending_d2d(task, display_sender, display_content):
        await aios_main(task)


async def main() -> None:
    host, port = _load_listen_address()
    server = await asyncio.start_server(handle_incoming, host, port)
    print(f"[AIOS Listener] Listening on {host}:{port}  (source: soul.json)")
    print("Waiting for incoming D2D messages... (Ctrl+C to stop)\n")
    async with server:
        await server.serve_forever()


if __name__ == "__main__":
    asyncio.run(main())
