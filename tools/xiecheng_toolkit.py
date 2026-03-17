import json
from typing import List, Optional
from camel.toolkits.base import BaseToolkit
from camel.toolkits.function_tool import FunctionTool
from loguru import logger
import os
from pathlib import Path


class XiechengToolkit(BaseToolkit):
    """Toolkit for the AIOS Xiecheng travel app."""

    def __init__(
        self,
        timeout: Optional[float] = None,
    ):
        super().__init__(timeout=timeout)

        base_dir = Path(__file__).resolve().parent.parent
        self.soul_path = os.path.join(base_dir, "mock_data", "xiecheng", "xiecheng_soul.md")
        self.attractions_data_path = os.path.join(base_dir, "mock_data", "xiecheng", "attractions.json")
        self.guides_data_path = os.path.join(base_dir, "mock_data", "xiecheng", "guides.json")
        self.orders_data_path = os.path.join(base_dir, "mock_data", "xiecheng", "orders.json")

    def get_xiecheng_soul(self, query: str) -> str:
        """
        Consults the Xiecheng app for personalization insights
        relevant to the task.

        Xiecheng is a travel platform that supports: querying the user's
        historical travel orders (flights, hotels, attraction tickets, train tickets),
        searching attraction details (opening hours, ticket prices, etc.), and
        retrieving travel guides and destination experience sharing. This tool provides
        advisory personalization input from Xiecheng app (e.g. travel preferences, frequent destinations,
        booking habits) — it does not execute any booking or modification operations.

        Args:
            query (str): Natural language description of the consultation.

        Returns:
            str: A Markdown-formatted advisory response containing Xiecheng-related
                 personalization information that the Xiecheng app agent considers
                 relevant to this task.

        Note:
            - This tool provides advisory input, not search or execution.
            - It does not expose raw booking records or personal travel data.
        """
        print(f"Asking Xiecheng App with the question of {query}")
        path = Path(self.soul_path).resolve()
        with open(path, encoding="utf-8") as soul:
            return soul.read()

    def search_attractions(self) -> str:
        """
        Retrieves all attraction records stored in the Xiecheng app.

        No parameters needed — filter results based on the task yourself.

        Returns:
            str: JSON string containing all attraction records.
        """
        logger.info(f"Fetching xiecheng app attractions")
        data = self._load_mock_data(self.attractions_data_path)
        return json.dumps(data, ensure_ascii=False, indent=2)

    def search_guides(self) -> str:
        """
        Retrieves all travel guide records stored in the Xiecheng app.

        No parameters needed — filter results based on the task yourself.

        Returns:
            str: JSON string containing all travel guide records.
        """
        logger.info(f"Fetching xiecheng app guides")
        data = self._load_mock_data(self.guides_data_path)
        return json.dumps(data, ensure_ascii=False, indent=2)

    def search_orders(self) -> str:
        """
        Retrieves all order records stored in the Xiecheng app.

        No parameters needed — filter results based on the task yourself.

        Returns:
            str: JSON string containing all order records.
        """
        logger.info(f"Fetching xiecheng app orders")
        data = self._load_mock_data(self.orders_data_path)
        return json.dumps(data, ensure_ascii=False, indent=2)

    def _load_mock_data(self, data_path: str) -> List[dict]:
        path = Path(data_path).resolve()
        if not path.exists():
            return []
        try:
            with open(path, encoding="utf-8") as file:
                return json.load(file)
        except json.JSONDecodeError:
            logger.warning(f"Invalid JSON in mock xiecheng data: {path}")
            return []

    def get_tools(self) -> List[FunctionTool]:
        return [
            FunctionTool(self.search_attractions),
            FunctionTool(self.search_guides),
            FunctionTool(self.search_orders),
            FunctionTool(self.get_xiecheng_soul)
        ]

    def get_soul_tools(self) -> List[FunctionTool]:
        return [
            FunctionTool(self.get_xiecheng_soul)
        ]
