"""Errors across agents (Session 4, task statement 5.3).

`get_order_history` is a tool the main support agent (the COORDINATOR) can call. Behind
it sits a WORKER that does many backend calls on its own: look up the customer, then
look up every order. In Session 5 this worker becomes a real Claude subagent; today it
is plain Python so that we can focus on one question:

    When part of the worker's job fails, what should reach the coordinator?

This file gives you the tool definition and three workers that answer that question
BADLY. You write the good one (TODO 7) in the notebook.

    use_worker(worker_silent_empty)   # register a worker as get_order_history
"""
import common
from backend import get_customer, lookup_order

ORDER_HISTORY_TOOL = {
    "name": "get_order_history",
    "description": (
        "Summarises every order on a customer's account in one call: for each order, the items, "
        "total, currency and status. Use it when the customer asks about all of their orders, "
        "their order history, or 'everything I've bought'. For one specific order use lookup_order "
        "or track_shipment instead. "
        "The result has a status: 'complete', or 'partial' when some orders could not be retrieved; "
        "in that case 'coverage' and 'failures' say which orders are missing and why, and you must "
        "tell the customer which orders you could not check rather than presenting a partial list "
        "as complete. Requires the customer's email address."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "email": {"type": "string", "description": "Customer email address, e.g. 'alex.rivera@example.com'"},
        },
        "required": ["email"],
    },
}


def _summary(order):
    return {
        "order_id": order["order_id"],
        "status": order["status"],
        "items": [i["name"] for i in order["items"]],
        "total": order["total"],
        "currency": order["currency"],
    }


# --------------------------------------------------------------------------------------
# Anti-pattern 1: SUPPRESSION. Any failure becomes an empty list marked as success.
# The coordinator cannot tell "this customer has no orders" from "the service was down".
def worker_silent_empty(email):
    try:
        customer = get_customer(email=email)
        return {"status": "ok", "orders": [_summary(lookup_order(o)) for o in customer["order_ids"]]}
    except Exception:  # noqa: BLE001
        return {"status": "ok", "orders": []}


# --------------------------------------------------------------------------------------
# Anti-pattern 2: GENERIC STATUS. The failure is reported, but with no context: no type,
# no record of what was attempted, and the orders that DID load are thrown away.
def worker_generic_status(email):
    try:
        customer = get_customer(email=email)
        return {"status": "ok", "orders": [_summary(lookup_order(o)) for o in customer["order_ids"]]}
    except Exception:  # noqa: BLE001
        return {"status": "error", "message": "Order history unavailable"}


# --------------------------------------------------------------------------------------
# Anti-pattern 3: NO HANDLING. One timeout on one order raises out of the worker. If the
# coordinator calls it directly, the whole workflow dies, including the orders that worked.
def worker_crash(email):
    customer = get_customer(email=email)
    return {"status": "ok", "orders": [_summary(lookup_order(o)) for o in customer["order_ids"]]}


def use_worker(worker):
    """Register `worker` as the implementation of the get_order_history tool."""
    common.TOOL_FUNCTIONS["get_order_history"] = worker
    return worker
