import asyncio
import concurrent.futures
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import List
from camel.toolkits import FunctionTool
from camel.toolkits.base import BaseToolkit
from loguru import logger


class ContactorsToolkit(BaseToolkit):
    """
    Toolkit for the AIOS Contacts app.
    Covers three capabilities:
      - Contact profiles  : phone numbers, relationship context, communication tone
      - Message history   : past conversations with each contact
      - D2D communication : send messages to / reply to remote AIOS nodes
    """

    def __init__(self):
        super().__init__()
        base_dir = Path(__file__).resolve().parent.parent
        self.profiles_path = base_dir / "mock_data" / "contactors" / "contactors_profiles.json"
        self.mock_data_path = base_dir / "mock_data" / "contactors" / "contactors_data.json"
        self._soul_path = base_dir / "mock_data" / "soul" / "soul.json"

        owner = self._get_owner_info()
        self.owner_name: str = owner.get("姓名", "Unknown")
        aios_phone: str = owner.get("aios_phone_number", "127.0.0.1:18889")
        host, port_str = aios_phone.rsplit(":", 1)
        self.RESPONSE_HOST: str = host
        self.RESPONSE_PORT: int = int(port_str)

    def _get_owner_info(self) -> dict:
        """Load the device owner's basic info from soul.json."""
        try:
            with open(self._soul_path, encoding="utf-8") as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError) as e:
            logger.warning(f"Could not load soul.json: {e}. Using defaults.")
            return {"姓名": "Unknown", "aios_phone_number": "127.0.0.1:18889"}

    def get_contacts_profile(self, query: str) -> str:
        """
        Consults the AIOS Contacts app for personalization insights relevant to the task.

        The Contacts app manages the user's social circle and supports: contact profile
        lookup (phone number, relationship background, current status), recommended
        communication tone guidance, browsing message history, and sending D2D messages
        or making calls to contacts. This tool provides advisory personalization input
        only — it does not execute any actual call or message.

        Args:
            query (str): Natural language description of the consultation, including
                         the current task context and what information is needed.

        Returns:
            str: Markdown-formatted contact profile sheet with phone numbers and
                 communication tone guidance.
        """
        logger.info(f"Fetching contactors app profiles for: {query}")
        try:
            with open(self.profiles_path, encoding="utf-8") as f:
                data = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError) as e:
            logger.warning(f"Failed to load contactors app profiles: {e}")
            return json.dumps([])
        return json.dumps(data, ensure_ascii=False, indent=2)

    def get_message_history(self) -> str:
        """
        Retrieves all conversation history stored in the Contacts app.

        Returns past message records with every contact, including contact name,
        phone number, and full conversation content.
        No parameters needed — filter results based on the task yourself.

        Returns:
            str: JSON string containing all conversation records.
        """
        logger.info(f"Fetching contactors app messages history")
        try:
            with open(self.mock_data_path, encoding="utf-8") as f:
                data = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError) as e:
            logger.warning(f"Failed to load message history: {e}")
            return json.dumps([])
        return json.dumps(data, ensure_ascii=False, indent=2)

    def ask_tool(self, target_host: str, target_port: int, msg: str) -> dict:
        """
        Send a D2D message to a remote AIOS contact and return their reply.

        Asks the user to confirm before sending. Logs the full exchange to
        the Contacts app message history after a successful call.

        The message is sent with the user's identity attached so the recipient
        knows who is reaching out.

        Args:
            target_host (str): Host portion of the contact's phone_number.
            target_port (int): Port portion of the contact's phone_number.
            msg (str): Message content to send.

        Returns:
            dict: {"status": "success", "reply": <reply text>}
                  {"status": "cancelled", "message": ...}
                  {"status": "error",     "message": ...}
        """
        print(f"\nContactors app wants to ask the phone number {target_host}:{target_port} with question of <{msg}>.")
        confirm = input("Send this message? (yes / no): ").strip().lower()
        if confirm not in ("yes", "y"):
            return {"status": "cancelled", "message": f"User declined to send the message and said: {confirm}"}

        try:
            asyncio.get_running_loop()
            with concurrent.futures.ThreadPoolExecutor() as executor:
                fut = executor.submit(
                    asyncio.run, self._ask_async(target_host, target_port, msg)
                )
                result = fut.result(timeout=450)
        except RuntimeError:
            result = asyncio.run(self._ask_async(target_host, target_port, msg))

        if result.get("status") == "success":
            reply_text = result.get("reply", "")
            self._log_conversation(
                phone_number=f"{target_host}:{target_port}",
                outgoing_msg=msg,
                incoming_msg=reply_text,
                direction="outgoing",
            )
        return result

    async def _ask_async(self, target_host: str, target_port: int, msg: str) -> dict:
        # Windows Proactor raises ConnectionResetError in _call_connection_lost when
        # the remote side closes first. Suppress it with a temporary exception handler.
        loop = asyncio.get_running_loop()
        old_handler = loop.get_exception_handler()

        def _suppress_connection_reset(loop, context):
            if isinstance(context.get("exception"), ConnectionResetError):
                return
            (old_handler or loop.default_exception_handler)(loop, context)

        loop.set_exception_handler(_suppress_connection_reset)

        reply_future: asyncio.Future = asyncio.Future()

        async def _collect_reply(reader, writer):
            try:
                lines = []
                async for line in reader:
                    stripped = line.decode("utf-8").strip()
                    if stripped == "END":
                        break
                    lines.append(stripped)
                if lines:
                    response_obj = json.loads("".join(lines))
                    reply_text = (
                        response_obj.get("data", "")
                        if isinstance(response_obj, dict)
                        else str(response_obj)
                    )
                    reply_future.set_result({"status": "success", "reply": reply_text})
                else:
                    reply_future.set_result({"status": "error", "message": "Empty response"})
            except Exception as e:
                reply_future.set_result({"status": "error", "message": str(e)})
            finally:
                writer.close()
                await writer.wait_closed()

        reply_server = await asyncio.start_server(
            _collect_reply, self.RESPONSE_HOST, self.RESPONSE_PORT
        )
        reader, writer = await asyncio.wait_for(
            asyncio.open_connection(target_host, target_port), timeout=30
        )
        payload = {
            "type": "request",
            "content": msg,
            "sender": self.owner_name,
            "response_host": self.RESPONSE_HOST,
            "response_port": self.RESPONSE_PORT,
        }
        writer.write(json.dumps(payload).encode("utf-8"))
        writer.write(b"\nEND\n")
        await writer.drain()

        try:
            result = await asyncio.wait_for(reply_future, timeout=400)
            writer.close()
            await writer.wait_closed()
            reply_server.close()
            await reply_server.wait_closed()
            return result
        finally:
            loop.set_exception_handler(old_handler)

    def tell_tool(
        self,
        target_host: str,
        target_port: int,
        msg: str,
        incoming_msg: str = "",
        caller_name: str = "",
        caller_phone: str = "",
    ) -> dict:
        """
        Send a one-way D2D message to a contact — no reply expected.

        Use this to inform, notify, or reply to a contact without waiting for
        a response. Asks the user to confirm before sending. Logs the exchange
        to message history.

        Args:
            target_host (str)  : host portion of the contact's phone_number,
                                 or response_host from an incoming request.
            target_port (int)  : port portion of the contact's phone_number,
                                 or response_port from an incoming request.
            msg (str)          : Message content to send.
            incoming_msg (str) : The original message received (for logging).
            caller_name (str)  : Name of the contact (for logging).
            caller_phone (str) : phone_number of the contact in "host:port" format (for logging).

        Returns:
            dict: {"status": "success"}
                  {"status": "cancelled", "message": ...}
                  {"status": "error",     "message": ...}
        """
        print(f"\nContactors app wants to send a one-way message to {target_host}:{target_port}: <{msg}>.")
        confirm = input("Send this message? (yes / no): ").strip().lower()
        if confirm not in ("yes", "y"):
            return {"status": "cancelled", "message": f"User declined to send the message and said: {confirm}"}

        try:
            asyncio.get_running_loop()
            with concurrent.futures.ThreadPoolExecutor() as executor:
                fut = executor.submit(
                    asyncio.run, self._reply_async(target_host, target_port, msg)
                )
                result = fut.result(timeout=30)
        except RuntimeError:
            result = asyncio.run(self._reply_async(target_host, target_port, msg))

        if result.get("status") == "success" and (incoming_msg or caller_name):
            self._log_conversation(
                phone_number=caller_phone or f"{target_host}:{target_port}",
                outgoing_msg=msg,
                incoming_msg=incoming_msg,
                direction="incoming",
                caller_name=caller_name,
            )
        return result

    async def _reply_async(self, target_host: str, target_port: int, msg: str) -> dict:
        try:
            reader, writer = await asyncio.wait_for(
                asyncio.open_connection(target_host, target_port), timeout=30
            )
            writer.write(json.dumps({"type": "response", "data": msg}).encode("utf-8"))
            writer.write(b"\nEND\n")
            await writer.drain()
            writer.close()
            await writer.wait_closed()
            return {"status": "success"}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    def _lookup_contact_name(self, phone_number: str) -> str:
        """Look up a contact's name from existing message history by phone_number."""
        try:
            with open(self.mock_data_path, encoding="utf-8") as f:
                records = json.load(f)
            for record in records:
                content = record.get("content", {})
                if content.get("phone_number") == phone_number:
                    return content.get("contactor", "")
        except Exception:
            pass
        return ""

    def _log_conversation(
        self,
        phone_number: str,
        outgoing_msg: str,
        incoming_msg: str,
        direction: str = "outgoing",
        caller_name: str = "",
    ) -> None:
        """Append a conversation record to contactors_data.json."""
        contactor = self._lookup_contact_name(phone_number) or caller_name or phone_number

        if direction == "outgoing":
            data_text = f"用户: {outgoing_msg}\n{contactor}: {incoming_msg}"
        else:
            data_text = f"{contactor}: {incoming_msg}\n用户: {outgoing_msg}"

        entry = {
            "title": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "content": {
                "contactor": contactor,
                "phone_number": phone_number,
                "data": data_text,
            },
        }

        try:
            with open(self.mock_data_path, encoding="utf-8") as f:
                records = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            records = []

        records.append(entry)

        with open(self.mock_data_path, "w", encoding="utf-8") as f:
            json.dump(records, f, ensure_ascii=False, indent=2)

        logger.info(f"Contactors app noted the conversation with {contactor} ({phone_number}) in the contact history.")

    def get_tools(self) -> List[FunctionTool]:
        """All Contacts app tools: data retrieval + D2D communication."""
        return [
            FunctionTool(self.get_message_history),
            FunctionTool(self.get_contacts_profile),
            FunctionTool(self.ask_tool),
            FunctionTool(self.tell_tool),
        ]

    def get_soul_tools(self) -> List[FunctionTool]:
        """Returns the soul-layer tool for querying personalization insights from the Contacts app."""
        return [
            FunctionTool(self.get_contacts_profile),
        ]
