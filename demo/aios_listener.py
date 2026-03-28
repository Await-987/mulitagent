import asyncio
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from aios_demo import main as aios_main
from tools.communication_recorder import record_message


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

    else:
        print(f"[AIOS Listener] Unknown message type {msg_type!r} — ignoring.")
        return

    print("[AIOS Listener] Routing to AIOS system...")
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
