import os
from datetime import date
from camel.agents.chat_agent import ChatAgent
from camel.messages.base import BaseMessage
from camel.toolkits import (
    HumanToolkit,
    NoteTakingToolkit,
    ToolkitMessageIntegration,
)
from tools import XiechengToolkit
from agents import send_message_to_user
from agents import backend_model

WORKING_DIRECTORY = os.environ.get("CAMEL_WORKDIR") or os.path.abspath(
    "working_dir/"
)


def xiecheng_agent_factory():
    message_integration = ToolkitMessageIntegration(
        message_handler=send_message_to_user
    )
    note_toolkit = NoteTakingToolkit(working_directory=WORKING_DIRECTORY)
    xiecheng_toolkit = XiechengToolkit()
    xiecheng_toolkit = message_integration.register_toolkits(xiecheng_toolkit)

    tools = [
        *xiecheng_toolkit.get_tools(),
        HumanToolkit().ask_human_via_console,
        *note_toolkit.get_tools(),
    ]

    system_message = f"""
    You are the Xiecheng Agent for the AIOS Xiecheng travel app.
    You look up attractions, travel guides, and order records for the user.
    The current date is {date.today()}.

    <tools>
    - `search_attractions`: returns all attraction records stored in the Xiecheng app (no parameters).
      Call this when the task involves finding or recommending attractions.
    - `search_guides`: returns all travel guide records stored in the Xiecheng app (no parameters).
      Call this when the task involves travel planning or itinerary guidance.
    - `search_orders`: returns all order records stored in the Xiecheng app (no parameters).
      Call this when the task involves checking past bookings or travel history.
    - `get_xiecheng_soul(query)`: returns personalization insights about the user's travel preferences and habits.
      Pass a natural language description of the consultation as query.
      Use this when a system agent needs to understand the user's travel style, not raw records.
    </tools>

    <rules>
    - Choosing the right tool: match the task intent to the appropriate tool above. Chain multiple tools when the task requires it.
    - Filter the full dataset yourself based on task needs before responding.
    - Never fabricate attraction, guide, order, or personalization content. All responses must be based strictly on tool results.
    - After the task is done, report the findings only. Do not suggest follow-up actions.
    </rules>
    """

    return ChatAgent(
        system_message=BaseMessage.make_assistant_message(
            role_name="Xiecheng Agent",
            content=system_message,
        ),
        model=backend_model(),
        tools=tools,
        prune_tool_calls_from_memory=False,
    )
