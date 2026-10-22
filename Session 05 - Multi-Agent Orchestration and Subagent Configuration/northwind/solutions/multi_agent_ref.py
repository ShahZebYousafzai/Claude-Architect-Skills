"""Session 5 reference solutions for TODO 1-5 (raw Messages API, hub-and-spoke).

Named *_ref.py so nothing auto-imports it by accident. The notebook's save cell
writes YOUR versions to multi_agent.py; this file is the fallback.
"""
import json
from concurrent.futures import ThreadPoolExecutor

from orchestration import failed_report, parse_report
from research_tools import RESEARCH_TOOL_DEFS, run_research_tool
from subagents import REPORT_CONTRACT, SUBAGENTS


# TODO 1 ---------------------------------------------------------------------
def build_subagent_prompt(task: str, context: str, contract: str = REPORT_CONTRACT) -> str:
    """Everything the subagent will ever know about this job, in one message.

    The subagent starts with an empty history. If a fact is not in this string,
    the subagent does not have it.
    """
    return (
        "## Your task\n"
        f"{task.strip()}\n\n"
        "## Context from the coordinator\n"
        f"{(context or '').strip() or 'No extra context.'}\n\n"
        "## Scope\n"
        "Work only on the task above. You cannot see the coordinator's conversation or other "
        "agents' work; everything you need is in this message.\n\n"
        "## Output format\n"
        f"{contract}"
    )


# TODO 2 ---------------------------------------------------------------------
def run_subagent(spec, prompt: str, client, verbose: bool = False) -> dict:
    """Run one subagent in an isolated loop and return its structured report (a dict)."""
    tools = [RESEARCH_TOOL_DEFS[name] for name in spec.tools]          # scoped toolset only
    messages = [{"role": "user", "content": prompt}]                    # fresh, isolated history

    for _ in range(spec.max_iterations):
        response = client.messages.create(
            model=spec.model, max_tokens=2048, system=spec.system_prompt,
            tools=tools, messages=messages,
        )
        messages.append({"role": "assistant", "content": response.content})

        if response.stop_reason == "tool_use":
            results = []
            for block in response.content:
                if block.type != "tool_use":
                    continue
                if block.name not in spec.tools:                         # defence in depth
                    output = {"isError": True, "errorCategory": "permission", "isRetryable": False,
                              "message": f"{spec.name} is not allowed to call {block.name}."}
                else:
                    output = run_research_tool(block.name, block.input)
                if verbose:
                    print(f"      [{spec.name}] {block.name}({block.input}) -> "
                          f"{'ERROR' if output.get('isError') else 'ok'}")
                results.append({"type": "tool_result", "tool_use_id": block.id,
                                "content": json.dumps(output), "is_error": bool(output.get("isError"))})
            messages.append({"role": "user", "content": results})
            continue

        text = "".join(b.text for b in response.content if b.type == "text")
        report = parse_report(text)
        if report is None:
            return failed_report(spec.name, "output_format",
                                 "Subagent finished without the JSON report.", raw=text)
        report.setdefault("subagent", spec.name)
        report.setdefault("status", "partial")
        report.setdefault("findings", [])
        report.setdefault("gaps", [])
        return report

    return failed_report(spec.name, "max_iterations",
                         f"No report after {spec.max_iterations} turns.", retryable=False)


# TODO 3 ---------------------------------------------------------------------
def make_delegate_tool(subagents=SUBAGENTS) -> dict:
    """Our version of the Agent SDK's Task/Agent tool. Built from the registry, so adding
    a subagent automatically makes it selectable (dynamic selection by description)."""
    roster = "\n".join(f"- {name}: {spec.description}" for name, spec in subagents.items())
    return {
        "name": "delegate_task",
        "description": (
            "Send one focused research task to a specialist subagent and get back its structured report "
            "(findings with sources, coverage, gaps, status). The subagent starts with NO memory of this "
            "conversation and cannot see other subagents' work, so put every fact, constraint and earlier "
            "finding it needs into `context`. Independent tasks should be sent together in the same "
            "response so they run in parallel.\nAvailable subagents:\n" + roster
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "subagent_type": {"type": "string", "enum": list(subagents),
                                  "description": "Which specialist runs this task."},
                "task": {"type": "string",
                         "description": "One focused objective and what a complete answer must include."},
                "context": {"type": "string",
                            "description": "Background the subagent needs: the overall question, relevant "
                                           "earlier findings with their source ids, time period, constraints."},
            },
            "required": ["subagent_type", "task", "context"],
        },
    }


# TODO 4 ---------------------------------------------------------------------
def execute_delegations(tool_uses, client, parallel: bool = True, subagents=SUBAGENTS) -> list:
    """Run every delegate_task call from ONE coordinator response.

    One tool_result per tool_use, same order. A failing subagent becomes an is_error
    tool_result with a structured report; it never kills the other subagents.
    """
    def run_one(block):
        spec = subagents.get(block.input.get("subagent_type"))
        if spec is None:
            report = failed_report(str(block.input.get("subagent_type")), "validation",
                                   f"Unknown subagent_type. Choose one of {list(subagents)}.")
        else:
            try:
                prompt = build_subagent_prompt(block.input.get("task", ""), block.input.get("context", ""))
                report = run_subagent(spec, prompt, client)
            except Exception as exc:                                     # crash -> structured, not fatal
                report = failed_report(spec.name, "transient", f"Subagent crashed: {exc}", retryable=True,
                                       attempted=block.input.get("task", ""))
        return {"type": "tool_result", "tool_use_id": block.id,
                "content": json.dumps(report), "is_error": report.get("status") == "failed"}

    if parallel and len(tool_uses) > 1:
        with ThreadPoolExecutor(max_workers=len(tool_uses)) as pool:
            return list(pool.map(run_one, tool_uses))                    # map keeps the order
    return [run_one(b) for b in tool_uses]


# TODO 5 ---------------------------------------------------------------------
COORDINATOR_SYSTEM = """You are the research coordinator for Northwind Outfitters' operations team.
You do no research yourself: you plan, delegate with delegate_task, check what comes back, and write the synthesis.

Goal: answer the research question with a report the operations team can act on before the holiday season.

Quality criteria for the final report:
- Coverage: consider every stage of the customer journey that can cause a return (the product itself, how it is described and sized online, fulfilment and delivery, and post-purchase policy). For each stage, present evidence or state that you checked and found none.
- Evidence: every claim cites its source id (W1, NW-..., DS-RET-2026) and date. Quantify with figures where the data allows.
- Honesty: state data coverage limits and any subagent failures as gaps. When sources disagree, show both with their dates instead of picking one.
- Usefulness: end with prioritized, specific recommendations tied to the drivers you found.

How to work well:
- Subagents know nothing except what you send them. Give each one the overall question, the period, and any earlier findings it needs, with source ids.
- Send independent tasks in the same response so they run in parallel.
- Before writing the final report, compare the findings against the coverage criterion. If a stage is unexamined or a report has gaps that matter, delegate a focused follow-up, then synthesize."""
