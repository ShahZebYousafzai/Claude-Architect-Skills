"""Ambiguous support requests for measuring tool SELECTION (Session 3).

Each case lists the acceptable FIRST tool(s). "(none)" means the right first move is
to answer or ask a question without calling any tool.

Backend facts these cases rely on: orders 12345 (tent, shipped) and 12400 (lantern,
delivered) belong to alex.rivera@example.com; 12399 (2 stoves, processing) belongs
to priya.nair@example.com.
"""

NONE = "(none)"

CASES = [
    # --- shipping questions: overlap zone between lookup_order and track_shipment
    {"id": "S1", "request": "Is order 12345 on its way? When will it get here?",
     "expect": {"track_shipment"},
     "why": "Delivery date and progress are shipping questions."},
    {"id": "S2", "request": "Can I get the tracking number for 12345?",
     "expect": {"track_shipment"},
     "why": "Tracking number is shipping data."},
    {"id": "S3", "request": "Has 12399 gone out yet?",
     "expect": {"track_shipment"},
     "why": "'Gone out' means shipped. Colloquial wording is where thin descriptions break."},
    {"id": "S4", "request": "Did my lantern arrive? Order 12400.",
     "expect": {"track_shipment"},
     "why": "Delivery confirmation is shipping data."},

    # --- order content and money questions
    {"id": "O1", "request": "What exactly did I buy in order 12400?",
     "expect": {"lookup_order"},
     "why": "Items purchased are order details, not shipping."},
    {"id": "O2", "request": "How much did I pay for order 12399?",
     "expect": {"lookup_order"},
     "why": "Totals and prices are order details."},
    {"id": "O3", "request": "Order 12345: which carrier is it with, and what was the total?",
     "expect": {"lookup_order", "track_shipment"},
     "why": "Two concerns. lookup_order covers both; track_shipment plus lookup_order also works."},

    # --- identity first: the customer gives an email, not an order number
    {"id": "C1", "request": "I'm priya.nair@example.com. Which orders do I have with you?",
     "expect": {"get_customer"},
     "why": "Only the customer record lists their order IDs."},
    {"id": "C2", "request": "alex.rivera@example.com here. Where is my tent?",
     "expect": {"get_customer"},
     "why": "No order ID yet, so find the customer first."},

    # --- refunds: the risky tool
    {"id": "R1", "request": "The stove from order 12399 arrived broken. I want my money back.",
     "expect": {"lookup_order"},
     "why": "Check the order and the price before refunding. Calling process_refund first means guessing the amount."},
    {"id": "R2", "request": "I want to return the lantern, it's too dim.",
     "expect": {NONE},
     "why": "No order ID and no email. Ask for an identifier instead of guessing one."},

    # --- no tool needed
    {"id": "N1", "request": "Do you sell sleeping bags for kids?",
     "expect": {NONE},
     "why": "No tool covers the product catalog. Answer or say you can't check, don't misuse an order tool."},
]

# Cases whose intended tool still exists when 14 extra tools are added (tool_sprawl.py).
# N1 and R2 are left out (with 18 tools, get_product_info or create_return_label could be fair
# picks), and O3 because two tools are already acceptable there.
SPRAWL_CASES = [c for c in CASES if c["id"] not in {"N1", "R2", "O3"}]
SHIPPING_IDS = {"S1", "S2", "S3", "S4"}
