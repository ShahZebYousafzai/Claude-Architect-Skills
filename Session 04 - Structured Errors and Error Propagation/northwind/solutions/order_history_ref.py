"""Reference solution: the order-history worker with proper error propagation (TODO 7).

Rules it follows (task statement 5.3):
1. Recover locally from transient failures (bounded retry inside the worker).
2. Keep going after an unresolved failure on one order: partial results are valuable.
3. Propagate only what is still unresolved, WITH context: failure type, what was
   attempted, how many attempts, whether a retry later could help, alternatives.
4. Never mark a failure as an empty success, and never treat a valid empty result
   (a customer with no orders) as a failure.
5. Annotate coverage so the coordinator can say what it could and could not check.
"""
import time

from backend import get_customer, lookup_order
from errors import NorthwindError, ServiceTimeout

try:                                    # your saved layer, if the notebook wrote it
    from tool_errors import call_with_retry
except ImportError:                     # otherwise the reference
    from solutions.tool_errors_ref import call_with_retry

CATEGORY_OF = {
    "ServiceTimeout": "transient",
    "InvalidInput": "validation",
    "NotFound": "validation",
    "PolicyViolation": "business",
    "PermissionDenied": "permission",
}


def _failure(attempted, exc, attempts):
    category = CATEGORY_OF.get(type(exc).__name__, "transient")
    return {
        "attempted": attempted,
        "errorCategory": category,
        "isRetryable": category == "transient",
        "attempts": attempts,
        "message": getattr(exc, "message", str(exc)),
    }


def order_history_worker(email, *, max_attempts=3, base_delay=0.2, sleep=time.sleep):
    # 1. Who is the customer? Without this nothing else can run, so a failure here is total.
    try:
        customer, _ = call_with_retry(get_customer, {"email": email}, max_attempts=max_attempts,
                                      base_delay=base_delay, sleep=sleep)
    except NorthwindError as exc:
        attempts = exc.details.get("attempts", 1) if isinstance(exc, ServiceTimeout) else 1
        failure = _failure(f"get_customer(email='{email}')", exc, attempts)
        return {
            "isError": True,
            "errorCategory": failure["errorCategory"],
            "isRetryable": failure["isRetryable"],
            "status": "failed",
            "message": "Could not identify the customer, so no orders were checked.",
            "failures": [failure],
            "orders": [],
            "alternatives": (["Try again in a few minutes"] if failure["isRetryable"]
                             else ["Ask the customer to confirm their email address"]),
        }

    # 2. Every order, independently. One failure must not discard the others.
    orders, failures = [], []
    for order_id in customer["order_ids"]:
        try:
            order, _ = call_with_retry(lookup_order, {"order_id": order_id}, max_attempts=max_attempts,
                                       base_delay=base_delay, sleep=sleep)
            orders.append({
                "order_id": order["order_id"],
                "status": order["status"],
                "items": [i["name"] for i in order["items"]],
                "total": order["total"],
                "currency": order["currency"],
            })
        except NorthwindError as exc:
            attempts = exc.details.get("attempts", 1) if isinstance(exc, ServiceTimeout) else 1
            failure = _failure(f"lookup_order(order_id='{order_id}')", exc, attempts)
            failure["order_id"] = order_id
            failures.append(failure)

    # 3. Status + coverage. Zero orders on the account is COMPLETE, not an error.
    missing = [f["order_id"] for f in failures]
    report = {
        "status": "partial" if failures else "complete",
        "customer_id": customer["customer_id"],
        "orders": orders,
        "coverage": {
            "orders_on_account": len(customer["order_ids"]),
            "retrieved": len(orders),
            "missing": missing,
        },
    }
    if not customer["order_ids"]:
        report["note"] = "The customer has no orders. This is a valid empty result, not an error."
    if failures:
        report["failures"] = failures
        report["alternatives"] = [
            "Tell the customer which orders could not be checked right now",
            "Retry the missing orders in a few minutes" if any(f["isRetryable"] for f in failures)
            else "Ask the customer about the missing orders",
            "If the customer only cares about one order, look it up directly with lookup_order",
        ]
    return report
