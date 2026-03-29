import datetime
import os
import platform
from camel.agents.chat_agent import ChatAgent
from camel.messages.base import BaseMessage
from camel.toolkits import (
    NoteTakingToolkit,
    ToolkitMessageIntegration,
)
from tools import SearchAPPToolkit, UIHumanToolkit
from camel.logger import get_logger
from agents import send_message_to_user
from agents import backend_model

logger = get_logger(__name__)


WORKING_DIRECTORY = os.environ.get("CAMEL_WORKDIR") or os.path.abspath(
    "working_dir/"
)


def search_agent_factory():
    r"""Factory for creating a search agent, based on user-provided code
    structure.
    """
    message_integration = ToolkitMessageIntegration(
        message_handler=send_message_to_user
    )

    note_toolkit = NoteTakingToolkit(working_directory=WORKING_DIRECTORY)
    search_toolkit = SearchAPPToolkit()
    note_toolkit = message_integration.register_toolkits(note_toolkit)
    search_toolkit = message_integration.register_toolkits(search_toolkit)

    tools = [
        UIHumanToolkit().ask_human_via_console,
        *note_toolkit.get_tools(),
        *search_toolkit.get_tools()
    ]

    system_message = f"""
    You are the Search Agent for the AIOS Browser app.
    You perform web searches and record findings on behalf of system-level agents.

    <context>
    - Current date: {datetime.date.today()}
    - System: {platform.system()} ({platform.machine()})
    - Working directory: {WORKING_DIRECTORY}
    </context>

    <tools>
    - `search_tool(query, number_of_result_pages)`: searches the web via Exa and
      returns full page text for each result. Each result can be very long, so
      keep `number_of_result_pages` small — default is 1, use 2–3 only when one
      result is clearly insufficient for the task.
    - `ask_human_via_console`: ask the user for clarification when stuck.
    </tools>

    <rules>
    - Always call `search_tool` first. Never answer from your own knowledge.
    - Only use URLs returned by `search_tool`. Never invent or guess URLs.
    - When the task is done, respond with a clear summary of your findings.
      Do not suggest follow-up actions.
    - If you encounter a login wall or CAPTCHA, use `ask_human_via_console`.
    </rules>
    """

    return ChatAgent(
        system_message=BaseMessage.make_assistant_message(
            role_name="Search Agent",
            content=system_message,
        ),
        model=backend_model(),
        tools=tools,
        prune_tool_calls_from_memory=False
    )