from __future__ import annotations

import json
from pathlib import Path
from typing import Any


class SoulStore:
    """File-backed Soul profile operations without any agent framework dependency."""

    def __init__(self, base_dir: str | Path | None = None) -> None:
        self.base_dir = Path(base_dir).resolve() if base_dir else Path(__file__).resolve().parent.parent
        soul_dir = self.base_dir / "mock_data" / "soul"
        self.soul_path = soul_dir / "soul.json"
        self.experiences_path = soul_dir / "experiences.json"
        self.task_status_path = self.base_dir / "demo" / "working_dir" / "task_status.md"

    def get_user_soul(self) -> str:
        with self.soul_path.open(encoding="utf-8") as f:
            soul_data = json.load(f)
        with self.experiences_path.open(encoding="utf-8") as f:
            exp_data = json.load(f)

        content = "### User Soul Profile\n\n"
        content += "## Personal Info\n\n"
        content += json.dumps(soul_data, ensure_ascii=False, indent=2)
        content += "\n\n## Experience Records\n\n"
        content += json.dumps(exp_data, ensure_ascii=False, indent=2)
        return content

    def get_task_status(self) -> str:
        if not self.task_status_path.exists():
            return f"task_status.md not found at: {self.task_status_path}"
        return self.task_status_path.read_text(encoding="utf-8")

    def update_soul_profile(
        self,
        key: str,
        value: str,
        *,
        confirm_protected: bool = False,
    ) -> str:
        parsed_value: Any
        try:
            parsed_value = json.loads(value)
        except (json.JSONDecodeError, ValueError):
            parsed_value = value

        with self.soul_path.open(encoding="utf-8") as f:
            current_soul = json.load(f)

        protected_fields = {"姓名", "aios_phone_number"}
        if key in protected_fields and current_soul.get(key) != parsed_value and not confirm_protected:
            return f'Protected field "{key}" requires explicit confirmation. soul.json was not updated.'

        is_new_key = key not in current_soul
        current_soul[key] = parsed_value

        with self.soul_path.open("w", encoding="utf-8") as f:
            json.dump(current_soul, f, ensure_ascii=False, indent=2)

        action = "added" if is_new_key else "updated"
        return f'Field "{key}" has been successfully {action} in soul.json.'

    def append_experience(self, experience_json: str) -> str:
        try:
            new_exp = json.loads(experience_json)
        except json.JSONDecodeError as exc:
            return f"Error: invalid JSON - {exc}"

        with self.experiences_path.open(encoding="utf-8") as f:
            experiences = json.load(f)

        experiences.append(new_exp)

        with self.experiences_path.open("w", encoding="utf-8") as f:
            json.dump(experiences, f, ensure_ascii=False, indent=2)

        name = new_exp.get("名称", "(unnamed)")
        return f"New experience '{name}' has been successfully appended to experiences.json."
