import json
from datetime import datetime, timezone
from pathlib import Path

from loguru import logger


def _default_data_path() -> Path:
    base = Path(__file__).resolve().parent.parent
    return base / "mock_data" / "contactors" / "contactors_data.json"


def record_message(
    contactor_name: str,
    phone_number: str,
    sender: str,
    content: str,
    data_path: Path = None,
    timestamp: str = None,
) -> None:
    """
    Append a single message to the conversation thread for a contact.

    If no thread exists for the given phone_number, one is created.
    The thread stores messages in chronological order, each with a timestamp,
    sender name, and content — mirroring a real SMS conversation view.

    Args:
        contactor_name: Display name of the contact (e.g. "妈妈", "艾华老师").
        phone_number:   Contact's AIOS address in "host:port" format.
        sender:         Who sent this message — use the contact's name for
                        incoming messages, or "我" for the user's own messages.
        content:        The message text.
        data_path:      Path to contactors_data.json (defaults to main user data).
        timestamp:      ISO 8601 UTC string (e.g. "2025-10-04T10:32:17Z").
                        Defaults to the current UTC time.
    """
    if data_path is None:
        data_path = _default_data_path()
    if timestamp is None:
        timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    try:
        with open(data_path, encoding="utf-8") as f:
            records = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        records = []

    # Find existing thread for this phone number
    thread = None
    for r in records:
        if r.get("phone_number") == phone_number:
            thread = r
            break

    if thread is None:
        thread = {
            "contactor": contactor_name,
            "phone_number": phone_number,
            "messages": [],
        }
        records.append(thread)

    # Update display name if we previously only had the phone number
    if contactor_name and thread.get("contactor") == phone_number:
        thread["contactor"] = contactor_name

    thread["messages"].append({
        "timestamp": timestamp,
        "sender": sender,
        "content": content,
    })

    with open(data_path, "w", encoding="utf-8") as f:
        json.dump(records, f, ensure_ascii=False, indent=2)

    logger.info(
        f"[CommunicationRecorder] Recorded message from '{sender}' "
        f"in thread with {contactor_name} ({phone_number})."
    )
