"""Shared setup for every Northwind exercise script.

Later sessions extend this file (more tools, hooks, error handling)
instead of starting over.
"""
import json

import anthropic

from backend import lookup_order

MODEL = "claude-sonnet-5-5"

# Reads ANTHROPIC_API_KEY from the environment of the running process.
client = anthropic.Anthropic()

SYSTEM = (
    "You are a customer support agent for Northwind Outfitters, "
    "an online camping-gear store. Be concise and friendly."
)

# One tool for now. The description is deliberately minimal:
# in Session 3 you will improve it and see the difference.
TOOLS = [
    {
        "name": "lookup_order",
        "description": "Retrieves order details.",
        "input_schema": {
            "type": "object",
            "properties": {
                "order_id": {"type": "string", "description": "The order number"},
            },
            "required": ["order_id"],
        },
    }
]

# Maps a tool name to the Python function that actually does the work.
TOOL_FUNCTIONS = {"lookup_order": lookup_order}


def run_tool(name: str, tool_input: dict) -> dict:
    """Execute a tool that Claude asked for. Claude never runs anything itself."""
    return TOOL_FUNCTIONS[name](**tool_input)


def show(response) -> None:
    """Print the parts of a response that matter for control flow."""
    print("stop_reason:", response.stop_reason)
    print("content blocks:", len(response.content))
    for i, block in enumerate(response.content):
        if block.type == "text":
            print(f'  [{i}] text     -> "{block.text}"')
        elif block.type == "tool_use":
            print(f"  [{i}] tool_use -> {block.name}")
            print(f"                  id={block.id}")
            print(f"                  input={block.input}")
        else:
            print(f"  [{i}] {block.type}")


def as_tool_result(tool_use_block, result: dict) -> dict:
    """Wrap a tool's output so it can go back to Claude."""
    return {
        "type": "tool_result",
        "tool_use_id": tool_use_block.id,
        "content": json.dumps(result),
    }
