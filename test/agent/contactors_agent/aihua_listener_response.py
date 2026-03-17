import asyncio
import json
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

FIXED_REPLY = "今天下午的组会两点开始，在实验室。"

SIMULATED_CONTACT = "艾华老师"

LISTEN_HOST, LISTEN_PORT = "127.0.0.1", "18887"


async def handle_client(reader, writer):
    peer = writer.get_extra_info("peername")
    print(f"\n[艾华老师] Incoming connection from {peer}")

    lines = []
    async for line in reader:
        stripped = line.decode("utf-8").strip()
        if stripped == "END":
            break
        lines.append(stripped)

    writer.close()
    await writer.wait_closed()

    if not lines:
        print("[艾华老师] Empty request, ignoring.")
        return

    try:
        request = json.loads("".join(lines))
    except json.JSONDecodeError:
        print("[艾华老师] Received malformed request, ignoring.")
        return

    content = request.get("content", "")
    sender = request.get("sender", "Unknown")
    response_host = request.get("response_host")
    response_port = request.get("response_port")

    print(f"\n[艾华老师] Message from {sender}:")
    print(f"  {content}")

    confirm = input("\nHandle this task? (yes / no): ").strip().lower()
    if confirm not in ("yes", "y"):
        print("[艾华老师] Task declined. No reply will be sent.")
        return

    print(f"\n[艾华老师] Sending reply: {FIXED_REPLY}")

    try:
        r, w = await asyncio.open_connection(response_host, response_port)
        w.write(json.dumps({"type": "response", "data": FIXED_REPLY}).encode("utf-8"))
        w.write(b"\nEND\n")
        await w.drain()
        w.close()
        await w.wait_closed()
        print("[艾华老师] Reply sent successfully.")
    except Exception as e:
        print(f"[艾华老师] Failed to send reply: {e}")


async def main():
    server = await asyncio.start_server(handle_client, LISTEN_HOST, LISTEN_PORT)
    print(f"[艾华老师] AIOS node started — listening on {LISTEN_HOST}:{LISTEN_PORT}")
    print("Waiting for incoming D2D messages... (Ctrl+C to exit)\n")
    async with server:
        await server.serve_forever()


if __name__ == "__main__":
    asyncio.run(main())
