"""Offline checks for run_agent. No API key needed.

Usage:  python test_loop_offline.py            (tests agent_loop.run_agent)
In the notebook the same checks run against YOUR function.
"""
from fake_client import FakeClient, chained_script, reply, text, tool_use


def check_loop(run_agent):
    """Return a list of (name, passed, hint) tuples. Never raises: crashes become FAILs."""
    out = []

    def run(name, fn):
        try:
            ok, hint = fn()
        except Exception as e:  # noqa: BLE001 - we want learner crashes reported, not raised
            ok, hint = False, f"{type(e).__name__}: {e}"
        out.append((name, ok, hint))

    def t_continues():
        fc = FakeClient(chained_script())
        run_agent("Where is my tent? alex.rivera@example.com", client=fc, verbose=False)
        return len(fc.requests) == 3, (
            "Expected 3 requests (get_customer, lookup_order, final answer) but the loop made "
            f"{len(fc.requests)}. Did it stop because a text block appeared next to a tool_use?")

    def t_final_text():
        fc = FakeClient(chained_script())
        final, _ = run_agent("hi", client=fc, verbose=False)
        return "SwiftShip" in (final or ""), "Return the text of the end_turn response, not the earlier preamble."

    def t_roles():
        fc = FakeClient(chained_script())
        run_agent("hi", client=fc, verbose=False)
        roles = [m["role"] for m in fc.requests[-1]["messages"]]
        return roles == ["user", "assistant", "user", "assistant", "user"], f"Roles sent on the last request: {roles}"

    def t_ids():
        fc = FakeClient(chained_script())
        run_agent("hi", client=fc, verbose=False)
        tr = fc.requests[-1]["messages"][2]["content"][0]
        ok = isinstance(tr, dict) and tr.get("type") == "tool_result" and tr.get("tool_use_id") == "toolu_1"
        return ok, "tool_use_id must equal the id of the tool_use block it answers."

    def t_parallel():
        fc = FakeClient([
            reply("tool_use",
                  tool_use("a", "lookup_order", order_id="12345"),
                  tool_use("b", "lookup_order", order_id="12400")),
            reply("end_turn", text("Both orders found.")),
        ])
        run_agent("two orders", client=fc, verbose=False)
        ids = [r["tool_use_id"] for r in fc.requests[-1]["messages"][-1]["content"]]
        return ids == ["a", "b"], "Claude can request several tools in one response; answer all of them in ONE user turn."

    def t_no_tools():
        fc = FakeClient([reply("end_turn", text("Hello!"))])
        final, _ = run_agent("hi", client=fc, verbose=False)
        return final == "Hello!" and len(fc.requests) == 1, "A plain answer needs exactly one request."

    def t_guard():
        fc = FakeClient([reply("tool_use", tool_use(f"t{i}", "lookup_order", order_id="12345")) for i in range(50)])
        try:
            run_agent("loop forever", client=fc, max_iterations=4, verbose=False)
        except Exception:
            return len(fc.requests) == 4, "The cap should allow exactly max_iterations requests, then raise."
        return False, "Hitting the cap must be loud (raise), not a quiet 'success'."

    run("continues past text + tool_use", t_continues)
    run("returns the final end_turn text", t_final_text)
    run("history alternates user/assistant", t_roles)
    run("tool_result matches the tool_use id", t_ids)
    run("answers every tool_use block", t_parallel)
    run("ends on end_turn when no tools needed", t_no_tools)
    run("guard rail raises when exceeded", t_guard)
    return out


def report(results):
    for name, ok, hint in results:
        print(("PASS  " if ok else "FAIL  ") + name + ("" if ok else f"\n        hint: {hint}"))
    passed = sum(ok for _, ok, _ in results)
    print(f"\n{passed}/{len(results)} checks passed")
    return passed == len(results)


if __name__ == "__main__":
    import os, sys
    os.environ.setdefault("ANTHROPIC_API_KEY", "offline-test")
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), "solutions"))
    from agent_loop import run_agent
    sys.exit(0 if report(check_loop(run_agent)) else 1)
