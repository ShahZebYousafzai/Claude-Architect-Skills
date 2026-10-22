"""Session 5 offline checks: no API key, no cost, deterministic.

    python test_multi_agent_offline.py            # checks multi_agent.py (yours) or the reference
    from test_multi_agent_offline import report   # in the notebook: report(globals())
"""
import json
import time
from types import SimpleNamespace as NS

import research_tools
from fake_multi_client import (RoutingFakeClient, fault_scripts, good_scripts, narrow_scripts,
                               reply, text, tool_use)
from orchestration import RESEARCH_QUESTION, run_coordinator
from subagents import REPORT_CONTRACT, SUBAGENTS

PASS, FAIL = "PASS", "FAIL"


def _get(ns, name):
    return ns.get(name) if isinstance(ns, dict) else getattr(ns, name, None)


def _single_agent_client(agent, replies, latency=0.0):
    return RoutingFakeClient({agent: [("", replies)]}, latency=latency)


def _report_text(**kw):
    base = {"subagent": "doc_analyst", "status": "complete", "findings": [], "coverage": "x", "gaps": []}
    base.update(kw)
    return json.dumps(base)


# ---------------------------------------------------------------- individual checks
def check_prompt(ns):
    f = _get(ns, "build_subagent_prompt")
    p = f("Measure Q3 tent returns.", "Earlier finding: TP-0726 cracked (NW-QA-2026-031).")
    ok = ("Measure Q3 tent returns." in p and "TP-0726" in p and "NW-QA-2026-031" in p
          and '"findings"' in p and '"gaps"' in p)
    return ok, "task + context (with source ids) + output contract all in the prompt"


def check_isolation(ns):
    f, spec = _get(ns, "run_subagent"), SUBAGENTS["data_analyst"]
    client = _single_agent_client("data_analyst", [reply("end_turn", text(_report_text(subagent="data_analyst")))])
    f(spec, "PROMPT-XYZ", client)
    r = client.requests[0]
    ok = (r["n_messages"] == 1 and r["first_message"] == "PROMPT-XYZ"
          and r["system"] == spec.system_prompt and r["tools"] == ["query_return_stats"])
    return ok, "fresh history (1 message), its own system prompt, only its own tools"


def check_tool_loop(ns):
    f, spec = _get(ns, "run_subagent"), SUBAGENTS["doc_analyst"]
    client = _single_agent_client("doc_analyst", [
        reply("tool_use", tool_use("t1", "read_internal_doc", doc_id="NW-POLICY-RET", page=1)),
        reply("end_turn", text("Here you go:\n```json\n" + _report_text() + "\n```")),
    ])
    rep = f(spec, "p", client)
    ok = isinstance(rep, dict) and rep.get("status") == "complete" and len(client.requests) == 2
    return ok, "executes tool_use, sends tool_result back, parses the JSON report (even inside ```json)"


def check_out_of_scope(ns):
    f, spec = _get(ns, "run_subagent"), SUBAGENTS["data_analyst"]
    seen = {}

    class Spy(RoutingFakeClient):
        def create(self, **kw):
            if len(kw["messages"]) == 3:
                seen["result"] = kw["messages"][2]["content"][0]
            return super().create(**kw)

    client = Spy({"data_analyst": [("", [
        reply("tool_use", tool_use("t1", "search_web", query="returns")),
        reply("end_turn", text(_report_text(subagent="data_analyst"))),
    ])]}, latency=0)
    f(spec, "p", client)
    res = seen.get("result", {})
    body = json.loads(res.get("content", "{}")) if isinstance(res.get("content"), str) else {}
    ok = res.get("is_error") is True and body.get("errorCategory") == "permission"
    return ok, "a tool outside the subagent's scope is refused with a permission error"


def check_bad_output(ns):
    f, spec = _get(ns, "run_subagent"), SUBAGENTS["web_researcher"]
    client = _single_agent_client("web_researcher", [reply("end_turn", text("I think returns went up."))])
    rep = f(spec, "p", client)
    ok = isinstance(rep, dict) and rep.get("status") == "failed" and rep.get("error", {}).get("errorCategory")
    return ok, "no JSON report -> status 'failed' with a structured error, not an exception"


def check_delegate_tool(ns):
    t = _get(ns, "make_delegate_tool")()
    props = t.get("input_schema", {}).get("properties", {})
    enum = props.get("subagent_type", {}).get("enum", [])
    req = set(t.get("input_schema", {}).get("required", []))
    desc = t.get("description", "").lower()
    ok = (t.get("name") == "delegate_task" and sorted(enum) == sorted(SUBAGENTS)
          and {"subagent_type", "task", "context"} <= req
          and all(s.description[:30].lower() in desc for s in SUBAGENTS.values()))
    return ok, "name, enum from registry, task+context required, roster descriptions in the description"


def _calls(*specs):
    return [NS(type="tool_use", id=f"c{i}", name="delegate_task",
               input={"subagent_type": a, "task": t, "context": "ctx"}) for i, (a, t) in enumerate(specs)]


def check_parallel(ns):
    f = _get(ns, "execute_delegations")
    old = research_tools.TOOL_LATENCY
    research_tools.TOOL_LATENCY = 0.0
    try:
        mk = lambda a: [("", [reply("end_turn", text(_report_text(subagent=a)))])]
        client = RoutingFakeClient({a: mk(a) for a in SUBAGENTS}, latency=0.4)
        calls = _calls(*[(a, f"task for {a}") for a in SUBAGENTS])
        t0 = time.perf_counter()
        results = f(calls, client, parallel=True)
        took = time.perf_counter() - t0
    finally:
        research_tools.TOOL_LATENCY = old
    ok = (len(results) == 3 and [r["tool_use_id"] for r in results] == ["c0", "c1", "c2"]
          and all(r.get("type") == "tool_result" for r in results) and took < 1.0)
    return ok, f"3 subagents concurrently ({took:.2f}s for 3 x 0.4s), one tool_result per call, order kept"


def check_failure_isolated(ns):
    f = _get(ns, "execute_delegations")
    client = RoutingFakeClient({"data_analyst": [("", [reply("end_turn", text(_report_text(subagent="data_analyst")))])]},
                               latency=0)
    calls = _calls(("data_analyst", "ok task"), ("no_such_agent", "bad task"))
    results = f(calls, client, parallel=True)
    bad = json.loads(results[1]["content"]) if len(results) == 2 else {}
    ok = (len(results) == 2 and results[0].get("is_error") in (False, None) and results[1].get("is_error") is True
          and bad.get("status") == "failed")
    return ok, "one bad delegation -> is_error result with a structured report; the other still returns"


def check_end_to_end(ns):
    client = RoutingFakeClient(good_scripts(), latency=0.05)
    final, msgs, trace = run_coordinator(
        RESEARCH_QUESTION, client, system=_get(ns, "COORDINATOR_SYSTEM"),
        delegate_tool=_get(ns, "make_delegate_tool")(),
        execute_delegations=_get(ns, "execute_delegations"), verbose=False)
    ok = (len(trace["rounds"]) == 2 and len(trace["rounds"][0]["delegations"]) == 3 and "TP-0726" in final)
    return ok, "scripted run: 3 parallel delegations, 1 follow-up, final report"


def check_coordinator_prompt(ns):
    s = (_get(ns, "COORDINATOR_SYSTEM") or "").lower()
    goal_words = sum(w in s for w in ("goal", "criteria", "complete", "coverage"))
    evidence = any(w in s for w in ("source", "cite"))
    gaps = "gap" in s
    procedural = "follow these steps exactly" in s or "returns are a product quality problem" in s
    ok = goal_words >= 2 and evidence and gaps and not procedural
    return ok, "goals + quality criteria (coverage, sources, gaps), not a fixed procedure"


CHECKS = [check_prompt, check_isolation, check_tool_loop, check_out_of_scope, check_bad_output,
          check_delegate_tool, check_parallel, check_failure_isolated, check_end_to_end, check_coordinator_prompt]


def check_sdk_config(build_agents, allowed_tools):
    """TODO 6: AgentDefinitions built correctly, coordinator allowed to spawn subagents."""
    out = []
    try:
        agents = build_agents()
    except Exception as exc:                      # noqa: BLE001
        return [(FAIL, "build_agents() raised", repr(exc))]
    out.append((PASS if len(agents) >= 2 else FAIL, "two or more AgentDefinitions", f"{len(agents)} defined"))
    scoped = all(a.tools and all(t.startswith("mcp__") for t in a.tools) for a in agents.values())
    out.append((PASS if scoped else FAIL, "each subagent has an explicit, scoped tools list (MCP tools only)", ""))
    distinct = len({tuple(sorted(a.tools or [])) for a in agents.values()}) == len(agents)
    out.append((PASS if distinct else FAIL, "toolsets differ per subagent (no copy-paste of all tools)", ""))
    described = all(a.description and len(a.description) > 40 for a in agents.values())
    out.append((PASS if described else FAIL, "every description says when to use the agent", ""))
    contract = all('"findings"' in (a.prompt or "") for a in agents.values())
    out.append((PASS if contract else FAIL, "every prompt includes the report contract", ""))
    spawn = any(t in allowed_tools for t in ("Agent", "Task"))
    out.append((PASS if spawn else FAIL, "coordinator allowed_tools includes the spawn tool (Agent / Task)", ""))
    return out


def report(ns, sdk=True):
    rows = []
    for chk in CHECKS:
        try:
            ok, what = chk(ns)
            rows.append((PASS if ok else FAIL, chk.__name__, what))
        except Exception as exc:                  # noqa: BLE001
            rows.append((FAIL, chk.__name__, f"raised {type(exc).__name__}: {exc}"))
    for status, name, what in rows:
        print(f"{status}  {name:<26} {what}")
    passed = sum(r[0] == PASS for r in rows)
    print(f"\n{passed}/{len(rows)} checks passed")
    if sdk and _get(ns, "build_agents"):
        print("\nTODO 6 (SDK config):")
        for status, what, note in check_sdk_config(_get(ns, "build_agents"), _get(ns, "COORDINATOR_ALLOWED_TOOLS") or []):
            print(f"{status}  {what} {note}")
    return passed, len(rows)


if __name__ == "__main__":
    try:
        import multi_agent as mod
        print("Checking multi_agent.py (yours)\n")
    except ImportError:
        from solutions import multi_agent_ref as mod
        print("Checking solutions/multi_agent_ref.py (reference)\n")
    ns = dict(vars(mod))
    try:
        try:
            import sdk_config as cfg
        except ImportError:
            from solutions import sdk_config_ref as cfg
        ns.update(build_agents=cfg.build_agents, COORDINATOR_ALLOWED_TOOLS=cfg.COORDINATOR_ALLOWED_TOOLS)
    except ImportError as exc:
        print("(Agent SDK not installed, skipping TODO 6 checks:", exc, ")")
    report(ns)
