"""Reference tool definitions for Session 3. Try the notebook exercise first.

TOOLS_IMPROVED  option A: same four names, differentiated descriptions.
TOOLS_RENAMED   option B: lookup_order renamed to get_order_details and narrowed so it
                no longer returns shipping data (backend.get_order_details).

Each description follows the official guidance: what the tool does, when to use it,
when NOT to use it (and which tool to use instead), what each input means and its
format, what it returns, and edge cases.
"""

LOOKUP_ORDER = {
    "name": "lookup_order",
    "description": (
        "Retrieves the full record of one order: items purchased (name, SKU, quantity, unit price), "
        "order total and currency, order status, and the customer ID that owns it. "
        "Use it for questions about WHAT was bought or HOW MUCH was paid, and before any refund, "
        "to confirm the item and its price. "
        "For questions about delivery progress, tracking numbers, carriers or arrival dates, "
        "use track_shipment instead. "
        "Requires an order number. If the customer has not given one, do not guess: "
        "call get_customer with their email to find their order IDs, or ask them. "
        "Example requests: 'What did I order in 12400?', 'How much was order 12399?'. "
        "Returns an error if no order has that number."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "order_id": {
                "type": "string",
                "description": "Northwind order number: 5 digits, e.g. '12345'. A leading '#' is accepted.",
            },
        },
        "required": ["order_id"],
    },
}

GET_CUSTOMER = {
    "name": "get_customer",
    "description": (
        "Finds a customer account by email address or customer ID and returns their name, "
        "loyalty tier, and the list of their order IDs. "
        "Use it first whenever the customer identifies themselves by email but has not given an "
        "order number (for example 'I'm alex@example.com, where is my tent?'), or when you need "
        "to confirm who owns an order. "
        "It does not return order contents or shipping status: follow up with lookup_order or "
        "track_shipment using the order IDs it returns. "
        "Provide email OR customer_id; email matching is case-insensitive. "
        "Returns an error if no account matches."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "email": {"type": "string", "description": "Customer email address, e.g. 'priya.nair@example.com'"},
            "customer_id": {"type": "string", "description": "Customer ID in the form C-1234, e.g. 'C-1001'"},
        },
    },
}

TRACK_SHIPMENT = {
    "name": "track_shipment",
    "description": (
        "Returns the shipping status of one order: status (processing, shipped, delivered), "
        "carrier, tracking number and estimated or actual delivery date. "
        "Use it for any question about where an order is, whether it has shipped or 'gone out', "
        "when it will arrive, whether it was delivered, or what the tracking number is. "
        "It does not return items or prices: use lookup_order for those. "
        "An order still in 'processing' has no carrier or tracking number yet; that is a normal "
        "result, not an error. "
        "Requires an order number; if you only have an email, call get_customer first."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "order_id": {
                "type": "string",
                "description": "Northwind order number: 5 digits, e.g. '12345'. A leading '#' is accepted.",
            },
        },
        "required": ["order_id"],
    },
}

PROCESS_REFUND = {
    "name": "process_refund",
    "description": (
        "Issues a refund to the customer's original payment method. This moves money and cannot be undone. "
        "Only call it after lookup_order has confirmed the order exists and you know the price of the "
        "item being refunded, and after the customer has said which item and why. "
        "Never guess the amount and never refund more than the order total. "
        "Do not use it to answer questions about refund policy or to check refund status. "
        "Returns the refund ID and status."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "order_id": {"type": "string", "description": "Order number confirmed with lookup_order, e.g. '12399'"},
            "amount": {
                "type": "number",
                "description": "Refund amount in the order's currency, taken from the item price returned by "
                               "lookup_order. Must not exceed the order total.",
            },
            "reason": {
                "type": "string",
                "description": "Short reason in the customer's terms, e.g. 'arrived broken', 'too dim'.",
            },
        },
        "required": ["order_id", "amount", "reason"],
    },
}

TOOLS_IMPROVED = [LOOKUP_ORDER, GET_CUSTOMER, TRACK_SHIPMENT, PROCESS_REFUND]


# --- Option B: rename + narrow. The overlap is removed at the interface, not only in prose.
GET_ORDER_DETAILS = {
    **LOOKUP_ORDER,
    "name": "get_order_details",
    "description": (
        "Returns what was bought and paid in one order: items (name, SKU, quantity, unit price), "
        "order total, currency, order status and owning customer ID. It contains NO shipping data. "
        "Use it for questions about contents or cost, and before any refund to confirm the price. "
        "For delivery, tracking or arrival questions use track_shipment. "
        "Requires an order number; with only an email, call get_customer first. "
        "Returns an error if no order has that number."
    ),
}

def _renamed(tool):
    """Copy of a tool whose description points at get_order_details instead of lookup_order."""
    return {**tool, "description": tool["description"].replace("lookup_order", "get_order_details")}


TOOLS_RENAMED = [GET_ORDER_DETAILS, _renamed(GET_CUSTOMER), _renamed(TRACK_SHIPMENT), _renamed(PROCESS_REFUND)]


# --- System prompts for the keyword-override experiment
SYSTEM_BASE = (
    "You are a customer support agent for Northwind Outfitters, "
    "an online camping-gear store. Be concise and friendly."
)

# The trap: a well-meant rule written months ago, naming a tool by keyword.
SYSTEM_KEYWORD = SYSTEM_BASE + (
    " Whenever a customer mentions an order, always use lookup_order first."
)

# The fix: state the goal and leave tool choice to the (now good) descriptions.
SYSTEM_FIXED = SYSTEM_BASE + (
    " Use the tools to check facts before answering; never guess order numbers, amounts or dates."
    " If the customer has not given an order number or email, ask for one."
)
