from agents import photos_agent_factory


def main():
    """Simple test of photos agent"""
    agent = photos_agent_factory()

    # Test queries
    test_queries = [
        # "相册里有哪些场景的照片？相同场景只需要说一次就好。",
        "有哪些去云南的照片？写一个列表给我，包含照片的路径",
        "C:\\Users\\45092\\Desktop\\aios-aios_merge_0307\\mock_data\\photos\\上海外滩.png里面谁才是这个AIOS的机主？"
    ]

    for query in test_queries:
        print(f"\n{'=' * 60}")
        print(f"Query: {query}")
        print(f"{'=' * 60}")

        result = agent.step(query)

        print("Agent Response:", result.msg.content)


if __name__ == "__main__":
    main()
