"""
Response Summarizer — generates a natural Chinese reply from raw task results.

Called after the AIOS Workforce completes a task. Takes the original user
request, the enriched task, and the raw subtask results, then produces a
concise, conversational summary suitable for display in the 小艺 chat panel.
"""

from camel.agents import ChatAgent
from camel.messages import BaseMessage
from agents.backend_model import backend_model

_SYSTEM_PROMPT = (
    "你是小艺，一个贴心的智能助手。你的任务是根据用户的原始请求和系统执行结果，"
    "生成一段简洁、自然、口语化的中文回复。\n\n"
    "要求：\n"
    "- 用第一人称（我）回复，语气亲切自然\n"
    "- 重点总结做了什么、结果是什么，不要罗列子任务编号\n"
    "- 如果执行结果中包含关键信息（如时间、地点、人名、具体内容），务必保留\n"
    "- 回复控制在 2-4 句话以内，避免冗长\n"
    "- 不要输出任何英文技术术语或子任务标记（如 Subtask、Result 等）\n"
    "- 直接输出回复内容，不要加任何前缀或标签"
)


def summarize_response(
    original_task: str,
    enriched_task: str,
    raw_result: str,
) -> str:
    """Summarize workforce results into a natural Chinese reply.

    Args:
        original_task: The user's original request text.
        enriched_task: The Soul Agent enriched task content.
        raw_result: The raw concatenated subtask results from Workforce.

    Returns:
        A concise, natural Chinese response string.
    """
    agent = ChatAgent(
        system_message=_SYSTEM_PROMPT,
        model=backend_model(),
        output_language="Chinese",
    )

    user_content = (
        f"【用户请求】\n{original_task}\n\n"
        f"【任务详情】\n{enriched_task}\n\n"
        f"【执行结果】\n{raw_result}"
    )

    msg = BaseMessage.make_user_message(role_name="User", content=user_content)
    response = agent.step(msg)

    if response and response.msg and response.msg.content.strip():
        return response.msg.content.strip()

    return "任务已完成。"
