import asyncio
import os
from camel.logger import get_logger
from camel.societies.workforce import Workforce
from camel.tasks.task import Task
from agents import (
    coordinator_agent_factory,
    task_agent_factory,
    soul_agent_factory,
    document_agent_factory,
    contactors_agent_factory,
    notes_agent_factory,
    photos_agent_factory,
    search_agent_factory,
    xiaohongshu_agent_factory,
    xiecheng_agent_factory,
)

logger = get_logger(__name__)

WORKING_DIRECTORY = os.environ.get("CAMEL_WORKDIR") or os.path.abspath(
    "working_dir/"
)


def _get_response_content(result) -> str:
    if result.msg is not None and result.msg.content.strip():
        return result.msg.content
    for msg in reversed(result.msgs):
        content = (msg.content or "").strip()
        if content and not content.startswith("{") and not content.startswith("["):
            return content
    return ""


async def main(task: str = ""):
    os.makedirs(WORKING_DIRECTORY, exist_ok=True)
    soul_agent = soul_agent_factory()
    coordinator_agent = coordinator_agent_factory()
    task_agent = task_agent_factory()
    document_agent = document_agent_factory()
    contactors_agent = contactors_agent_factory()
    notes_agent = notes_agent_factory()
    photos_agent = photos_agent_factory()
    search_agent = search_agent_factory()
    xiaohongshu_agent = xiaohongshu_agent_factory()
    xiecheng_agent = xiecheng_agent_factory()

    workforce = Workforce(
        'AIOS Workforce',
        graceful_shutdown_timeout=30.0,
        share_memory=False,
        coordinator_agent=coordinator_agent,
        task_agent=task_agent,
        use_structured_output_handler=True,
        task_timeout_seconds=900.0,
    )

    workforce.add_single_agent_worker(
        "Document Agent: Responsible for creating and writing files in the working "
        "directory. The ONLY agent that can produce output files (Markdown, JSON, "
        "Word, PDF, Excel, PowerPoint, etc.). Must always be the final agent to "
        "summarize the task and write task_status.md.",
        worker=document_agent,
    ).add_single_agent_worker(
        "Contactors Agent: Integrated within the AIOS Contacts app. Looks up contact "
        "profiles (phone numbers, relationship background, recommended communication "
        "tone) via get_contacts_profile, retrieves full message history via "
        "get_message_history, sends D2D inquiries that await a reply via ask_tool, "
        "and sends one-way D2D replies or notifications via tell_tool.",
        worker=contactors_agent,
    ).add_single_agent_worker(
        "Notes Agent: Integrated within the AIOS Notes app. Retrieves the user's "
        "personal notes and memos via search_my_notes. Use this agent to surface "
        "relevant notes, ideas, or records stored by the user.",
        worker=notes_agent,
    ).add_single_agent_worker(
        "Photos Agent: Integrated within the AIOS Photos app. Retrieves all photo "
        "metadata via search_photos and performs detailed visual content analysis on "
        "individual images via get_image_information. Use this agent to find photos "
        "or understand what is in them.",
        worker=photos_agent,
    ).add_single_agent_worker(
        "Search Agent: Integrated within the AIOS Browser app. Performs web searches "
        "and browses websites to gather up-to-date online information. Use this agent "
        "for any task that requires external knowledge or real-time web content.",
        worker=search_agent,
    ).add_single_agent_worker(
        "XiaoHongShu Agent: Integrated within the third-party XiaoHongShu app. "
        "Publishes photo-and-text posts to the XiaoHongShu platform via "
        "publish_xhs_post (title, body text, image paths). Publish-only — cannot "
        "search, edit, or delete posts.",
        worker=xiaohongshu_agent,
    ).add_single_agent_worker(
        "Xiecheng Agent: Integrated within the third-party Xiecheng travel app. "
        "Queries attraction details via search_attractions, retrieves travel guides "
        "via search_guides, and looks up the user's historical travel orders "
        "(flights, hotels, tickets, trains) via search_orders. Read-only — cannot "
        "create, modify, or cancel any booking.",
        worker=xiecheng_agent,
    )

    original_task = task
    print("AIOS received task:", original_task)
    soul_response = soul_agent.step(original_task)
    enriched_task_content = _get_response_content(soul_response)
    if not enriched_task_content or enriched_task_content == "(no response)":
        print("Warning: Soul Agent returned no content — falling back to original task.")
        enriched_task_content = original_task
    print("AIOS is building the plan:\n", enriched_task_content)

    human_task = Task(content=enriched_task_content, id='0')
    await workforce.process_task_async(human_task)

    print("\n--- Workforce Log Tree ---")
    print(workforce.get_workforce_log_tree())

    print("\n--- Workforce KPIs ---")
    kpis = workforce.get_workforce_kpis()
    for key, value in kpis.items():
        print(f"{key}: {value}")

    log_file_path = os.path.join(WORKING_DIRECTORY, "workforce_logs.json")
    workforce.dump_workforce_logs(log_file_path)
    print(f"\nWorkforce logs saved to: {log_file_path}")

    soul_agent.reset()

    soul_result = soul_agent.step(
        "The task has been completed by AIOS. "
        "Please use get_task_status to review the execution record and decide "
        "whether the soul profile needs to be updated based on what happened."
    )
    print("\n--- Soul Agent: Profile Update ---")
    print(_get_response_content(soul_result))


if __name__ == "__main__":
    # _task = "我去云南玩了，帮我看看相册有没有自拍照，然后去携程看看有没有对应的旅游攻略，写个帖子帮我发到我的小红书上面去。"
    _task = "帮我问问艾华老师，下午几点开会来着"
    asyncio.run(main(_task))
