"""Session 5: the three specialist subagents of the research pipeline.

SubagentSpec is our plain-Python mirror of the Agent SDK's AgentDefinition:

    SubagentSpec field   AgentDefinition field   What it controls
    ------------------   ---------------------   ---------------------------------------
    description          description             WHEN the coordinator picks this agent
    system_prompt        prompt                  HOW the agent behaves (its system prompt)
    tools                tools                   WHAT it may call (least privilege)
    model                model                   which model runs it

Nothing else is shared. A subagent never sees the coordinator's conversation:
everything it needs must travel in the task prompt (see build_subagent_prompt).
"""
from dataclasses import dataclass, field

SUBAGENT_MODEL = "claude-haiku-5-5"


@dataclass(frozen=True)
class SubagentSpec:
    name: str
    description: str
    system_prompt: str
    tools: tuple = field(default_factory=tuple)
    model: str = SUBAGENT_MODEL
    max_iterations: int = 8


_EVIDENCE_RULES = (
    "Evidence rules: cite only what you actually read with your tools. Every finding needs the "
    "source_id (or doc_id / dataset_id), its date, and a locator (url, page number, or quarter). "
    "Never fill a gap from memory. If a tool fails or returns nothing useful, say so in 'gaps' and "
    "set status to 'partial' (some evidence) or 'failed' (none)."
)

SUBAGENTS = {
    "web_researcher": SubagentSpec(
        name="web_researcher",
        description=(
            "Finds and reads PUBLIC web sources: industry benchmarks, carrier and logistics news, "
            "e-commerce research. Use for external context and comparisons. Cannot see Northwind's "
            "internal documents or data."
        ),
        system_prompt=(
            "You are a web research specialist for Northwind Outfitters. You search public articles and "
            "read them in full before citing. Prefer recent sources and always record the publication date, "
            "because older figures may no longer hold. " + _EVIDENCE_RULES
        ),
        tools=("search_web", "fetch_web_page"),
    ),
    "doc_analyst": SubagentSpec(
        name="doc_analyst",
        description=(
            "Searches and reads Northwind's INTERNAL documents: QA incident reports, support ticket "
            "summaries, logistics/carrier reports, merchandising change logs, policies. Use for what "
            "happened inside the company and when."
        ),
        system_prompt=(
            "You are an internal-documents analyst for Northwind Outfitters. Search the document store, read "
            "the relevant pages, and extract dated, specific facts (what changed, when, how many units). "
            + _EVIDENCE_RULES
        ),
        tools=("search_internal_docs", "read_internal_doc"),
    ),
    "data_analyst": SubagentSpec(
        name="data_analyst",
        description=(
            "Queries Northwind's returns database for numbers: return rate by product category and share "
            "of returns by reason, per quarter. Use to measure size and direction of change."
        ),
        system_prompt=(
            "You are a data analyst for Northwind Outfitters. Query the returns database, compare quarters, "
            "and report the numbers exactly as returned, with units. Always report the dataset's coverage "
            "field: a partial period limits what the numbers can prove. " + _EVIDENCE_RULES
        ),
        tools=("query_return_stats",),
    ),
}

# The structure every subagent must return. Content (claim, evidence) is kept
# apart from metadata (source fields) so the coordinator can cite and reconcile.
REPORT_CONTRACT = """Return ONLY one JSON object, no prose around it:
{
  "subagent": "<your name>",
  "status": "complete" | "partial" | "failed",
  "findings": [
    {
      "claim": "<one specific finding in your own words>",
      "evidence": "<the exact figure or short quote that supports it>",
      "source": {"source_id": "<W1 / NW-... / DS-RET-2026>", "type": "web|internal|dataset",
                 "title": "<title>", "date": "YYYY-MM-DD", "locator": "<url, page N, or quarter>"}
    }
  ],
  "coverage": "<what you searched or queried, and the period the data covers>",
  "gaps": ["<anything you could not find, could not verify, or that failed>"]
}"""
