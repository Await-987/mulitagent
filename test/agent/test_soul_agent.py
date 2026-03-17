from agents import soul_agent_factory


def get_response_content(result) -> str:
    if result.msg is not None and result.msg.content.strip():
        return result.msg.content
    for msg in reversed(result.msgs):
        content = (msg.content or "").strip()
        # Skip empty strings and raw JSON tool-call payloads
        if content and not content.startswith("{") and not content.startswith("["):
            return content
    return "(no response)"


def main():
    """Test soul agent: pre-task personalization analysis + post-task profile update."""
    agent = soul_agent_factory()

    # --- Phase 1: Pre-task personalization analysis ---
    original_task = "我去云南玩了，帮我看看相册有没有自拍照，然后去携程看看有没有对应的旅游攻略，写个帖子帮我发到我的小红书上面去。"

    print("\n" + "=" * 60)
    print("Phase 1: Pre-task personalization analysis")
    print("=" * 60)
    print(f"Original task: {original_task}\n")

    pre_result = agent.step(original_task)
    print("Soul Agent output (enriched task):\n")
    # print(get_response_content(pre_result))
    print("msg:", pre_result.msg)
    print("msgs:", pre_result.msgs)

    # # --- Phase 2: Post-task profile update ---
    # print("\n" + "=" * 60)
    # print("Phase 2: Post-task profile update")
    # print("=" * 60)
    #
    # post_result = agent.step(
    #     "The task has been completed by AIOS. "
    #     "Please use get_task_status to review the execution record and decide "
    #     "whether the soul profile needs to be updated based on what happened."
    # )
    # print("Soul Agent output (profile update decision):\n")
    # print(get_response_content(post_result))


if __name__ == "__main__":
    main()
