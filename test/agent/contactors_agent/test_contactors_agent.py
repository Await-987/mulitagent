"""
Please ensure that <./aihua_listener_response.py> and <./liuxing_listener.py> are running in the first place.
"""

from agents import contactors_agent_factory


def test_query_contact_info():
    """Check info of contactors app"""
    print("\n" + "=" * 60)
    print("Checkings info of contactors app")
    print("=" * 60)

    agent = contactors_agent_factory()
    result = agent.step("帮我查一下通讯录里艾华老师的联系方式和关系背景")
    print(result.msg.content)


def test_query_call_log():
    """Check call logs of contactors app"""
    print("\n" + "=" * 60)
    print("Checking call logs of contactors app")
    print("=" * 60)

    agent = contactors_agent_factory()
    result = agent.step("帮我看一下最近和刘星的通话记录，主要聊了什么内容")
    print(result.msg.content)


def test_d2d_ask():
    """Check ask function with the expectation of response"""
    print("\n" + "=" * 60)
    print("Checking ask function with the expectation of response")
    print("=" * 60)

    agent = contactors_agent_factory()
    result = agent.step("帮我问一下艾华老师，今天下午的组会是几点开始")
    print(result.msg.content)


def test_d2d_reply():
    """Check tell function without the expectation of response"""
    print("\n" + "=" * 60)
    print("Checking tell function without the expectation of response")
    print("=" * 60)

    agent = contactors_agent_factory()
    result = agent.step(
        "刘星发来消息问我：'明天有空一起出去玩吗？' "
        "请帮我回复他说明天可以出去玩。"
    )
    print(result.msg.content)


if __name__ == "__main__":
    # test_query_contact_info()
    # test_query_call_log()
    # test_d2d_ask()
    test_d2d_reply()
