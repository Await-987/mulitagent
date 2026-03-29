import os
from camel.agents.chat_agent import ChatAgent
from camel.messages.base import BaseMessage
from camel.toolkits import (
    NoteTakingToolkit,
    ToolkitMessageIntegration,
)
from tools import NotesRetrievalToolkit, UIHumanToolkit
from agents import send_message_to_user
from agents import backend_model

WORKING_DIRECTORY = os.environ.get("CAMEL_WORKDIR") or os.path.abspath(
    "working_dir/"
)


def notes_agent_factory():
    message_integration = ToolkitMessageIntegration(message_handler=send_message_to_user)
    note_toolkit = NoteTakingToolkit(working_directory=WORKING_DIRECTORY)
    notes_toolkit = NotesRetrievalToolkit()
    notes_toolkit = message_integration.register_toolkits(notes_toolkit)

    tools = [
        *notes_toolkit.get_tools(),
        UIHumanToolkit().ask_human_via_console,
        *note_toolkit.get_tools(),
    ]

    system_message = """
    You are the Notes Agent for the AIOS Notes app.
    You retrieve personal notes and provide personalization insights for the user.

    <tools>
    - `search_my_notes`: returns all notes stored in the Notes app (no parameters).
      Call this whenever a task requires reading note content. Filter the results yourself based on the task.
    - `get_notes_soul(query)`: returns personalization insights about the user's note-taking habits and preferences.
      Pass a natural language description of the consultation as query.
      Use this when a system agent needs to understand the user's knowledge organization style, not the raw note content.
    </tools>

    <rules>
    - Choosing the right tool:
      · The task requires reading note content (e.g. find, retrieve, look up) → call `search_my_notes` first.
      · The task requires personalization context (e.g. understand habits, preferences, style) → call `get_notes_soul`.
    - Never fabricate note content or personalization insights. All responses must be based strictly on tool results.
    - After the task is done, report the findings only. Do not suggest follow-up actions.
    </rules>
    """

    return ChatAgent(
        system_message=BaseMessage.make_assistant_message(
            role_name="Notes Agent",
            content=system_message,
        ),
        model=backend_model(),
        tools=tools,
    )
