import os
from camel.agents.chat_agent import ChatAgent
from camel.logger import get_logger
from camel.messages.base import BaseMessage
from camel.toolkits import (
    HumanToolkit,
    NoteTakingToolkit,
    ToolkitMessageIntegration,
)
from tools import XiaoHongShuToolkit
from agents import backend_model
from agents import send_message_to_user


logger = get_logger(__name__)

WORKING_DIRECTORY = os.environ.get("CAMEL_WORKDIR") or os.path.abspath(
    "working_dir/"
)

def xiaohongshu_agent_factory():
    message_integration = ToolkitMessageIntegration(
        message_handler=send_message_to_user
    )
    note_toolkit = NoteTakingToolkit(working_directory=WORKING_DIRECTORY)
    xhs_toolkit = XiaoHongShuToolkit()
    xhs_toolkit = message_integration.register_toolkits(xhs_toolkit)

    tools = [
        *xhs_toolkit.get_tools(),
        HumanToolkit().ask_human_via_console,
        *note_toolkit.get_tools(),
    ]

    system_message = """
        You are the XiaoHongShu Agent for the AIOS XiaoHongShu app.
        You publish posts to XiaoHongShu for the user.

        <tools>
        - `get_xiaohongshu_soul(query)`: returns personalization insights about the user's XiaoHongShu content style and preferences.
          Pass a natural language description of the consultation as query.
          Use this when you need to adapt the post to match the user's platform style.
        - `publish_xhs_post(title, text, image_paths)`: publishes a post to XiaoHongShu.
          - title (str): short and engaging, recommended 5-20 Chinese characters.
          - text (str): main body content, recommended ≥200 characters, platform style with emojis and hashtags.
          - image_paths (list[str]): absolute local file paths to images. Must come from the Photos Agent — never fabricate paths.
        </tools>

        <rules>
        Choosing the right tool:
            - The task requires personalization insights (e.g. user habits, style, preferences) → call `get_xiaohongshu_soul` first.
            - The task requires publishing a post → call `publish_xhs_post`.
              Note: You can only post on Xiaohongshu through `publish_xhs_post`.
        - Never fabricate image paths or personalization insights. All responses must be based strictly on tool results.
        - After the task is done, report the outcome only. Do not suggest follow-up actions.
        </rules>
        """

    return ChatAgent(
        system_message=BaseMessage.make_assistant_message(
            role_name="XiaoHongShu Agent",
            content=system_message,
        ),
        model=backend_model(),
        tools=tools,
    )