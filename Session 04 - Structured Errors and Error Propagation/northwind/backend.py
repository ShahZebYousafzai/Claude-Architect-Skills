"""Mock Northwind Outfitters backend (Session 4 version).

What changed in Session 4
-------------------------
Until Session 3 every function returned a plain {"error": "..."} dict. A real order
system raises exceptions instead, so from now on this backend does too (see errors.py):

    lookup_order("99999")    -> NotFound          lookup_order("12-34") -> InvalidInput
    process_refund(...649)   -> PolicyViolation   (above the $500 automatic-refund limit)
    any tool, when a fault is injected -> ServiceTimeout or PermissionDenied

Turning those exceptions into something Claude can act on is the job of the TOOL
LAYER you build in the notebook, not of the backend.

Fault injection
---------------
Real outages are hard to reproduce on demand, so tests inject them:

    inject_fault("track_shipment", "timeout", times=1)                  # next call times out
    inject_fault("lookup_order", "timeout", times=99, when={"order_id": "12400"})
    inject_fault("process_refund", "permission")                        # credential lacks scope
    clear_faults()
"""
import re

from errors import InvalidInput, NotFound, PermissionDenied, PolicyViolation, ServiceTimeout

# Payments rule: refunds above this amount need a human approver (Session 6 adds a hook
# that blocks them BEFORE the call; today the payments service rejects them AFTER).
AUTO_REFUND_LIMIT = 500.00

ORDER_ID_PATTERN = re.compile(r"^\d{5}$")

ORDERS = {
    "12345": {
        "order_id": "12345",
        "customer_id": "C-1001",
        "status": "shipped",
        "carrier": "SwiftShip",
        "tracking_number": "SS-9081-4472",
        "estimated_delivery": "2026-10-02",
        "items": [{"sku": "TENT-2P", "name": "Trailhead 2-person tent", "qty": 1, "price": 249.00}],
        "total": 249.00,
        "currency": "USD",
    },
    "12399": {
        "order_id": "12399",
        "customer_id": "C-1002",
        "status": "processing",
        "carrier": None,
        "tracking_number": None,
        "estimated_delivery": None,
        "items": [{"sku": "STOVE-1", "name": "Ridge pocket stove", "qty": 2, "price": 39.50}],
        "total": 79.00,
        "currency": "USD",
    },
    "12400": {
        "order_id": "12400",
        "customer_id": "C-1001",
        "status": "delivered",
        "carrier": "SwiftShip",
        "tracking_number": "SS-7731-0058",
        "estimated_delivery": "2026-09-20",
        "items": [{"sku": "LANTERN-LED", "name": "Basecamp LED lantern", "qty": 1, "price": 34.00}],
        "total": 34.00,
        "currency": "USD",
    },
    # Session 4: an order large enough to hit the automatic-refund limit.
    "12455": {
        "order_id": "12455",
        "customer_id": "C-1001",
        "status": "delivered",
        "carrier": "SwiftShip",
        "tracking_number": "SS-5520-1934",
        "estimated_delivery": "2026-10-09",
        "items": [{"sku": "TENT-4S", "name": "Summit 4-season expedition tent", "qty": 1, "price": 649.00}],
        "total": 649.00,
        "currency": "USD",
    },
}

CUSTOMERS = {
    "C-1001": {
        "customer_id": "C-1001",
        "name": "Alex Rivera",
        "email": "alex.rivera@example.com",
        "tier": "gold",
        "order_ids": ["12345", "12400", "12455"],
    },
    "C-1002": {
        "customer_id": "C-1002",
        "name": "Priya Nair",
        "email": "priya.nair@example.com",
        "tier": "standard",
        "order_ids": ["12399"],
    },
    # Session 4: a real account with NO orders. Looking him up must succeed with an
    # empty list. "No orders" is a valid answer, not an error.
    "C-1003": {
        "customer_id": "C-1003",
        "name": "Sam Okafor",
        "email": "sam.okafor@example.com",
        "tier": "standard",
        "order_ids": [],
    },
}


# ---------------------------------------------------------------- fault injection
FAULTS = []


def inject_fault(tool, kind="timeout", times=1, when=None):
    """Make the next `times` calls to `tool` fail. kind: 'timeout' or 'permission'.
    `when` limits the fault to calls whose arguments match, e.g. {"order_id": "12400"}."""
    if kind not in ("timeout", "permission"):
        raise ValueError("kind must be 'timeout' or 'permission'")
    FAULTS.append({"tool": tool, "kind": kind, "remaining": times, "when": when or {}})


def clear_faults():
    FAULTS.clear()


def _maybe_fail(tool, **args):
    for fault in FAULTS:
        if fault["tool"] != tool or fault["remaining"] <= 0:
            continue
        if any(str(args.get(k)) != str(v) for k, v in fault["when"].items()):
            continue
        fault["remaining"] -= 1
        if fault["kind"] == "timeout":
            raise ServiceTimeout(f"{tool}: the order service did not respond within 5 seconds",
                                 service="order-service", timeout_seconds=5)
        raise PermissionDenied(f"{tool}: the service credential lacks the scope for this action",
                               required_scope="refunds:write")


# ---------------------------------------------------------------- helpers
def _clean_order_id(order_id):
    """Accept '12345', ' #12345 '. Anything else is the caller's mistake, said precisely."""
    cleaned = str(order_id).strip().lstrip("#")
    if not ORDER_ID_PATTERN.match(cleaned):
        raise InvalidInput(f"'{order_id}' is not a valid order number",
                           field="order_id", received=str(order_id),
                           expected="5 digits, optionally with a leading '#'", example="12345")
    return cleaned


def _get_order(order_id):
    cleaned = _clean_order_id(order_id)
    order = ORDERS.get(cleaned)
    if order is None:
        raise NotFound(f"No order with number {cleaned} exists", resource="order", id=cleaned)
    return order


# ---------------------------------------------------------------- tools
def lookup_order(order_id: str) -> dict:
    """Full order record: items, prices, total, status, owner, shipping fields."""
    _maybe_fail("lookup_order", order_id=order_id)
    return dict(_get_order(order_id))


def get_customer(email: str = None, customer_id: str = None) -> dict:
    """Customer account by email or customer ID. order_ids may be an empty list."""
    _maybe_fail("get_customer", email=email, customer_id=customer_id)
    if not email and not customer_id:
        raise InvalidInput("Provide an email or a customer_id",
                           field="email|customer_id", expected="one of the two", example="alex.rivera@example.com")
    if customer_id:
        customer = CUSTOMERS.get(customer_id)
        key = customer_id
    else:
        customer = next((c for c in CUSTOMERS.values() if c["email"].lower() == email.strip().lower()), None)
        key = email
    if customer is None:
        raise NotFound(f"No customer account matches {key}", resource="customer", id=key)
    return dict(customer)


def track_shipment(order_id: str) -> dict:
    """Shipping status. An order still 'processing' has no carrier yet: a normal result."""
    _maybe_fail("track_shipment", order_id=order_id)
    order = _get_order(order_id)
    return {
        "order_id": order["order_id"],
        "status": order["status"],
        "carrier": order["carrier"],
        "tracking_number": order["tracking_number"],
        "estimated_delivery": order["estimated_delivery"],
    }


def process_refund(order_id: str, amount: float, reason: str) -> dict:
    """Issue a refund. Enforces two payments rules as BUSINESS errors."""
    _maybe_fail("process_refund", order_id=order_id)
    order = _get_order(order_id)
    try:
        amount = round(float(amount), 2)
    except (TypeError, ValueError):
        raise InvalidInput(f"'{amount}' is not a number", field="amount", expected="a positive number", example="34.00")
    if amount <= 0:
        raise InvalidInput("Refund amount must be positive", field="amount", received=amount,
                           expected="a positive number", example="34.00")
    if amount > order["total"]:
        raise PolicyViolation(
            f"Refund of {amount:.2f} exceeds the {order['total']:.2f} paid for order {order['order_id']}",
            code="REFUND_EXCEEDS_PAID", amount_requested=amount, amount_paid=order["total"],
            customer_message=f"We can refund at most the {order['total']:.2f} {order['currency']} "
                             f"you paid for this order.")
    if amount > AUTO_REFUND_LIMIT:
        raise PolicyViolation(
            f"Refund of {amount:.2f} is above the {AUTO_REFUND_LIMIT:.2f} automatic-refund limit",
            code="REFUND_ABOVE_AUTO_LIMIT", amount_requested=amount, limit=AUTO_REFUND_LIMIT,
            suggested_action="escalate_to_human",
            customer_message="Refunds of this size need approval from a member of our team. "
                             "I've passed your request on and someone will confirm within one business day.")
    return {
        "refund_id": f"R-{order['order_id']}-1",
        "order_id": order["order_id"],
        "amount": amount,
        "currency": order["currency"],
        "reason": reason,
        "status": "issued",
    }


def get_order_details(order_id: str) -> dict:
    """Session 3 option B (rename + narrow): items and totals, no shipping fields."""
    order = lookup_order(order_id)
    shipping = {"carrier", "tracking_number", "estimated_delivery"}
    return {k: v for k, v in order.items() if k not in shipping}
