from __future__ import annotations
import json
from typing import List, Optional
from PIL import Image
from camel.agents import ChatAgent
from camel.messages import BaseMessage
from camel.toolkits import FunctionTool
from camel.toolkits.base import BaseToolkit
from loguru import logger
import os
from pathlib import Path


class PhotosToolkit(BaseToolkit):
    """Toolkit for the AIOS Photos app."""

    def __init__(
        self,
        timeout: Optional[float] = None,
    ):
        super().__init__(timeout=timeout)
        base_dir = Path(__file__).resolve().parent.parent
        self.soul_path = os.path.join(base_dir, "mock_data", "photos", "photos_soul.md")
        self.mock_data_path = os.path.join(base_dir, "mock_data", "photos", "photos_data.json")

    def get_photos_soul(self, query: str) -> str:
        """
        Consults the AIOS Photos app for personalization insights relevant to the task.

        The Photos app manages all photos on the user's device and supports: semantic
        photo search and detailed visual content analysis. But Photos app does not support modify photos.
        This tool provides advisory personalization input (e.g. shooting habits, visual preferences, photo style
        tendencies) — it does not return raw photo files or perform any operations.

        Args:
            query (str): A natural language description of the consultation.

        Returns:
            str: Markdown-formatted personalization insights from the Photos app.

        Note:
            - This tool provides advisory input, not search or execution.
            - It does not expose raw photo files or image data.
        """
        print(f"Asking Photos App with the question of {query}")
        path = Path(self.soul_path).resolve()
        with open(path, encoding="utf-8") as soul:
            return soul.read()

    def _load_image(self, image_path: str) -> Image.Image:
        try:
            return Image.open(image_path)
        except Exception as e:
            logger.error(f"Image loading failed: {e}")
            raise ValueError(f"Invalid image file: {e}")

    def _make_vision_agent(self) -> ChatAgent:
        from agents.backend_model import backend_model_image
        system_msg = BaseMessage.make_assistant_message(
            role_name="Senior Computer Vision Analyst",
            content=(
                "You are an image analysis expert. "
                "Provide a detailed description of the image, "
                "including any visible objects, scenes, and text if present."
            ),
        )
        return ChatAgent(system_message=system_msg, model=backend_model_image())

    def get_image_information(self, image_path: str, user_message: str) -> str:
        """
        Analyzes a specific image and returns a detailed description of its visual content.

        Args:
            image_path (str): Absolute local file path to the image. Typically obtained
                              from `search_photos` results. Supports JPEG, PNG, etc.
            user_message (str): Specific question or analysis requirement for the image.

        Returns:
            str: Natural language description of the image content, or an error message
                 if the image cannot be loaded or analyzed.
        """
        try:
            image = self._load_image(image_path)
            logger.info(f"Analyzing image: {image_path} with the question of {user_message}")
            user_msg = BaseMessage.make_user_message(
                role_name="User",
                content=user_message,
                image_list=[image],
            )
            agent = self._make_vision_agent()
            response = agent.step(user_msg)
            logger.info(f"Image analyzed result: {response.msgs[0].content}")
            return response.msgs[0].content
        except ValueError as e:
            logger.error(f"Image loading error: {e}")
            return f"Image error: {e!s}"
        except Exception as e:
            logger.error(f"Unexpected error: {e}")
            return f"Analysis failed: {e!s}"

    def search_photos(self) -> str:
        """
        Retrieves all photos stored in the Photos app.

        No parameters needed — filter results based on the task yourself.

        Returns:
            str: JSON string containing all photos information.
        """
        logger.info(f"Fetching photos app photos")
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
            logger.warning(f"Invalid JSON in mock photos data: {path}")
            return []

    def get_tools(self) -> List[FunctionTool]:
        return [
            FunctionTool(self.get_image_information),
            FunctionTool(self.search_photos),
            FunctionTool(self.get_photos_soul)
        ]

    def get_soul_tools(self) -> List[FunctionTool]:
        return [
            FunctionTool(self.get_photos_soul)
        ]
