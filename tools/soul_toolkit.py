from typing import List

from camel.toolkits import FunctionTool
from camel.toolkits.base import BaseToolkit
from .soul_store import SoulStore

try:
    from demo.os_view import ui_bridge as _ui_bridge
except ImportError:
    _ui_bridge = None


class SoulToolkit(BaseToolkit):
    def __init__(self):
        super().__init__()
        self.store = SoulStore()

    def get_user_soul(self) -> str:
        """
        Read and return the user's soul profile.

        Returns the personal info from soul.json and experience records from
        experiences.json, combined in Markdown format.
        """
        return self.store.get_user_soul()

    def get_task_status(self) -> str:
        """
        Read and return the full content of the current task execution record.

        Used after workforce completion so Soul Agent can decide whether to
        update the user's soul profile based on what happened.
        """
        result = self.store.get_task_status()
        print(result if result.startswith("task_status.md not found") else "task_status.md found")
        return result

    def update_soul_profile(self, key: str, value: str) -> str:
        """
        Add or update a single field in the user's soul profile (Personal Info).

        If the key already exists, its value is replaced with the new one.
        If the key does not exist, it is added as a new field.

        IMPORTANT — partial list/dict updates:
        If the current value of a key is a list (e.g. a list of preferences or habits)
        and you only want to change one item within it, you must still provide the
        COMPLETE new list including all unchanged items. This tool performs a full
        replacement of the key's value, not a merge.

        Value encoding:
        - For a string value, pass it as a plain string: e.g. value="Suzhou"
        - For a list value, pass it as a JSON array string:
          e.g. value='["pref A", "pref B", "pref C"]'
        - For an object value, pass it as a JSON object string.

        Protected fields: if key is "姓名" or "aios_phone_number", the system will
        prompt the user for explicit confirmation before saving. The update will be
        cancelled if the user declines.

        Args:
            key (str): The field name in soul.json to add or update.
            value (str): The new value. Pass lists and objects as JSON strings.

        Returns:
            str: Result message.
        """
        protected_fields = ["姓名", "aios_phone_number"]
        if key in protected_fields:
            print(f'\n[Soul Agent] Protected field "{key}" is about to be changed:')
            if _ui_bridge and _ui_bridge.get_session_id():
                confirmed = _ui_bridge.request_confirm(
                    f"修改重要字段「{key}」",
                    details=f"新值：{value}",
                )
            else:
                answer = input("Confirm this change? (yes/no): ").strip().lower()
                confirmed = answer in ("yes", "y")
            if not confirmed:
                return f'User declined to modify protected field "{key}". soul.json was not updated.'
            result = self.store.update_soul_profile(key, value, confirm_protected=True)
        else:
            result = self.store.update_soul_profile(key, value)

        print(f'[SoulToolkit] {result}')
        return result

    def append_experience(self, experience_json: str) -> str:
        """
        Append a new experience entry to experiences.json.

        IMPORTANT:
        - Experiences are immutable historical records. This tool only APPENDS
          new entries and can never modify or delete existing ones.
        - A well-formed experience object should include:
            "名称" (str): short title of the experience
            "时间" (str): when it happened (e.g. "July 2025")
            "内容" (str): detailed description of the experience

        Args:
            experience_json (str): JSON string of a single experience object.

        Returns:
            str: Result message.
        """
        result = self.store.append_experience(experience_json)
        print(f"[SoulToolkit] {result}")
        return result

    def get_tools(self) -> List[FunctionTool]:
        return [
            FunctionTool(self.get_user_soul),
            FunctionTool(self.get_task_status),
            FunctionTool(self.update_soul_profile),
            FunctionTool(self.append_experience),
        ]
