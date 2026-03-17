from agents import xiaohongshu_agent_factory


def main():
    """Simple test of xiaohongshu agent"""
    agent = xiaohongshu_agent_factory()

    # Test queries
    test_queries = [
        "请帮助用户发布一个小红书笔记，内容就是我今天去上海的思南公馆的咖啡厅喝咖啡了，特别开心。配图的照片是C:\\Users\\45092\\Desktop\\aios\\mock_data\\photos\\coffee.jpg。",
        "用户发小红书照片的时候有什么特殊的习惯吗？"
    ]

    for query in test_queries:
        print(f"\n{'=' * 60}")
        print(f"Query: {query}")
        print(f"{'=' * 60}")

        result = agent.step(query)

        print("Agent Response:", result.msg.content)


if __name__ == "__main__":
    main()
