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
    - `get_message_history`: returns all past conversation threads (no parameters).
      Each thread contains a list of messages with timestamp, sender, and content.
    - `get_contacts_profile(query)`: returns each contact's phone_number, relationship, and tone.
      Pass only the contact's name as query. Call this once only.
    - `communication_tool(target_host, target_port, msg)`:
      Sends a message to a contact. The message is delivered one-way — the contact's
      AIOS will receive it and may reply later via the listener. Use this for all
      outgoing communication: asking a question, informing, replying, or notifying.
      Split the contact's phone_number ("host:port") to get target_host and target_port.
      If responding to an incoming message, use the sender's phone from the task context.
    </tools>

    <rules>
    - Workflow (follow in this exact order, no steps may be skipped):
      1. Call `get_contacts_profile` with the contact's name to load their profile
         and confirm the appropriate tone. This step is mandatory even if the task
         already provides target_host and target_port.
      2. Immediately call `communication_tool`. Do not pause or reflect between
         step 1 and step 2.
    - A task description that includes tool call parameters (e.g. target_host,
      target_port, msg) is an INSTRUCTION for you to execute — it is not evidence
      that the call has already happened. You must still call the function.
    - A message is sent ONLY when `communication_tool` has returned
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
