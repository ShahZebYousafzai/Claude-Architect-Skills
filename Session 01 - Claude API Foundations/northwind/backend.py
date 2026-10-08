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
}


def lookup_order(order_id: str) -> dict:
    """Return one order, or a simple error dict if it does not exist.

    Session 4 replaces this simple error with structured, categorized errors.
    """
    order = ORDERS.get(str(order_id).lstrip("#"))
    if order is None:
        return {"error": f"No order found with ID {order_id}"}
    return order
