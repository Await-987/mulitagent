from agents import developer_agent_factory

def test_developer_agent():
    """Test developer agent"""
    print("\n" + "=" * 60)
    print("Testing developer agent")
    print("=" * 60)

    agent = developer_agent_factory()
    result = agent.step("用dir命令，去“C:\\Users\\45092\\Desktop”目录下帮我看看下面有哪些文件？")
    print(result.msg.content)


if __name__ == "__main__":
    test_developer_agent()