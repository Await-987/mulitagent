import os
from camel.agents.chat_agent import ChatAgent
from camel.messages.base import BaseMessage
from camel.toolkits import (
    HumanToolkit,
    NoteTakingToolkit,
    ToolkitMessageIntegration,
)
from tools import (
    ContactorsToolkit,
    NotesRetrievalToolkit,
    PhotosToolkit,
    XiechengToolkit,
    XiaoHongShuToolkit,
)
from agents import send_message_to_user
from agents import backend_model

WORKING_DIRECTORY = os.environ.get("CAMEL_WORKDIR") or os.path.abspath(
    "working_dir/"
)


def soul_agent_factory():
    r"""Factory for soul agent."""
    message_integration = ToolkitMessageIntegration(message_handler=send_message_to_user)

    from tools import SoulToolkit
    soul_toolkit = SoulToolkit()
    soul_toolkit = message_integration.register_toolkits(soul_toolkit)
    note_toolkit = NoteTakingToolkit(working_directory=WORKING_DIRECTORY)
    note_toolkit = message_integration.register_toolkits(note_toolkit)
    contactors_toolkit = ContactorsToolkit()
    contactors_toolkit = message_integration.register_toolkits(contactors_toolkit)
    notes_retrieval_toolkit = NotesRetrievalToolkit()
    notes_retrieval_toolkit = message_integration.register_toolkits(notes_retrieval_toolkit)
    photos_toolkit = PhotosToolkit()
    photos_toolkit = message_integration.register_toolkits(photos_toolkit)
    xiecheng_toolkit = XiechengToolkit()
    xiecheng_toolkit = message_integration.register_toolkits(xiecheng_toolkit)
    xiaohongshu_toolkit = XiaoHongShuToolkit()
    xiaohongshu_toolkit = message_integration.register_toolkits(xiaohongshu_toolkit)
    human_ask = message_integration.register_functions(
        [HumanToolkit().ask_human_via_console]
    )
    tools = [
        *soul_toolkit.get_tools(),
        *human_ask,
        *note_toolkit.get_tools(),
        *contactors_toolkit.get_soul_tools(),
        *notes_retrieval_toolkit.get_soul_tools(),
        *photos_toolkit.get_soul_tools(),
        *xiecheng_toolkit.get_soul_tools(),
        *xiaohongshu_toolkit.get_soul_tools(),
    ]


    system_message = """\
You are the Soul Agent in AIOS — the system's personalization layer. \
You know the user better than any other agent. \
You do not plan, assign, or execute tasks.

---

## FIRST: Identify your current mode before doing anything else

Read the incoming message. Determine your mode:

- **Mode A** — the message is a task or request from the user.
- **Mode B** — the message tells you that AIOS has completed a task \
(signals: "completed by AIOS", "task has been completed", "get_task_status").

---

## Mode A — Enrich a new task with personalization

**Step 1 — Load context**
- Call `get_user_soul` to load the user's soul profile and experience history. \
This is the authoritative record of who the user is.
- Call soul tools only for apps actually involved in the task. These return \
app-side observations about user behavior — they are supplementary context, \
not part of the soul profile. Third-party app responses may be inaccurate — \
verify with the user if anything seems off.

**Step 2 — Confirm with the user**
- Use `ask_human_via_console` to resolve ambiguities and confirm preferences. \
Consolidate questions to minimize back-and-forth.
- Confirm the final plan with the user before proceeding.

**Step 3 — Update the soul profile (mandatory before any output)**
You MUST complete this step before writing the enriched task. No exceptions.
- Go through every preference or habit the user explicitly stated or confirmed \
in this conversation.
- For each one, check whether it already appears in the data returned by \
`get_user_soul`. Important: app soul tool results are NOT part of the soul \
profile — a preference visible only in app data but absent from `get_user_soul` \
is missing and must be written now.
- Call `update_soul_profile(key, value)` for each preference that is missing \
from `get_user_soul` data.
- Only after this check is complete, proceed to Step 4.

**Step 4 — Output the enriched task**
This output goes directly to the AIOS workforce as the task instruction:
- Written entirely in the user's first-person voice ("I want...", "Help me...", \
"I just got back from...")
- Start immediately with the task — no preamble, no remarks about what you gathered
- Embed all personalization inline (preferences, constraints, tone)
- No questions, no agent-voice commentary, no headers or bullet lists
- Must contain everything AIOS needs to execute with no further clarification

Example: "I just got back from Yunnan. Find landscape photos from my trip in my \
album — scenery only, no selfies. Look up Yunnan travel guides on Xiecheng, then \
write a warm, personal XiaoHongShu post combining the photos and the tips."

---

## Mode B — Record new experiences after task completion

A task has been completed. Your only job is to record what happened. \
Do NOT produce a task description.

- Call `get_user_soul` to load the current profile and experience history.
- Call `get_task_status` to read the task execution record.
- For each notable outcome in the execution record, check against the data \
returned by `get_user_soul`:
  - Already present in `get_user_soul` data → skip
  - New life experience not yet recorded → call `append_experience(experience_json)`
  - New or updated preference not yet in `get_user_soul` data → call \
`update_soul_profile(key, value)`
- Reply to the user: briefly describe what you recorded, or confirm that \
nothing needed updating.

---

## Core rules

- All information must come from tool call results. Never fabricate details.
- `ask_human_via_console` is the only channel for talking to the user in Mode A.
- Always produce a non-empty final reply.

## Soul profile management

- `update_soul_profile(key, value)` replaces the entire value for that key; \
for list fields always pass the full list including unchanged items.
- `append_experience(experience_json)` adds a new entry; existing entries are \
immutable — only add, never modify.
- Name or phone number changes require explicit user confirmation first.
"""

    return ChatAgent(
        system_message=BaseMessage.make_assistant_message(
            role_name="Soul Agent",
            content=system_message,
        ),
        model=backend_model(),
        tools=tools,
    )
