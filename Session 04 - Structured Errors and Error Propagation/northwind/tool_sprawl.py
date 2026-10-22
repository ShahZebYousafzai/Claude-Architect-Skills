"""Fourteen extra tools that a growing support team might bolt on (Session 3).

Used only to MEASURE selection with 18 tools vs 4. None of these are implemented:
the selection harness never executes tools. Several overlap on purpose, the way real
tool catalogs drift (get_order_status vs track_shipment, list_orders vs get_customer,
create_return_label vs process_refund).
"""


def _tool(name, description, **props):
    return {
        "name": name,
        "description": description,
        "input_schema": {
            "type": "object",
            "properties": {k: {"type": "string", "description": v} for k, v in props.items()},
        },
    }


SPRAWL_TOOLS = [
    _tool("get_order_status", "Gets the status of an order.", order_id="Order number"),
    _tool("list_orders", "Lists orders.", email="Customer email"),
    _tool("update_shipping_address", "Changes the address on an order.", order_id="Order number", address="New address"),
    _tool("cancel_order", "Cancels an order.", order_id="Order number"),
    _tool("apply_discount_code", "Applies a discount.", order_id="Order number", code="Discount code"),
    _tool("get_product_info", "Product information.", sku="Product SKU"),
    _tool("check_inventory", "Checks stock.", sku="Product SKU"),
    _tool("create_return_label", "Creates a return for an order.", order_id="Order number"),
    _tool("get_return_policy", "Returns policy text.", topic="Policy topic"),
    _tool("send_email", "Sends an email to the customer.", email="Recipient", body="Message"),
    _tool("add_order_note", "Adds a note to an order.", order_id="Order number", note="Note text"),
    _tool("get_loyalty_points", "Loyalty info.", customer_id="Customer ID"),
    _tool("search_knowledge_base", "Searches help articles.", query="Search text"),
    _tool("escalate_to_human", "Hands the conversation to a person.", summary="Case summary"),
]
