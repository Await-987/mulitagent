import json
import datetime
from camel.toolkits import BaseToolkit, FunctionTool
from camel.logger import get_logger
from pathlib import Path
import os

logger = get_logger(__name__)


class XiaoHongShuToolkit(BaseToolkit):
    """Toolkit for XiaoHongShu Agent"""

    def __init__(self):
        super().__init__()
        self.base_dir = Path(__file__).resolve().parent.parent
        self.output_dir = Path(self.base_dir) / "mock_data" / "xiaohongshu"
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.soul_path = os.path.join(Path(__file__).resolve().parent.parent, "mock_data", "xiaohongshu", "xiaohongshu_soul.md")

    def get_xiaohongshu_soul(self, query: str) -> str:
        """
        Consults the XiaoHongShu app (third-party) for personalization insights
        relevant to the task.

        XiaoHongShu is a social media platform that supports publishing
        photo-and-text posts (with title, body, and images). This tool provides
        advisory personalization input from XiaoHongShu app (e.g. posting style, content preferences,
        hashtag habits) — it does not publish content or access account data.

        Args:
            query (str): Natural language description of the consultation.

        Returns:
            str: A Markdown-formatted advisory response containing Xiaohongshu-related
                 personalization information.

        Note:
            - This tool provides advisory input, not search or execution.
            - It does not expose raw platform data or account information.
        """
        print(f"Asking Xiaohongshu App with the question of {query}")
        path = Path(self.soul_path).resolve()
        with open(path, encoding="utf-8") as soul:
            return soul.read()


    def publish_xhs_post(self, title: str, text: str, image_paths: list[str]) -> dict:
        """
        Publishes a post to XiaoHongShu.

        Args:
            title (str): Post title. Recommended: short and engaging, 5-20 Chinese characters.
            text (str): Main body content. Recommended: ≥200 characters, platform style with emojis and hashtags.
            image_paths (list[str]): Absolute local file paths to images (JPEG, PNG, etc.).

        Returns:
            dict: {"upload confirmation message": ..., "publication record": ...}
                  {"status": "cancelled", "message": ...} if user declines.
        """
        print(f"\nXiaoHongShu app wants to publish a post:")
        print(f"  Title  : {title}")
        print(f"  Content: {text}")
        print(f"  Images : {image_paths}")
        confirm = input("Publish this post? (yes / no): ").strip().lower()
        if confirm not in ("yes", "y"):
            return {"status": "cancelled", "message": f"User declined to send the message and said: {confirm}"}

        logger.info(f"Publishing Xiaohongshu Post...")
        post = {
            "title": title,
            "text": text,
            "image_paths": image_paths,
            "created_at": datetime.datetime.now().isoformat()
        }
        output_path = self.output_dir / f"xhs_post_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        try:
            with open(output_path, "w", encoding="utf-8") as f:
                json.dump(post, f, ensure_ascii=False, indent=2)
            Published = True
        except Exception as e:
            Published = False
        return {
            "upload confirmation message": f"XiaoHongShu post created: {Published}",
            "publication record": str(post)
        }

    def get_tools(self) -> list[FunctionTool]:
        return [
            FunctionTool(self.publish_xhs_post),
            FunctionTool(self.get_xiaohongshu_soul)
        ]

    def get_soul_tools(self) -> list[FunctionTool]:
        return [
            FunctionTool(self.get_xiaohongshu_soul)
        ]
