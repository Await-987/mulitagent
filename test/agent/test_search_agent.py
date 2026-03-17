import asyncio
from agents import search_agent_factory


async def main():
    """Simple test of search agent"""
    agent = search_agent_factory()

    # Test queries
    test_queries = [
        "哈梅内伊怎么样了？"
    ]

    for query in test_queries:
        print(f"\n{'=' * 60}")
        print(f"Query: {query}")
        print(f"{'=' * 60}")

        result = await agent.astep(query)

        print("Agent Response:", result.msg.content)


if __name__ == "__main__":
    asyncio.run(main())
