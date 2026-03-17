import asyncio
import json
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

SIMULATED_CONTACT = "刘星"

LISTEN_HOST, LISTEN_PORT = "127.0.0.1", "18883"


async def handle_client(reader, writer):
    peer = writer.get_extra_info("peername")
    print(f"\n[刘星] Incoming connection from {peer}")

    lines = []
    async for line in reader:
        stripped = line.decode("utf-8").strip()
        if stripped == "END":
            break
        lines.append(stripped)

    writer.close()
    await writer.wait_closed()

    if not lines:
        print("[刘星] Empty message, ignoring.")
        return

    try:
        message = json.loads("".join(lines))
    except json.JSONDecodeError:
        print("[刘星] Received malformed message, ignoring.")
        return

    msg_type = message.get("type", "")
    if msg_type == "response":
        reply_text = message.get("data", "")
        print(f"\n[刘星] Received message from 张小宇:")
        print(f"  {reply_text}")
    elif msg_type == "request":
        content = message.get("content", "")
        sender = message.get("sender", "Unknown")
        print(f"\n[刘星] WARNING: Received a request (ask_tool) from {sender}, expected a one-way message.")
        print(f"  Content: {content}")
    else:
        print(f"\n[刘星] Received unknown message type '{msg_type}': {message}")


async def main():
    server = await asyncio.start_server(handle_client, LISTEN_HOST, LISTEN_PORT)
    print(f"[刘星] AIOS node started — listening on {LISTEN_HOST}:{LISTEN_PORT}")
    print("Waiting for reply from 张小宇... (Ctrl+C to exit)\n")
    async with server:
        await server.serve_forever()


if __name__ == "__main__":
    asyncio.run(main())
