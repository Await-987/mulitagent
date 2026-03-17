import asyncio
import os
from camel.logger import get_logger
from camel.societies.workforce import Workforce
from camel.tasks.task import Task
from agents import (coordinator_agent_factory,
                    task_agent_factory,
                    developer_agent_factory,
                    document_agent_factory,
                    contactors_agent_factory,
                    notes_agent_factory,
                    photos_agent_factory,
                    soul_agent_factory,
                    search_agent_factory,
                    xiaohongshu_agent_factory,
                    xiecheng_agent_factory
                    )
from demo.monitor.run_event_artifacts import RunEventArtifacts

logger = get_logger(__name__)

WORKING_DIRECTORY = os.environ.get("CAMEL_WORKDIR") or os.path.abspath(
    "working_dir/"
)

async def main():
    # Ensure working directory exists
    os.makedirs(WORKING_DIRECTORY, exist_ok=True)

### ========== ↓↓↓ 第1处 part.1 ↓↓↓ ========== ###
    run_artifacts = RunEventArtifacts(WORKING_DIRECTORY)
    run_artifacts.prepare_run_output_dir()
### ========== ↑↑↑ 第1处 part.1 ↑↑↑ ========== ###

    # Create custom agents for the workforce
    coordinator_agent = coordinator_agent_factory()
    task_agent = task_agent_factory()
    developer_agent = developer_agent_factory()
    document_agent = document_agent_factory()
    contactors_agent = contactors_agent_factory()
    notes_agent = notes_agent_factory()
    photos_agent = photos_agent_factory()
    soul_agent = soul_agent_factory()
    search_agent = search_agent_factory()
    xiaohongshu_agent = xiaohongshu_agent_factory()
    xiecheng_agent = xiecheng_agent_factory()

    # Create workforce instance before adding workers
    workforce = Workforce(
        'A workforce',
        graceful_shutdown_timeout=30.0,  
        share_memory=False,
        coordinator_agent=coordinator_agent,
        task_agent=task_agent,
        use_structured_output_handler=False,
        task_timeout_seconds=900.0,
    )

    workforce.add_single_agent_worker(
        "Document Agent: A fallback document processing specialist for handling direct file operations within AIOS internal workflows. "
        "Serves as the LAST-RESORT solution for file processing tasks - should ONLY be invoked when specialized app agents (Notes Agent, Photos Agent, XiaoHongShu Agent, etc.) cannot handle the file operation. "
        "Provides edge capability support for generic document operations including creating/modifying text files (Markdown, JSON, YAML, HTML), office documents (Word, PDF), "
        "presentations (PowerPoint), and spreadsheets (Excel, CSV). Capabilities include document reading, document creation with formatting, PowerPoint layouts, Excel management, and data visualization. "
        "IMPORTANT: Always prioritize specialized app agents first before considering this agent.",
        worker=document_agent,
    ).add_single_agent_worker(
        "Contactors Agent: An application-level intelligent assistant integrated within the AIOS Contacts application. "
        "Retrieves and analyzes conversation history and contact profiles from the Contacts app. "
        "Uses get_message_history to access all past conversations and get_contacts_profile to look up phone numbers, "
        "relationship context, and recommended communication tone. "
        "Sends messages to remote AIOS contacts via D2D communication using ask_tool, "
        "composing messages with appropriate tone while protecting user privacy.",
        worker=contactors_agent,
    ).add_single_agent_worker(
        "Notes Agent: An application-level intelligent assistant integrated within the AIOS Notes application. "
        "Retrieves and analyzes personal notes from the local Notes app database. "
        "Calls search_my_notes to retrieve the full local dataset and filters results based on the task.",
        worker=notes_agent,
    ).add_single_agent_worker(
        "Photos Agent: An application-level intelligent assistant integrated within the AIOS Photos application. "
        "Searches, retrieves, and analyzes photo content from the local Photos app database. "
        "Uses search_photos to retrieve all photo records and get_image_information for detailed image analysis and visual descriptions.",
        worker=photos_agent,
    ).add_single_agent_worker(
        "Search Agent: An application-level intelligent web research specialist integrated within the AIOS Browser application. "
        "Conducts web searches, browses websites, and gathers online information. "
        "Uses search_exa for initial searches, HybridBrowserToolkit for website navigation and interaction, and records detailed findings using note-taking tools.",
        worker=search_agent,
    ).add_single_agent_worker(
        "XiaoHongShu Agent: An application-level intelligent assistant integrated within the third-party XiaoHongShu application on AIOS. "
        "Publishes posts to the XiaoHongShu platform using publish_xhs_post tool with title, text content, and images. "
        "Formats content according to XiaoHongShu platform standards. Cannot search, edit, or delete posts - only publishes new content immediately.",
        worker=xiaohongshu_agent,
    ).add_single_agent_worker(
        "Xiecheng Travel Agent: An application-level intelligent assistant integrated within the Xiecheng (携程) travel application on AIOS. "
        "Provides three core query capabilities: (1) Attraction lookup — ask about any scenic spot or destination to get official details such as opening hours, ticket prices, and visitor notices; "
        "(2) Travel guide retrieval — find destination guides and travel recommendations the user has previously browsed on Xiecheng, such as itinerary suggestions and local tips; "
        "(3) Order inquiry — check the user's travel order history including flight bookings, hotel reservations, attraction tickets, and train tickets. "
        "This agent is read-only and cannot create, modify, or cancel any orders or bookings.",
        worker=xiecheng_agent,
    )


    ori_task = " 给秦华老师发消息：“你晚饭吃的什么？” "
    #ori_task = "我去云南玩了，帮我看看相册有没有自拍照，然后去携程看看有没有对应的旅游攻略，写个帖子帮我发到我的社交媒体。"
    
### ========== ↓↓↓ 第2处 part.2 ↓↓↓ ========== ###
    run_artifacts.attach_event_file_writer(workforce.metrics_logger)
    run_artifacts.attach_agent_message_event_bridge(workforce.metrics_logger)
    run_artifacts.log_original_task(workforce.metrics_logger, ori_task)
### ========== ↑↑↑ 第2处 part.2 ↑↑↑ ========== ###

    fancy_task = soul_agent.step(ori_task)

    human_task = Task(
        content=(
            fancy_task.msg.content
        ),
        id='0',
    )

    # Use the async version directly to avoid hanging with async tools
    await workforce.process_task_async(human_task)

    # Test WorkforceLogger features
    print("\n--- Workforce Log Tree ---")
    print(workforce.get_workforce_log_tree())

    print("\n--- Workforce KPIs ---")
    kpis = workforce.get_workforce_kpis()
    for key, value in kpis.items():
        print(f"{key}: {value}")

    log_file_path = "eigent_logs.json"
    print(f"\n--- Dumping Workforce Logs to {log_file_path} ---")
    workforce.dump_workforce_logs(log_file_path)
    print(f"Logs dumped. Please check the file: {log_file_path}")

    result = soul_agent.step("Now please update the `soul.md` file")

if __name__ == "__main__":
    asyncio.run(main())
