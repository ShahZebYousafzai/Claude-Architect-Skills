"""Session 5 reference for TODO 6: the same three subagents as Agent SDK AgentDefinitions.

s5_sdk_research.py imports build_agents() and COORDINATOR_ALLOWED_TOOLS from sdk_config.py
(your version, written by the notebook) or falls back to this file.
"""
from claude_agent_sdk import AgentDefinition

from research_tools import RESEARCH_FUNCTIONS
from subagents import REPORT_CONTRACT, SUBAGENTS

SERVER = "research"   # key used in mcp_servers={...}; tool names become mcp__research__<tool>


def mcp_name(tool: str) -> str:
    return f"mcp__{SERVER}__{tool}"


def build_agents() -> dict:
    """One AgentDefinition per SubagentSpec. Same description (selection), prompt (behaviour),
    scoped tools (least privilege) and a cheap model."""
    return {
        name: AgentDefinition(
            description=spec.description,
            prompt=spec.system_prompt + "\n\n" + REPORT_CONTRACT,
            tools=[mcp_name(t) for t in spec.tools],
            model="haiku",
        )
        for name, spec in SUBAGENTS.items()
    }


# The coordinator must be allowed to spawn subagents. The exam guide (and SDK releases
# before Claude Code v2.1.63) call this tool "Task"; current releases call it "Agent".
# Listing both keeps the script working on either version.
# The research tools are listed so the subagents' calls run without permission prompts.
COORDINATOR_ALLOWED_TOOLS = ["Agent", "Task"] + [mcp_name(t) for t in RESEARCH_FUNCTIONS]
