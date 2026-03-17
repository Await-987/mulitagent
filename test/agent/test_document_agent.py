from agents import document_agent_factory

def test_document_agent():
    """Test document agent"""
    print("\n" + "=" * 60)
    print("Testing document agent")
    print("=" * 60)

    agent = document_agent_factory()
    result = agent.step("帮我创建一个“日记”的markdown文件，里面写今天早上我七点就起床了。告诉我保存到哪里去了。")
    print(result.msg.content)


if __name__ == "__main__":
    test_document_agent()