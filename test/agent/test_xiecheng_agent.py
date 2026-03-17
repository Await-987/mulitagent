from agents import xiecheng_agent_factory


def main():
    """Simple test of xiecheng agent"""
    agent = xiecheng_agent_factory()

    test_queries = [
        "用户最近订了哪些酒店？",
        "帮用户查一下故宫的信息",
        "有哪些成都的攻略？",
    ]
    
    for query in test_queries:
        print(f"\n{'='*60}")
        print(f"Query: {query}")
        print(f"{'='*60}")
        
        result = agent.step(query)

        print("Agent Response:", result.msg.content)


if __name__ == "__main__":
    main()
