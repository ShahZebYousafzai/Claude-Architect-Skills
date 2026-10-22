"""Offline checks for the Session 3 run_agent extension. No API key needed.

Usage:  python test_tool_choice_offline.py      (tests solutions/agent_loop.run_agent)
In the notebook the same checks run against YOUR function.
"""
import common
from common import pick_tools
from fake_client import FakeClient, chained_script, reply, text, tool_use


def check_s3(run_agent):
    """Return a list of (name, passed, hint) tuples. Never raises: crashes become FAILs."""
    out = []

    def run(name, fn):
        try:
            ok, hint = fn()
        except Exception as e:  # noqa: BLE001 - report learner crashes, do not raise
            ok, hint = False, f"{type(e).__name__}: {e}"
        out.append((name, ok, hint))

    forced = {"type": "tool", "name": "get_customer"}

    def t_first_has_choice():
        fc = FakeClient(chained_script())
        run_agent("hi", client=fc, verbose=False, tool_choice=forced)
        return fc.requests[0].get("tool_choice") == forced, "The first request must carry the tool_choice you passed."

    def t_later_auto():
        fc = FakeClient(chained_script())
        run_agent("hi", client=fc, verbose=False, tool_choice=forced)
        later = [r.get("tool_choice", {"type": "auto"}) for r in fc.requests[1:]]
        ok = all(c == {"type": "auto"} for c in later)
        return ok, ("Follow-up requests must use auto (or omit tool_choice). Forcing every turn means Claude "
                    f"can never reach end_turn. Sent: {later}")

    def t_default_unchanged():
        fc = FakeClient(chained_script())
        run_agent("hi", client=fc, verbose=False)
        return "tool_choice" not in fc.requests[0], "With no tool_choice argument, send none (Session 2 behaviour)."

    def t_scoped_tools_sent():
        fc = FakeClient(chained_script())
        scoped = pick_tools("get_customer", "lookup_order")
        run_agent("hi", client=fc, verbose=False, tools=scoped)
        names = [[t["name"] for t in r["tools"]] for r in fc.requests]
        ok = all(n == ["get_customer", "lookup_order"] for n in names)
        return ok, f"Every request must send only the scoped toolset. Sent: {names}"

    def t_out_of_scope_refused():
        calls = []
        real = common.TOOL_FUNCTIONS["process_refund"]
        common.TOOL_FUNCTIONS["process_refund"] = lambda **kw: calls.append(kw) or {"status": "issued"}
        try:
            fc = FakeClient([
                reply("tool_use", tool_use("x1", "process_refund", order_id="12399", amount=79, reason="broken")),
                reply("end_turn", text("I can't issue refunds, but I've noted it.")),
            ])
            run_agent("refund", client=fc, verbose=False, tools=pick_tools("get_customer", "lookup_order"))
        finally:
            common.TOOL_FUNCTIONS["process_refund"] = real
        result = fc.requests[1]["messages"][-1]["content"][0]
        ok = not calls and "error" in result.get("content", "")
        return ok, ("A tool outside the agent's scope must NOT run. Return an error tool_result instead. "
                    f"Backend called {len(calls)} time(s).")

    def t_system_param():
        fc = FakeClient([reply("end_turn", text("ok"))])
        run_agent("hi", client=fc, verbose=False, system="CUSTOM")
        return fc.requests[0]["system"] == "CUSTOM", "Pass the system argument through to the request."

    run("tool_choice sent on the first request", t_first_has_choice)
    run("follow-up requests fall back to auto", t_later_auto)
    run("no tool_choice argument -> none sent", t_default_unchanged)
    run("scoped toolset sent on every request", t_scoped_tools_sent)
    run("out-of-scope tool call is refused", t_out_of_scope_refused)
    run("system prompt parameter honoured", t_system_param)
    return out


if __name__ == "__main__":
    import os, sys
    os.environ.setdefault("ANTHROPIC_API_KEY", "offline-test")
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "solutions"))
    from agent_loop import run_agent
    from test_loop_offline import check_loop, report
    print("Session 2 regression checks")
    ok2 = report(check_loop(run_agent))
    print("\nSession 3 checks")
    ok3 = report(check_s3(run_agent))
    sys.exit(0 if ok2 and ok3 else 1)
