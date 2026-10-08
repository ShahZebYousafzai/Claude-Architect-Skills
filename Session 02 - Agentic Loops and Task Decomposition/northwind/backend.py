"""Mock Northwind Outfitters backend.

In a real deployment these functions would call your order system.
Here they read from an in-memory dictionary so the exercise runs anywhere.
"""

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
}

# Session 2: customers. get_customer returns the order IDs so the agent can chain
# get_customer -> lookup_order without the customer knowing an order number.
CUSTOMERS = {
    "C-1001": {
        "customer_id": "C-1001",
        "name": "Alex Rivera",
        "email": "alex.rivera@example.com",
        "tier": "gold",
        "order_ids": ["12345", "12400"],
    },
    "C-1002": {
        "customer_id": "C-1002",
        "name": "Priya Nair",
        "email": "priya.nair@example.com",
        "tier": "standard",
        "order_ids": ["12399"],
    },
}


def lookup_order(order_id: str) -> dict:
    """Return one order, or a simple error dict if it does not exist.

    Session 4 replaces this simple error with structured, categorized errors.
    """
    order = ORDERS.get(str(order_id).lstrip("#"))
    if order is None:
        return {"error": f"No order found with ID {order_id}"}
    return order


def get_customer(email: str = None, customer_id: str = None) -> dict:
    """Find a customer by email or customer ID.

    Session 4 replaces the simple error dict with structured errors.
    """
    if customer_id:
        customer = CUSTOMERS.get(customer_id)
    elif email:
        customer = next(
            (c for c in CUSTOMERS.values() if c["email"].lower() == email.lower()), None
        )
    else:
        return {"error": "Provide an email or a customer_id"}
    if customer is None:
        return {"error": "No customer found"}
    return customer


# --- Homework helpers (Exercise 1). You write the tool definitions; the
# --- backend functions are provided so you can focus on the interface.

def track_shipment(order_id: str) -> dict:
    """Return shipping status for an order. Overlaps with lookup_order on purpose."""
    order = ORDERS.get(str(order_id).lstrip("#"))
    if order is None:
        return {"error": f"No order found with ID {order_id}"}
    return {
        "order_id": order["order_id"],
        "status": order["status"],
        "carrier": order["carrier"],
        "tracking_number": order["tracking_number"],
        "estimated_delivery": order["estimated_delivery"],
    }


def process_refund(order_id: str, amount: float, reason: str) -> dict:
    """Issue a refund. No limit check yet: Sessions 4 and 6 add business errors and a hook."""
    order = ORDERS.get(str(order_id).lstrip("#"))
    if order is None:
        return {"error": f"No order found with ID {order_id}"}
    return {
        "refund_id": f"R-{order['order_id']}-1",
        "order_id": order["order_id"],
        "amount": amount,
        "currency": order["currency"],
        "reason": reason,
        "status": "issued",
    }
