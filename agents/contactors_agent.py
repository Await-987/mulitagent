import os
from camel.agents.chat_agent import ChatAgent
from camel.messages.base import BaseMessage
from camel.toolkits import (
    HumanToolkit,
    NoteTakingToolkit,
    ToolkitMessageIntegration,
)
from tools import ContactorsToolkit
from agents import send_message_to_user
from agents import backend_model


WORKING_DIRECTORY = os.environ.get("CAMEL_WORKDIR") or os.path.abspath(
    "working_dir/"
)


def contactors_agent_factory():
    message_integration = ToolkitMessageIntegration(
        message_handler=send_message_to_user
    )
    note_toolkit = NoteTakingToolkit(working_directory=WORKING_DIRECTORY)
    contactors_toolkit = ContactorsToolkit()
    contactors_toolkit = message_integration.register_toolkits(contactors_toolkit)

    tools = [
        *contactors_toolkit.get_tools(),
        HumanToolkit().ask_human_via_console,
        *note_toolkit.get_tools(),
    ]

    system_message = """
    You are the Contactors Agent for the AIOS Contactors app.
    You look up contact info and send D2D messages on behalf of the user.

    <tools>
    - `get_message_history`: returns all past conversations (no parameters).
    - `get_contacts_profile(query)`: returns each contact's phone_number, relationship, and tone.
      Pass only the contact's name as query. Call this once only.
    - `ask_tool(target_host, target_port, msg)`:
      Sends a message and waits for a reply. Use when you need a response from the contact.
      Split the contact's phone_number ("host:port") to get target_host and target_port.
    - `tell_tool(target_host, target_port, msg, incoming_msg, caller_name, caller_phone)`:
      Sends a one-way message — no response expected. Use when informing or replying to a contact.
      Split the contact's phone_number ("host:port") to get target_host and target_port,
      or use response_host/response_port if provided in an incoming request.
      Pass incoming_msg, caller_name, caller_phone when available (used for logging).
    </tools>

    <rules>
    - Choosing the right tool:
      · The task expects a reply from the contact (e.g. ask, inquire, find out) → use `ask_tool`.
      · The task is just sending something without expecting a response
        (e.g. reply, tell, notify, inform) → use `tell_tool`.
    - Workflow (follow in this exact order, no steps may be skipped):
      1. Call `get_contacts_profile` with the contact's name to load their profile
         and confirm the appropriate tone. This step is mandatory even if the task
         already provides target_host and target_port.
      2. Immediately call `ask_tool` or `tell_tool`. Do not pause or reflect between
         step 1 and step 2.
    - A task description that includes tool call parameters (e.g. target_host,
      target_port, msg) is an INSTRUCTION for you to execute — it is not evidence
      that the call has already happened. You must still call the function.
    - A message is sent ONLY when `ask_tool` or `tell_tool` has returned
      {"status": "success"} as a function call result visible in this conversation.
      If you cannot find that return value in your context, the message has not been
      sent — do not report success.
    - Never fabricate phone numbers. If a contact is not found, report it clearly.
    - After the task is done, report the outcome only. Do not suggest follow-up actions.
    </rules>
    """

    return ChatAgent(
        system_message=BaseMessage.make_assistant_message(
            role_name="Contactors Agent",
            content=system_message,
        ),
        model=backend_model(),
        tools=tools,
    )
