"""Session 5: the research pipeline on the Claude Agent SDK (Exercise 4, steps 1 and 2).

Same three specialists as the notebook, now as AgentDefinitions. The SDK runs the loops;
the coordinator spawns subagents with the Agent tool (called "Task" in the exam guide).

Usage (from the northwind folder):
    python s5_sdk_research.py --dry-run        # print the configuration, no API call
    python s5_sdk_research.py                  # parallel run (default)
    python s5_sdk_research.py --sequential     # one subagent at a time, for the latency comparison
    python s5_sdk_research.py --narrow         # the narrow, procedural coordinator prompt (diagnosis drill)
    python s5_sdk_research.py --with-support   # homework extension: adds support_analyst, coordinator unchanged

Cost guard: max_budget_usd caps the whole run, subagents included.
"""
import argparse
import asyncio
import json
import sys
import time

from claude_agent_sdk import (AssistantMessage, ClaudeAgentOptions, ResultMessage, ToolAnnotations,
                              ToolResultBlock, ToolUseBlock, UserMessage, create_sdk_mcp_server, query, tool)

if "--with-support" in sys.argv:                # homework extension: register a 4th subagent first
    import solutions.support_analyst_ext  # noqa: F401

from orchestration import NARROW_COORDINATOR_SYSTEM, RESEARCH_QUESTION
from research_tools import RESEARCH_TOOL_DEFS, run_research_tool

try:                                            # your TODO 6, saved by the notebook
    from sdk_config import COORDINATOR_ALLOWED_TOOLS, SERVER, build_agents
    CONFIG_SOURCE = "sdk_config.py (yours)"
except ImportError:
    from solutions.sdk_config_ref import COORDINATOR_ALLOWED_TOOLS, SERVER, build_agents
    CONFIG_SOURCE = "solutions/sdk_config_ref.py (reference)"

try:                                            # your TODO 5, saved by the notebook
    from multi_agent import COORDINATOR_SYSTEM
except ImportError:
    from solutions.multi_agent_ref import COORDINATOR_SYSTEM

SPAWN_TOOL_NAMES = ("Agent", "Task")            # current name, and the name before Claude Code v2.1.63
BUILTINS_OFF = ["Bash", "Read", "Write", "Edit", "Glob", "Grep", "WebFetch", "WebSearch", "NotebookEdit"]


# ---------------------------------------------------------------- tools as an in-process MCP server
def _wrap(name):
    spec = RESEARCH_TOOL_DEFS[name]

    @tool(name, spec["description"], spec["input_schema"], annotations=ToolAnnotations(readOnlyHint=True))
    async def handler(args):
        out = await asyncio.to_thread(run_research_tool, name, args)
        return {"content": [{"type": "text", "text": json.dumps(out)}], "is_error": bool(out.get("isError"))}

    return handler


research_server = create_sdk_mcp_server(name=SERVER, version="1.0.0",
                                        tools=[_wrap(n) for n in RESEARCH_TOOL_DEFS])


def coordinator_prompt(narrow: bool) -> str:
    if narrow:
        return NARROW_COORDINATOR_SYSTEM.replace("delegate_task", "the Agent tool")
    return (COORDINATOR_SYSTEM.replace("delegate_task", "the Agent tool")
            + "\n\nWait for every subagent's report before writing the final answer.")


def build_options(narrow: bool) -> ClaudeAgentOptions:
    return ClaudeAgentOptions(
        system_prompt=coordinator_prompt(narrow),
        agents=build_agents(),
        mcp_servers={SERVER: research_server},
        allowed_tools=COORDINATOR_ALLOWED_TOOLS,
        disallowed_tools=BUILTINS_OFF,           # the research must come from OUR sources only
        model="haiku",
        max_turns=30,
        max_budget_usd=1.00,
        env={
            "ENABLE_TOOL_SEARCH": "false",                     # 5 small tools: load them up front
            "CLAUDE_AGENT_SDK_DISABLE_BUILTIN_AGENTS": "1",    # only our three subagent types
            "CLAUDE_CODE_MAX_SUBAGENT_SPAWN_DEPTH": "1",       # subagents may not spawn subagents
        },
    )


def dry_run(narrow: bool) -> None:
    opts = build_options(narrow)
    print("Config from:", CONFIG_SOURCE)
    print("allowed_tools:", opts.allowed_tools)
    for name, agent in opts.agents.items():
        print(f"\n[{name}]\n  description: {agent.description[:110]}...\n  tools: {agent.tools}\n  model: {agent.model}")
    print("\nCoordinator system prompt (first 300 chars):\n", opts.system_prompt[:300])


async def run(sequential: bool, narrow: bool) -> None:
    prompt = RESEARCH_QUESTION
    if sequential:
        prompt += ("\n\nFor this run, delegate ONE task at a time: wait for each subagent's report "
                   "before starting the next one.")
    started, inflight, max_inflight = {}, set(), 0
    t0 = time.perf_counter()

    async for message in query(prompt=prompt, options=build_options(narrow)):
        parent = getattr(message, "parent_tool_use_id", None)
        if isinstance(message, AssistantMessage):
            for block in message.content:
                if isinstance(block, ToolUseBlock) and block.name in SPAWN_TOOL_NAMES:
                    started[block.id] = time.perf_counter()
                    inflight.add(block.id)
                    max_inflight = max(max_inflight, len(inflight))
                    print(f"[{time.perf_counter() - t0:6.1f}s] SPAWN {block.input.get('subagent_type')}: "
                          f"{str(block.input.get('prompt', ''))[:80]}")
                elif isinstance(block, ToolUseBlock):
                    where = "  (inside subagent)" if parent else "  WARNING: coordinator researched itself"
                    print(f"[{time.perf_counter() - t0:6.1f}s]   {block.name}{where}")
        elif isinstance(message, UserMessage) and isinstance(message.content, list):
            for block in message.content:
                if isinstance(block, ToolResultBlock) and block.tool_use_id in started:
                    inflight.discard(block.tool_use_id)
                    took = time.perf_counter() - started[block.tool_use_id]
                    print(f"[{time.perf_counter() - t0:6.1f}s] REPORT back after {took:.1f}s")
        elif isinstance(message, ResultMessage):
            wall = time.perf_counter() - t0
            print("\n" + "=" * 70)
            print(message.result or "(no result text)")
            print("=" * 70)
            print(f"mode={'sequential' if sequential else 'parallel'}{' narrow' if narrow else ''} | "
                  f"wall={wall:.1f}s | subagents spawned={len(started)} | max concurrent={max_inflight} | "
                  f"turns={message.num_turns} | cost=${message.total_cost_usd or 0:.4f} | {message.subtype}")
            tag = ("narrow" if narrow else "sequential" if sequential else "parallel")
            with open(f"sdk_report_{tag}.md", "w", encoding="utf-8") as fh:
                fh.write(message.result or "")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--sequential", action="store_true")
    ap.add_argument("--narrow", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--with-support", action="store_true")
    a = ap.parse_args()
    if a.dry_run:
        dry_run(a.narrow)
    else:
        asyncio.run(run(a.sequential, a.narrow))
