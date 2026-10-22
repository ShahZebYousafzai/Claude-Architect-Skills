"""Step 6: confirm the Claude Agent SDK can run with your API key."""
import asyncio

from claude_agent_sdk import AssistantMessage, ClaudeAgentOptions, ResultMessage, query


async def main():
    async for message in query(
        prompt="Reply with exactly the words: SDK OK",
        options=ClaudeAgentOptions(allowed_tools=[]),
    ):
        if isinstance(message, AssistantMessage):
            for block in message.content:
                if hasattr(block, "text"):
                    print(block.text)
        elif isinstance(message, ResultMessage):
            print("Done:", message.subtype)


asyncio.run(main())
