import json
import os
from pathlib import Path
from typing import List
from camel.toolkits.base import BaseToolkit, FunctionTool
from loguru import logger


class NotesRetrievalToolkit(BaseToolkit):
    """
    Toolkit for the AIOS notes app.
    """
    def __init__(self):
        super().__init__()
        base_dir = Path(__file__).resolve().parent.parent
        self.soul_path = os.path.join(base_dir, "mock_data", "notes", "notes_soul.md")
        self.mock_data_path = os.path.join(base_dir, "mock_data", "notes", "notes_data.json")

    def get_notes_soul(self, query: str) -> str:
        """
        Consults the AIOS Notes app for personalization insights relevant to the task.

        The Notes app stores the user's personal notes, ideas, and memos, and supports
        full-library semantic search. This tool provides advisory personalization input
        (e.g. note-taking habits, information organization style, common note types) —
        it does not return raw note contents or perform any operations.

        Args:
            query (str): A natural language description of the consultation.

        Returns:
            str: A Markdown-formatted advisory response containing notes-related
                 personalization information.

        Note:
            - This tool provides advisory input, not search or execution.
            - It does not expose raw note contents.
        """
        logger.info(f"Fetching notes app records for: {query}")
        path = Path(self.soul_path).resolve()
        with open(path, encoding="utf-8") as soul:
            return soul.read()

    def search_my_notes(self) -> str:
        """
        Retrieves all notes records stored in the notes app.

        Returns notes records.
        No parameters needed — filter results based on the task yourself.

        Returns:
            str: JSON string containing all notes records.
        """
        logger.info(f"Fetching notes app notes records")
        data = self._load_mock_data()
        return json.dumps(data, ensure_ascii=False, indent=2)

    def _load_mock_data(self) -> List[dict]:
        path = Path(self.mock_data_path).resolve()
        if not path.exists():
            return []
        try:
            with open(path, encoding="utf-8") as file:
                return json.load(file)
        except json.JSONDecodeError:
            logger.warning(f"Invalid JSON in mock notes data: {path}")
            return []

    def get_tools(self) -> List[FunctionTool]:
        return [
            FunctionTool(self.search_my_notes),
            FunctionTool(self.get_notes_soul)
        ]

    def get_soul_tools(self) -> List[FunctionTool]:
        return [
            FunctionTool(self.get_notes_soul)
        ]
