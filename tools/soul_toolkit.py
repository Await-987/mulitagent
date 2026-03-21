import json
from pathlib import Path
from typing import List

from camel.toolkits import FunctionTool
from camel.toolkits.base import BaseToolkit


class SoulToolkit(BaseToolkit):
    def __init__(self):
        super().__init__()
        base_dir = Path(__file__).resolve().parent.parent
        soul_dir = base_dir / "mock_data" / "soul"
        self.soul_path = soul_dir / "soul.json"
        self.experiences_path = soul_dir / "experiences.json"
        self.task_status_path = base_dir / "demo" / "working_dir" / "task_status.md"

    def get_user_soul(self) -> str:
        """
        Read and return the user's soul profile.

        Returns the personal info from soul.json and experience records from
        experiences.json, combined in Markdown format.
        """
        with open(self.soul_path, encoding="utf-8") as f:
            soul_data = json.load(f)
        with open(self.experiences_path, encoding="utf-8") as f:
            exp_data = json.load(f)

        content = "### User Soul Profile\n\n"
        content += "## Personal Info\n\n"
        content += json.dumps(soul_data, ensure_ascii=False, indent=2)
        content += "\n\n## Experience Records\n\n"
        content += json.dumps(exp_data, ensure_ascii=False, indent=2)
        return content

    def get_task_status(self) -> str:
        """
        Read and return the full content of the current task execution record.

        Used after workforce completion so Soul Agent can decide whether to
        update the user's soul profile based on what happened.
        """
        if not self.task_status_path.exists():
            print(f"task_status.md not found at: {self.task_status_path}")
            return f"task_status.md not found at: {self.task_status_path}"
        with open(self.task_status_path, encoding="utf-8") as f:
            print(f"task_status.md found at: {self.task_status_path}")
            return f.read()

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
        try:
            parsed_value = json.loads(value)
        except (json.JSONDecodeError, ValueError):
            parsed_value = value

        with open(self.soul_path, encoding="utf-8") as f:
            current_soul = json.load(f)

        protected_fields = ["姓名", "aios_phone_number"]
        if key in protected_fields and current_soul.get(key) != parsed_value:
            print(f'\n[Soul Agent] Protected field "{key}" is about to be changed:')
            print(f'  Current : {current_soul.get(key)}')
            print(f'  New     : {parsed_value}')
            confirm = input("Confirm this change? (yes/no): ").strip().lower()
            if confirm not in ("yes", "y"):
                return f'User declined to modify protected field "{key}". soul.json was not updated. The user said {confirm}.'

        is_new_key = key not in current_soul
        current_soul[key] = parsed_value

        with open(self.soul_path, "w", encoding="utf-8") as f:
            json.dump(current_soul, f, ensure_ascii=False, indent=2)

        action = "added" if is_new_key else "updated"
        print(f'[SoulToolkit] soul.json {action}: field "{key}"')
        return f'Field "{key}" has been successfully {action} in soul.json.'

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
        try:
            new_exp = json.loads(experience_json)
        except json.JSONDecodeError as e:
            return f"Error: invalid JSON — {e}"

        with open(self.experiences_path, encoding="utf-8") as f:
            experiences = json.load(f)

        experiences.append(new_exp)

        with open(self.experiences_path, "w", encoding="utf-8") as f:
            json.dump(experiences, f, ensure_ascii=False, indent=2)

        name = new_exp.get("名称", "(unnamed)")
        print(f"[SoulToolkit] New experience appended to experiences.json: {name}")
        return f"New experience '{name}' has been successfully appended to experiences.json."

    def get_tools(self) -> List[FunctionTool]:
        return [
            FunctionTool(self.get_user_soul),
            FunctionTool(self.get_task_status),
            FunctionTool(self.update_soul_profile),
            FunctionTool(self.append_experience),
        ]
