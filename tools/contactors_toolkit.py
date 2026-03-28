import asyncio
import concurrent.futures
import json
from pathlib import Path
from typing import List
from camel.toolkits import FunctionTool
from camel.toolkits.base import BaseToolkit
from loguru import logger

from tools.communication_recorder import record_message


class ContactorsToolkit(BaseToolkit):
    """
    Toolkit for the AIOS Contacts app.
    Covers three capabilities:
      - Contact profiles  : phone numbers, relationship context, communication tone
      - Message history   : past conversations with each contact
      - D2D communication : send messages to remote AIOS nodes
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
        to contacts. This tool provides advisory personalization input only — it does
        not execute any actual message.

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

        Returns past message threads with every contact, including contact name,
        phone number, and the full list of messages (each with timestamp, sender,
        and content). No parameters needed — filter results based on the task yourself.

        Returns:
            str: JSON string containing all conversation threads.
        """
        logger.info("Fetching contactors app message history")
        try:
            with open(self.mock_data_path, encoding="utf-8") as f:
                data = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError) as e:
            logger.warning(f"Failed to load message history: {e}")
            return json.dumps([])
        return json.dumps(data, ensure_ascii=False, indent=2)

    def communication_tool(self, target_host: str, target_port: int, msg: str) -> dict:
        """
        Send a D2D message to a contact. The message is delivered one-way — no
        immediate reply is expected. If the contact wishes to respond, their AIOS
        will send a separate message that the listener will receive automatically.

        Asks the user to confirm before sending. Records the sent message to the
        contact's conversation thread in the Contacts app history.

        Args:
            target_host (str): Host portion of the contact's phone_number.
            target_port (int): Port portion of the contact's phone_number.
            msg (str):         Message content to send.

        Returns:
            dict: {"status": "success"}
                  {"status": "cancelled", "message": ...}
                  {"status": "error",     "message": ...}
        """
        print(f"\nContactors app wants to send a message to {target_host}:{target_port}:\n  <{msg}>")
        confirm = input("Send this message? (yes / no): ").strip().lower()
        if confirm not in ("yes", "y"):
            return {"status": "cancelled", "message": f"User declined to send the message and said: {confirm}"}

        try:
            asyncio.get_running_loop()
            with concurrent.futures.ThreadPoolExecutor() as executor:
                fut = executor.submit(
                    asyncio.run, self._send_async(target_host, target_port, msg)
                )
                result = fut.result(timeout=30)
        except RuntimeError:
            result = asyncio.run(self._send_async(target_host, target_port, msg))

        if result.get("status") == "success":
            phone = f"{target_host}:{target_port}"
            contact_name = self._lookup_contact_name(phone) or phone
            record_message(
                contactor_name=contact_name,
                phone_number=phone,
                sender="我",
                content=msg,
                data_path=self.mock_data_path,
            )
            logger.info(f"Contactors app recorded outgoing message to {contact_name} ({phone}).")

        return result

    async def _send_async(self, target_host: str, target_port: int, msg: str) -> dict:
        """Open a TCP connection, send the message payload, and close."""
        try:
            reader, writer = await asyncio.wait_for(
                asyncio.open_connection(target_host, target_port), timeout=30
            )
            payload = {
                "type": "message",
                "content": msg,
                "sender": self.owner_name,
                "sender_phone": f"{self.RESPONSE_HOST}:{self.RESPONSE_PORT}",
            }
            writer.write(json.dumps(payload).encode("utf-8"))
            writer.write(b"\nEND\n")
            await writer.drain()
            writer.close()
            await writer.wait_closed()
            return {"status": "success"}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    def _lookup_contact_name(self, phone_number: str) -> str:
        """Look up a contact's name from profiles or existing threads."""
        try:
            with open(self.profiles_path, encoding="utf-8") as f:
                profiles = json.load(f)
            if isinstance(profiles, list) and profiles:
                for name, data in profiles[0].items():
                    if isinstance(data, dict) and data.get("phone_number") == phone_number:
                        return name
        except Exception:
            pass
        try:
            with open(self.mock_data_path, encoding="utf-8") as f:
                records = json.load(f)
            for thread in records:
                if thread.get("phone_number") == phone_number:
                    return thread.get("contactor", "")
        except Exception:
            pass
        return ""

    def get_tools(self) -> List[FunctionTool]:
        """All Contacts app tools: data retrieval + D2D communication."""
        return [
            FunctionTool(self.get_message_history),
            FunctionTool(self.get_contacts_profile),
            FunctionTool(self.communication_tool),
        ]

    def get_soul_tools(self) -> List[FunctionTool]:
        """Returns the soul-layer tool for querying personalization insights from the Contacts app."""
        return [
            FunctionTool(self.get_contacts_profile),
        ]
