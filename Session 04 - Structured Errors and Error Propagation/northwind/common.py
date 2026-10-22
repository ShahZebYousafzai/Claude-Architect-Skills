"""Shared setup for every Northwind exercise script.

Later sessions extend this file (more tools, hooks, error handling)
instead of starting over.

Session 4 state: four tools with the Session 3 descriptions (tool_defs.py), and a
backend that now RAISES exceptions (errors.py). run_tool below is the naive version
most teams write first: one catch-all that turns every failure into "Operation failed".
The Session 4 notebook builds a structured replacement and saves it to tool_errors.py;
once that file exists, this module uses it automatically (same pattern as tool_defs.py).
"""
import json

import anthropic

from backend import get_customer, lookup_order, process_refund, track_shipment

MODEL = "claude-haiku-5-5"   # course default; see the Session 4 review note on model choice

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


def run_tool_naive(name: str, tool_input: dict) -> dict:
    """Execute a tool that Claude asked for. Claude never runs anything itself.

    Session 4 starting point: the naive catch-all. Every failure, whatever its cause,
    reaches Claude as the same opaque sentence. The notebook shows what that costs.
    """
    if name not in TOOL_FUNCTIONS:
        return {"error": f"Unknown tool: {name}"}
    try:
        return TOOL_FUNCTIONS[name](**tool_input)
    except Exception:  # noqa: BLE001 - deliberately naive, replaced in Session 4
        return {"error": "Operation failed"}


run_tool = run_tool_naive


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


def as_tool_result_plain(tool_use_block, result: dict) -> dict:
    """Wrap a tool's output so it can go back to Claude (no is_error flag yet)."""
    return {
        "type": "tool_result",
        "tool_use_id": tool_use_block.id,
        "content": json.dumps(result),
    }


as_tool_result = as_tool_result_plain


# Session 4: once the notebook has saved tool_errors.py, use the structured versions.
# agent_loop.py calls common.run_tool and common.as_tool_result at run time, so this
# swap (or a notebook assigning common.run_tool = ...) changes behaviour everywhere.
try:
    from tool_errors import as_tool_result, run_tool  # noqa: F811,E402
except ImportError:
    pass
