"""Offline checks for the Session 4 TODOs. No API key needed, no API calls.

Each check_* function takes YOUR function from the notebook and returns a list of
(name, passed, hint). Use report() from test_loop_offline to print them.

Usage:  python test_errors_offline.py      (tests the reference solutions)
"""
import inspect
import json

import backend
import common
from errors import InvalidInput, NotFound, ServiceTimeout
from fake_client import FakeClient, reply, text, tool_use


def _noop(_seconds):
    pass


def _runner(out):
    def run(name, fn):
        backend.clear_faults()
        try:
            ok, hint = fn()
        except Exception as e:  # noqa: BLE001 - learner crashes are reported, not raised
            ok, hint = False, f"{type(e).__name__}: {e}"
        finally:
            backend.clear_faults()
        out.append((name, bool(ok), hint))
    return run


def _with_sleep(fn, **kwargs):
    """Pass sleep=_noop when the function accepts it, so checks stay fast."""
    if "sleep" in inspect.signature(fn).parameters:
        kwargs["sleep"] = _noop
    return kwargs


# ------------------------------------------------------------------ TODO 1
def check_structured_error(structured_error):
    out, run = [], None
    run = _runner(out)

    def t_shape():
        e = structured_error("validation", "No order 99999")
        ok = (e.get("isError") is True and e.get("errorCategory") == "validation"
              and isinstance(e.get("message"), str) and "isRetryable" in e)
        return ok, f"Need isError=True, errorCategory, isRetryable and message. Got: {e}"

    def t_defaults():
        got = {c: structured_error(c, "x").get("isRetryable")
               for c in ("transient", "validation", "business", "permission")}
        want = {"transient": True, "validation": False, "business": False, "permission": False}
        return got == want, f"Only transient errors are retryable by default. Got: {got}"

    def t_override():
        e = structured_error("transient", "circuit open", retryable=False)
        return e.get("isRetryable") is False, "retryable=False must override the category default."

    def t_customer_message():
        with_msg = structured_error("business", "over limit", customer_message="We can refund at most 34.00")
        without = structured_error("validation", "bad id")
        ok = with_msg.get("customer_message") == "We can refund at most 34.00" and "customer_message" not in without
        return ok, "Include customer_message only when one is given."

    def t_details():
        e = structured_error("validation", "bad id", field="order_id", example="12345")
        d = e.get("details", {})
        return d.get("field") == "order_id" and d.get("example") == "12345", \
            f"Extra keyword arguments belong under 'details'. Got: {e}"

    def t_unknown():
        try:
            structured_error("oops", "x")
        except ValueError:
            return True, ""
        return False, "An unknown category should raise ValueError (a typo here would mislead the agent)."

    run("payload has isError/errorCategory/isRetryable/message", t_shape)
    run("only transient is retryable by default", t_defaults)
    run("retryable override works", t_override)
    run("customer_message only when given", t_customer_message)
    run("extra context goes under details", t_details)
    run("unknown category rejected", t_unknown)
    return out


# ------------------------------------------------------------------ TODO 2
def check_retry(call_with_retry):
    out = []
    run = _runner(out)

    def flaky(failures, exc_type=ServiceTimeout):
        state = {"calls": 0}

        def fn(**kw):
            state["calls"] += 1
            if state["calls"] <= failures:
                raise exc_type("boom")
            return {"ok": True, **kw}
        return fn, state

    def t_first_try():
        fn, state = flaky(0)
        slept = []
        result, attempts = call_with_retry(fn, {"order_id": "1"}, max_attempts=3, sleep=slept.append)
        return (result.get("ok") and attempts == 1 and not slept and state["calls"] == 1), \
            "Success on the first call: return (result, 1) and do not sleep."

    def t_recovers():
        fn, state = flaky(2)
        slept = []
        result, attempts = call_with_retry(fn, {}, max_attempts=3, sleep=slept.append)
        ok = result.get("ok") and attempts == 3 and len(slept) == 2 and slept[1] > slept[0]
        return ok, f"Two timeouts then success: attempts=3, two growing sleeps. Got attempts={attempts}, sleeps={slept}"

    def t_exhausted():
        fn, state = flaky(10)
        try:
            call_with_retry(fn, {}, max_attempts=3, sleep=_noop)
        except ServiceTimeout:
            return state["calls"] == 3, f"Give up after exactly max_attempts calls (made {state['calls']})."
        return False, "When every attempt times out, re-raise the ServiceTimeout so the caller can report it."

    def t_no_retry_validation():
        for exc_type in (InvalidInput, NotFound):
            fn, state = flaky(10, exc_type)
            try:
                call_with_retry(fn, {}, max_attempts=3, sleep=_noop)
            except exc_type:
                if state["calls"] != 1:
                    return False, f"{exc_type.__name__} was retried {state['calls']} times. Retrying a bad input never helps."
                continue
            return False, f"{exc_type.__name__} must be re-raised immediately."
        return True, ""

    run("first-try success returns attempts=1", t_first_try)
    run("recovers from transient timeouts with backoff", t_recovers)
    run("gives up after max_attempts and re-raises", t_exhausted)
    run("never retries validation / not-found errors", t_no_retry_validation)
    return out


# ------------------------------------------------------------------ TODO 3
def check_run_tool(run_tool_structured):
    out = []
    run = _runner(out)

    def call(name, tool_input):
        return run_tool_structured(name, tool_input, **_with_sleep(run_tool_structured))

    def cat(r):
        return r.get("errorCategory") if isinstance(r, dict) and r.get("isError") else None

    def t_not_found():
        r = call("lookup_order", {"order_id": "99999"})
        return cat(r) == "validation" and r.get("isRetryable") is False, \
            f"Order 99999 does not exist: validation, not retryable. Got: {r}"

    def t_malformed():
        r = call("track_shipment", {"order_id": "12-34"})
        return cat(r) == "validation" and "order_id" in json.dumps(r), \
            f"A malformed ID is a validation error that says which field and what format. Got: {r}"

    def t_transient_unresolved():
        backend.inject_fault("track_shipment", "timeout", times=10)
        r = call("track_shipment", {"order_id": "12345"})
        attempts = (r.get("details") or {}).get("attempts")
        return cat(r) == "transient" and r.get("isRetryable") is True and attempts == 3, \
            f"After 3 failed attempts: transient, isRetryable=True, details.attempts=3. Got: {r}"

    def t_transient_recovered():
        backend.inject_fault("track_shipment", "timeout", times=1)
        r = call("track_shipment", {"order_id": "12345"})
        return cat(r) is None and r.get("carrier") == "SwiftShip", \
            f"One timeout should be retried locally; Claude should never see it. Got: {r}"

    def t_business_limit():
        r = call("process_refund", {"order_id": "12455", "amount": 649, "reason": "torn"})
        code = (r.get("details") or {}).get("code")
        return (cat(r) == "business" and r.get("isRetryable") is False and r.get("customer_message")
                and code == "REFUND_ABOVE_AUTO_LIMIT"), \
            f"Refund above the limit: business, not retryable, customer_message, details.code. Got: {r}"

    def t_business_paid():
        r = call("process_refund", {"order_id": "12400", "amount": 100, "reason": "dim"})
        return cat(r) == "business" and (r.get("details") or {}).get("code") == "REFUND_EXCEEDS_PAID", \
            f"Refund above the amount paid: business error REFUND_EXCEEDS_PAID. Got: {r}"

    def t_permission():
        backend.inject_fault("process_refund", "permission")
        r = call("process_refund", {"order_id": "12400", "amount": 34, "reason": "dim"})
        return cat(r) == "permission" and r.get("isRetryable") is False, \
            f"A credential without the scope: permission, not retryable. Got: {r}"

    def t_unknown_tool():
        r = call("cancel_order", {"order_id": "12345"})
        return cat(r) == "validation", f"An unknown tool name is a validation error. Got: {r}"

    def t_valid_empty():
        r = call("get_customer", {"email": "sam.okafor@example.com"})
        return cat(r) is None and r.get("order_ids") == [] and not r.get("isError"), \
            f"A customer with no orders is a SUCCESS with an empty list, not an error. Got: {r}"

    def t_processing_not_error():
        r = call("track_shipment", {"order_id": "12399"})
        return cat(r) is None and r.get("status") == "processing", \
            f"An order with no tracking yet is a normal result. Got: {r}"

    def t_no_generic():
        r = call("lookup_order", {"order_id": "99999"})
        return "Operation failed" not in json.dumps(r), "No generic 'Operation failed' messages."

    run("unknown order ID -> validation, not retryable", t_not_found)
    run("malformed order ID -> validation naming the field", t_malformed)
    run("persistent timeout -> transient, retryable, attempts=3", t_transient_unresolved)
    run("single timeout recovered locally", t_transient_recovered)
    run("refund above $500 -> business + customer_message", t_business_limit)
    run("refund above amount paid -> business", t_business_paid)
    run("missing scope -> permission", t_permission)
    run("unknown tool -> validation", t_unknown_tool)
    run("customer with no orders is a valid empty result", t_valid_empty)
    run("processing order (no tracking) is not an error", t_processing_not_error)
    run("no generic 'Operation failed'", t_no_generic)
    return out


# ------------------------------------------------------------------ TODO 4
def check_tool_result(as_tool_result):
    out = []
    run = _runner(out)
    block = tool_use("toolu_9", "lookup_order", order_id="99999")
    err = {"isError": True, "errorCategory": "validation", "isRetryable": False, "message": "No order"}

    def t_error_flag():
        b = as_tool_result(block, err)
        ok = (b.get("type") == "tool_result" and b.get("tool_use_id") == "toolu_9"
              and b.get("is_error") is True and json.loads(b["content"]) == err)
        return ok, f"Error payload: is_error=True, same tool_use_id, JSON content. Got: {b}"

    def t_success_flag():
        b = as_tool_result(block, {"order_id": "12345"})
        return not b.get("is_error"), "A successful result must not be marked is_error."

    run("error result marked is_error=True", t_error_flag)
    run("success result not marked is_error", t_success_flag)
    return out


# ------------------------------------------------------------------ TODO 5
def check_agent_permission(run_agent, as_tool_result=None):
    out = []
    run = _runner(out)

    def t_permission():
        calls = []
        real_fn = common.TOOL_FUNCTIONS["process_refund"]
        real_wrap = common.as_tool_result
        common.TOOL_FUNCTIONS["process_refund"] = lambda **kw: calls.append(kw) or {"status": "issued"}
        if as_tool_result is not None:
            common.as_tool_result = as_tool_result
        try:
            fc = FakeClient([
                reply("tool_use", tool_use("x1", "process_refund", order_id="12399", amount=79, reason="broken")),
                reply("end_turn", text("I can't issue refunds, so I've passed this to our refunds team.")),
            ])
            run_agent("refund", client=fc, verbose=False, tools=common.pick_tools("get_customer", "lookup_order"))
        finally:
            common.TOOL_FUNCTIONS["process_refund"] = real_fn
            common.as_tool_result = real_wrap
        block = fc.requests[1]["messages"][-1]["content"][0]
        payload = json.loads(block["content"])
        ok = (not calls and payload.get("errorCategory") == "permission"
              and payload.get("isRetryable") is False and payload.get("isError") is True)
        flag_ok = as_tool_result is None or block.get("is_error") is True
        return ok and flag_ok, ("Out-of-scope call: do not run it; return isError, errorCategory='permission', "
                                f"isRetryable=False (and is_error on the block). Backend calls: {len(calls)}, sent: {block}")

    run("out-of-scope tool -> structured permission error", t_permission)
    return out


# ------------------------------------------------------------------ TODO 7
def check_worker(worker):
    out = []
    run = _runner(out)
    alex = "alex.rivera@example.com"

    def call(email):
        return worker(email, **_with_sleep(worker))

    def t_complete():
        r = call(alex)
        ok = r.get("status") == "complete" and len(r.get("orders", [])) == 3 and not r.get("isError")
        return ok, f"No faults: status 'complete' with all 3 orders. Got: {r}"

    def t_partial():
        backend.inject_fault("lookup_order", "timeout", times=99, when={"order_id": "12400"})
        r = call(alex)
        fails = r.get("failures") or []
        f = fails[0] if fails else {}
        cov = r.get("coverage") or {}
        ok = (r.get("status") == "partial" and len(r.get("orders", [])) == 2 and len(fails) == 1
              and f.get("errorCategory") == "transient" and "12400" in str(f.get("attempted", ""))
              and f.get("isRetryable") is True and "12400" in cov.get("missing", []))
        return ok, ("One order keeps timing out: status 'partial', keep the 2 good orders, one failure with "
                    f"errorCategory, attempted, isRetryable, and coverage.missing. Got: {r}")

    def t_local_recovery():
        backend.inject_fault("lookup_order", "timeout", times=1, when={"order_id": "12400"})
        r = call(alex)
        return r.get("status") == "complete" and len(r.get("orders", [])) == 3, \
            f"A single timeout must be recovered inside the worker. Got: {r}"

    def t_valid_empty():
        r = call("sam.okafor@example.com")
        ok = r.get("status") == "complete" and r.get("orders") == [] and not r.get("isError")
        return ok, f"Sam has no orders: 'complete' with an empty list, NOT an error. Got: {r}"

    def t_customer_missing():
        r = call("nobody@example.com")
        ok = r.get("isError") is True and r.get("errorCategory") == "validation" and r.get("failures")
        return ok, f"Unknown customer: isError, errorCategory 'validation', and a failure record. Got: {r}"

    def t_customer_timeout():
        backend.inject_fault("get_customer", "timeout", times=99)
        r = call(alex)
        ok = r.get("isError") is True and r.get("errorCategory") == "transient" and r.get("isRetryable") is True
        return ok, f"Customer lookup keeps timing out: transient, retryable, and do not raise. Got: {r}"

    run("all orders retrieved -> complete", t_complete)
    run("one order fails -> partial with failure context + coverage", t_partial)
    run("single timeout recovered inside the worker", t_local_recovery)
    run("customer with no orders -> complete, not an error", t_valid_empty)
    run("unknown customer -> structured validation error", t_customer_missing)
    run("customer lookup timing out -> transient, not a crash", t_customer_timeout)
    return out


if __name__ == "__main__":
    import os
    import sys
    os.environ.setdefault("ANTHROPIC_API_KEY", "offline-test")
    from test_loop_offline import check_loop, report
    from test_tool_choice_offline import check_s3
    from solutions.tool_errors_ref import (as_tool_result, call_with_retry, run_tool_structured,
                                           structured_error)
    from solutions.order_history_ref import order_history_worker
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "solutions"))
    from agent_loop import run_agent  # solutions/agent_loop.py (Session 4 reference)

    results = []
    for title, res in [
        ("TODO 1 structured_error", check_structured_error(structured_error)),
        ("TODO 2 call_with_retry", check_retry(call_with_retry)),
        ("TODO 3 run_tool_structured", check_run_tool(run_tool_structured)),
        ("TODO 4 as_tool_result", check_tool_result(as_tool_result)),
        ("TODO 5 run_agent permission error", check_agent_permission(run_agent, as_tool_result)),
        ("TODO 7 order_history_worker", check_worker(order_history_worker)),
        ("Session 2 regression", check_loop(run_agent)),
        ("Session 3 regression", check_s3(run_agent)),
    ]:
        print(f"\n== {title}")
        results.append(report(res))
    sys.exit(0 if all(results) else 1)
