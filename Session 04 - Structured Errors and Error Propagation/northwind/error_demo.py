"""Helpers for the live part of Session 4: run one case and print a compact trace.

    run_case("Where is order 99999?", run_agent)
    run_case("Where is 12345?", run_agent, faults=[("track_shipment", "timeout", 5)])

The trace shows every tool call, how its result came back (ok, or the errorCategory),
and the final answer. That is all you need to judge: did the agent retry, explain,
ask, or escalate?
"""
import json

import backend


def _blocks(content):
    return content if isinstance(content, list) else []


def trace(history):
    """Print each tool call with the outcome Claude saw."""
    results = {}
    for m in history:
        if m["role"] == "user":
            for b in _blocks(m["content"]):
                if isinstance(b, dict) and b.get("type") == "tool_result":
                    results[b["tool_use_id"]] = b
    n = 0
    for m in history:
        if m["role"] != "assistant":
            continue
        for b in _blocks(m["content"]):
            if getattr(b, "type", None) != "tool_use":
                continue
            n += 1
            r = results.get(b.id, {})
            try:
                payload = json.loads(r.get("content", "{}"))
            except (TypeError, ValueError):
                payload = {}
            if payload.get("isError"):
                outcome = f"ERROR {payload.get('errorCategory')} (retryable={payload.get('isRetryable')})"
            elif "error" in payload:
                outcome = f"ERROR '{payload['error']}'"
            else:
                outcome = "ok"
            flag = " is_error" if r.get("is_error") else ""
            print(f"  call {n}: {b.name}({json.dumps(b.input)}) -> {outcome}{flag}")
    if n == 0:
        print("  (no tool calls)")


def run_case(question, run_agent, *, faults=(), label=None, **agent_kwargs):
    """Clear faults, inject the given ones, run the agent, print the trace and the answer.

    faults: iterable of (tool, kind, times) or (tool, kind, times, when_dict).
    """
    backend.clear_faults()
    for f in faults:
        tool, kind, times, *rest = f
        backend.inject_fault(tool, kind, times=times, when=rest[0] if rest else None)
    print(f"\n=== {label or question}")
    if label:
        print(f"USER: {question}")
    try:
        final, history = run_agent(question, verbose=False, **agent_kwargs)
    finally:
        backend.clear_faults()
    trace(history)
    print("AGENT:", final.strip())
    return final, history
