from agents import notes_agent_factory

def test_notes_agent():
    """Test notes agent"""
    print("\n" + "=" * 60)
    print("Testing notes agent")
    print("=" * 60)

    agent = notes_agent_factory()
    result = agent.step("用户之前去过云南哪里？他记笔记有什么操作习惯？")
    print(result.msg.content)


if __name__ == "__main__":
    test_notes_agent()