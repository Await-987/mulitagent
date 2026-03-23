from agents import contactors_agent_factory

def test_contactors_agent():
    """Test contactors agent"""
    print("\n" + "=" * 60)
    print("Testing contactors agent")
    print("=" * 60)

    agent = contactors_agent_factory()
    result = agent.step("刘星的电话号码是多少来着？")
    print(result.msg.content)


if __name__ == "__main__":
    test_contactors_agent()