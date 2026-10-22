"""Homework extension reference: a fourth subagent added WITHOUT touching coordinator code.

Import this module BEFORE building the delegate tool (raw API) or the SDK options:
    import solutions.support_analyst_ext   # registers the tool and the subagent
It mutates the registries in place, which is exactly what makes dynamic selection work:
make_delegate_tool() and build_agents() both read the registries at call time.
"""
import time

import research_tools
from research_corpus import INTERNAL_DOCS
from subagents import SUBAGENTS, SubagentSpec


def search_support_tickets(theme: str) -> dict:
    """Search ONLY the Q3 support ticket summary (NW-SUP-Q3), page by page."""
    time.sleep(research_tools.TOOL_LATENCY)
    doc = INTERNAL_DOCS["NW-SUP-Q3"]
    words = {w for w in theme.lower().split() if len(w) > 2}
    hits = [{"doc_id": "NW-SUP-Q3", "page": i + 1, "date": doc["date"], "text": page}
            for i, page in enumerate(doc["pages"]) if words & set(page.lower().replace("'", " ").split())]
    return {"theme": theme, "matches": hits, "searched": "NW-SUP-Q3 (Support ticket themes, Q3 2026), all pages"}


research_tools.RESEARCH_FUNCTIONS["search_support_tickets"] = search_support_tickets
research_tools.RESEARCH_TOOL_DEFS["search_support_tickets"] = {
    "name": "search_support_tickets",
    "description": ("Search the Q3 2026 customer support ticket summary for a complaint theme (e.g. 'runs small', "
                    "'arrived damaged'). Returns matching pages with their text. Covers support tickets only."),
    "input_schema": {"type": "object",
                     "properties": {"theme": {"type": "string", "description": "Complaint words to look for"}},
                     "required": ["theme"]},
}

SUBAGENTS["support_analyst"] = SubagentSpec(
    name="support_analyst",
    description=("Reads what CUSTOMERS complained about in Q3 2026 support tickets (themes, timing, products). "
                 "Use for the customer's side of a problem. Does not read QA, logistics or merchandising documents."),
    system_prompt=("You analyse customer support ticket themes for Northwind Outfitters. Report each theme with "
                   "the product, the timing and the page it came from. Cite only what the tool returned."),
    tools=("search_support_tickets",),
)
