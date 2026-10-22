"""Session 5: provided plumbing for the coordinator (hub-and-spoke).

You write the interesting parts in the notebook (TODO 1-5):
    build_subagent_prompt, run_subagent, make_delegate_tool,
    execute_delegations, COORDINATOR_SYSTEM
This module gives you the coordinator loop that calls them, a JSON report
parser, a helper for failed reports, a trace printer, and the deliberately
NARROW coordinator prompt used in the diagnosis drill.
"""
import json
import re
import time

COORDINATOR_MODEL = "claude-haiku-5-5"

RESEARCH_QUESTION = (
    "Why did return rates at Northwind Outfitters rise in Q3 2026, and what should we "
    "change before the holiday season?"
)

# A procedure-style prompt that bakes in an assumption ("it's a quality problem")
# and a fixed partition (by product category, one agent). Every subagent will
# succeed and the report will still be incomplete. Used in section 5.
NARROW_COORDINATOR_SYSTEM = (
    "You are the research coordinator for Northwind Outfitters. Returns are a product quality "
    "problem. Follow these steps exactly: 1) Call delegate_task three times, sending the doc_analyst "
    "one product category each: tents, sleeping bags, stoves. Ask it to find quality defects. "
    "2) Combine the three answers into a short report."
)


# ---------------------------------------------------------------- helpers
def parse_report(text: str):
    """Pull the first JSON object out of a subagent's final text. None if there isn't one."""
    if not text:
        return None
    fenced = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.S)
    candidates = [fenced.group(1)] if fenced else []
    start, end = text.find("{"), text.rfind("}")
    if start != -1 and end > start:
        candidates.append(text[start:end + 1])
    for chunk in candidates:
        try:
            data = json.loads(chunk)
            if isinstance(data, dict):
                return data
        except json.JSONDecodeError:
            continue
    return None


def failed_report(subagent: str, category: str, message: str, retryable: bool = False,
                  attempted: str = "", partial_findings=None, raw: str = "") -> dict:
    """The Session 4 propagation shape, as a subagent report.

    The coordinator gets: what failed (category + message), whether retrying could help,
    what was attempted, and anything found before the failure. Never just "failed".
    """
    report = {
        "subagent": subagent,
        "status": "failed",
        "findings": list(partial_findings or []),
        "coverage": attempted or "nothing completed",
        "gaps": [message],
        "error": {"errorCategory": category, "isRetryable": retryable, "message": message},
    }
    if raw:
        report["raw_output_preview"] = raw[:300]
    return report


def final_text(response) -> str:
    return "".join(b.text for b in response.content if b.type == "text")


# ---------------------------------------------------------------- coordinator loop
def run_coordinator(question, client, *, system, delegate_tool, execute_delegations,
                    parallel=True, model=COORDINATOR_MODEL, max_iterations=10, verbose=True):
    """The Session 2 loop, one level up: the coordinator's only tool is delegate_task.

    Every delegate_task call in ONE response is handed to execute_delegations together,
    which is what makes parallel fan-out possible.

    Returns (final_text, messages, trace). trace lists each delegation round with timings.
    """
    messages = [{"role": "user", "content": question}]
    trace = {"rounds": [], "total_seconds": 0.0, "parallel": parallel}
    t_start = time.perf_counter()

    for _ in range(max_iterations):
        response = client.messages.create(
            model=model, max_tokens=4096, system=system,
            tools=[delegate_tool], messages=messages,
        )
        messages.append({"role": "assistant", "content": response.content})

        if response.stop_reason != "tool_use":
            trace["total_seconds"] = time.perf_counter() - t_start
            return final_text(response), messages, trace

        calls = [b for b in response.content if b.type == "tool_use"]
        if verbose:
            print(f"Round {len(trace['rounds']) + 1}: coordinator sent {len(calls)} task(s) in one response")
            for c in calls:
                print(f"   -> {c.input.get('subagent_type')}: {c.input.get('task', '')[:90]}")
        t0 = time.perf_counter()
        results = execute_delegations(calls, client, parallel=parallel)
        elapsed = time.perf_counter() - t0
        trace["rounds"].append({
            "delegations": [(c.input.get("subagent_type"), c.input.get("task", "")) for c in calls],
            "statuses": [json.loads(r["content"]).get("status") if isinstance(r.get("content"), str) else "?"
                         for r in results],
            "seconds": round(elapsed, 2),
        })
        if verbose:
            print(f"   <- {len(results)} report(s) back in {elapsed:.1f}s, "
                  f"statuses: {trace['rounds'][-1]['statuses']}")
        messages.append({"role": "user", "content": results})

    raise RuntimeError(f"Coordinator did not finish within {max_iterations} iterations")


def print_trace(trace) -> None:
    mode = "parallel" if trace["parallel"] else "sequential"
    print(f"Mode: {mode} | total {trace['total_seconds']:.1f}s | rounds: {len(trace['rounds'])}")
    for i, r in enumerate(trace["rounds"], 1):
        print(f"  round {i}: {r['seconds']}s")
        for (agent, task), status in zip(r["delegations"], r["statuses"]):
            print(f"     {agent:<15} {status:<9} {task[:70]}")
