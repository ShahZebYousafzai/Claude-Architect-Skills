"""Shared setup for every Northwind exercise script.

Later sessions extend this file (more tools, hooks, error handling)
instead of starting over.

Session 3 starting state = the Session 2 homework: four tools, thin descriptions,
and one deliberate overlap (track_shipment vs lookup_order). If you wrote your own
homework definitions, paste them over the two new entries below before class.
"""
import json

import anthropic

from backend import get_customer, lookup_order, process_refund, track_shipment

MODEL = "claude-haiku-5-5"

# Reads ANTHROPIC_API_KEY from the environment of the running process.
client = anthropic.Anthropic()

SYSTEM = (
    "You are a customer support agent for Northwind Outfitters, "
    "an online camping-gear store. Be concise and friendly."
)   # Agent Role, agent tone and instructions to follow

# Four tools as of the Session 2 homework. Descriptions are still thin ON PURPOSE.
# Session 3 measures what that costs, then you rewrite them in the notebook.
THIN_TOOLS = [
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
    },
    {
        "name": "get_customer",
        "description": "Retrieves customer details.",
        "input_schema": {
            "type": "object",
            "properties": {
                "email": {"type": "string", "description": "Customer email address"},
                "customer_id": {"type": "string", "description": "Customer ID, e.g. C-1001"},
            },
        },
    },
    {
        "name": "track_shipment",
        "description": "Gets shipping info for an order.",
        "input_schema": {
            "type": "object",
            "properties": {
                "order_id": {"type": "string", "description": "The order number"},
            },
            "required": ["order_id"],
        },
    },
    {
        "name": "process_refund",
        "description": "Refunds an order.",
        "input_schema": {
            "type": "object",
            "properties": {
                "order_id": {"type": "string"},
                "amount": {"type": "number"},
                "reason": {"type": "string"},
            },
            "required": ["order_id", "amount", "reason"],
        },
    },
]

# The tools every agent uses by default. The last cell of the Session 3 notebook writes
# your improved definitions to tool_defs.py; from then on they replace the thin ones.
TOOLS = THIN_TOOLS
try:
    from tool_defs import TOOLS  # noqa: F811
except ImportError:
    pass

# Maps a tool name to the Python function that actually does the work.
TOOL_FUNCTIONS = {
    "lookup_order": lookup_order,
    "get_customer": get_customer,
    "track_shipment": track_shipment,
    "process_refund": process_refund,
}


def run_tool(name: str, tool_input: dict) -> dict:
    """Execute a tool that Claude asked for. Claude never runs anything itself."""
    if name not in TOOL_FUNCTIONS:
        return {"error": f"Unknown tool: {name}"}
    return TOOL_FUNCTIONS[name](**tool_input)


def pick_tools(*names, tools=None):
    """Return the tool definitions with these names, in this order (scoped toolsets)."""
    by_name = {t["name"]: t for t in (tools or TOOLS)}
    missing = [n for n in names if n not in by_name]
    if missing:
        raise KeyError(f"No tool definition for: {missing}")
    return [by_name[n] for n in names]


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
