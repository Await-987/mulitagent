import asyncio
import os
import time
from camel.logger import get_logger
from camel.societies.workforce import Workforce
from camel.tasks.task import Task

try:
    from demo.os_view import ui_bridge as _bridge
except ImportError:
    _bridge = None

try:
    from demo.os_view.lib.response_summarizer import summarize_response as _summarize
except ImportError:
    _summarize = None

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
from demo.monitor.run_event_artifacts import RunEventArtifacts
from demo import WORKING_DIRECTORY

logger = get_logger(__name__)


async def _get_enriched_task(agent, task: str) -> str:
    """Call Soul Agent to produce an enriched task for the Workforce."""
    started_at = time.monotonic()
    try:
        if hasattr(agent, "run"):
            return await agent.run(task)
        result = agent.step(task)
        if result.msg and result.msg.content.strip():
            return result.msg.content
        for msg in reversed(result.msgs):
            content = (msg.content or "").strip()
            if content:
                return content
        return ""
    finally:
        print(f"  Soul Agent finished in {time.monotonic() - started_at:.1f}s")


# ---------------------------------------------------------------------------
# Main pipeline
# ---------------------------------------------------------------------------


async def main(task: str = ""):
    os.environ.setdefault("AIOS_AUTO_CONFIRM_PUBLISH", "1")
    os.makedirs(WORKING_DIRECTORY, exist_ok=True)
    run_artifacts = RunEventArtifacts(WORKING_DIRECTORY)
    run_artifacts.prepare_run_output_dir()

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
        "Document Agent: Creates output files and writes task_status.md.",
        worker=document_agent,
    ).add_single_agent_worker(
        "Contactors Agent: Looks up contacts and sends D2D messages.",
        worker=contactors_agent,
    ).add_single_agent_worker(
        "Notes Agent: Retrieves the user's personal notes.",
        worker=notes_agent,
    ).add_single_agent_worker(
        "Photos Agent: Searches photos and analyzes image content.",
        worker=photos_agent,
    ).add_single_agent_worker(
        "Search Agent: Web search and browsing.",
        worker=search_agent,
    ).add_single_agent_worker(
        "XiaoHongShu Agent: Publishes posts to XiaoHongShu.",
        worker=xiaohongshu_agent,
    ).add_single_agent_worker(
        "Xiecheng Agent: Queries attractions, guides, and travel orders.",
        worker=xiecheng_agent,
    )

    original_task = task
    run_artifacts.attach_event_file_writer(workforce.metrics_logger)
    run_artifacts.attach_agent_message_event_bridge(workforce.metrics_logger)
    run_artifacts.log_original_task(workforce.metrics_logger, original_task)

    # Phase 1: Soul enrichment
    print("AIOS received task:", original_task)
    if _bridge:
        _bridge.push_system_message("小艺正在结合您的个人档案理解任务…")
    enriched = await _get_enriched_task(soul_agent, original_task)
    if not enriched:
        enriched = original_task
    print("AIOS enriched task:\n", enriched)

    # Phase 2: Workforce execution
    if _bridge:
        _bridge.push_system_message("小艺正在协调各应用处理您的任务…")
    t0 = time.monotonic()
    completed_task = await workforce.process_task_async(
        Task(content=enriched, id='0')
    )
    print(f"Workforce finished in {time.monotonic() - t0:.1f}s")
    print(f"Status: {completed_task.state}")

    # Phase 3: Deliver result
    if _bridge and completed_task.result:
        if _summarize:
            try:
                msg = _summarize(original_task, enriched, completed_task.result)
            except Exception:
                msg = completed_task.result
        else:
            msg = completed_task.result
        _bridge.push_ai_message(msg)

    workforce.dump_workforce_logs(
        os.path.join(WORKING_DIRECTORY, "workforce_logs.json")
    )
    if hasattr(soul_agent, "reset"):
        soul_agent.reset()
    if _bridge:
        _bridge.mark_done()


if __name__ == "__main__":
    _task = "我去云南玩了，帮我看看相册有没有自拍照，然后去携程看看有没有对应的旅游攻略，写个帖子帮我发到我的小红书上面去。"
    asyncio.run(main(_task))