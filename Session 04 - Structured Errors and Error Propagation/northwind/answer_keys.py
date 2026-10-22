"""Answer keys and reviewers for the Session 4 design exercises.

Do not open this file before you have answered. The notebook imports it only to
score what you wrote.
"""

# ---------------------------------------------------------------- Exercise A
# What a good payload for each case MUST get right. Wording is yours; these are not.
DESIGN_RULES = {
    "timeout": {
        "errorCategory": "transient", "isRetryable": True, "customer_message": False,
        "detail_any": ("attempts", "retry_after_seconds", "timeout_seconds"),
        "why": "Same call may work in a moment. Say how many attempts were made and when to try again.",
    },
    "bad_order_id": {
        "errorCategory": "validation", "isRetryable": False, "customer_message": False,
        "detail_any": ("field", "expected", "example", "received", "id"),
        "why": "Retrying the same ID never helps. Say which field, what format, and the next step (ask, or get_customer).",
    },
    "refund_over_limit": {
        "errorCategory": "business", "isRetryable": False, "customer_message": True,
        "detail_any": ("code", "limit", "amount_requested", "suggested_action"),
        "why": "Policy, not failure. retriable: false plus a customer-friendly explanation and the allowed alternative.",
    },
    "no_permission": {
        "errorCategory": "permission", "isRetryable": False, "customer_message": True,
        "detail_any": ("suggested_action", "required_scope", "allowed_tools", "tool"),
        "why": "This agent may not do it. Hand off or escalate; never retry.",
    },
}

GENERIC = ("operation failed", "error occurred", "something went wrong", "failed", "todo")


def review_design(design):
    """Print a verdict per case for the four payloads you designed in Exercise A."""
    all_ok = True
    for case, rule in DESIGN_RULES.items():
        p = design.get(case) or {}
        problems = []
        if p.get("isError") is not True:
            problems.append("isError must be True")
        if p.get("errorCategory") != rule["errorCategory"]:
            problems.append(f"errorCategory should be '{rule['errorCategory']}' (you: {p.get('errorCategory')!r})")
        if p.get("isRetryable") is not rule["isRetryable"]:
            problems.append(f"isRetryable should be {rule['isRetryable']}")
        msg = str(p.get("message", "")).strip()
        if len(msg) < 25 or msg.lower() in GENERIC:
            problems.append("message is too short or generic: say what happened AND what to do next")
        if rule["customer_message"] and not p.get("customer_message"):
            problems.append("needs a customer_message (safe wording the agent can pass on)")
        details = p.get("details") or {}
        if not any(k in details for k in rule["detail_any"]):
            problems.append(f"details should carry context, e.g. one of {rule['detail_any']}")
        ok = not problems
        all_ok &= ok
        print(f"{'ok  ' if ok else 'FIX '} {case:<18} {rule['why']}")
        for pr in problems:
            print(f"        - {pr}")
    return all_ok


# ---------------------------------------------------------------- Exercise B
# Vocabulary: local | ask | not-error | explain | handoff | later
EX_B_KEY = {
    1: ("local",     "Timed out once, worked on the second try: recovered inside the tool layer. Claude never sees it."),
    2: ("ask",       "Order 99999 does not exist (validation). Ask the customer to check it, or list their orders with get_customer."),
    3: ("not-error", "' #12345 ' is the right order with extra characters. The backend normalises it: plain success."),
    4: ("explain",   "Refund above the $500 limit (business). Explain with customer_message, route for approval. Never split it."),
    5: ("handoff",   "The status agent has no refund tool (permission). Hand off to the refunds team; do not retry."),
    6: ("not-error", "Sam has no orders: a VALID EMPTY result. Tell him so; this is not a failure."),
    7: ("not-error", "Order 12399 is still processing, so no tracking number yet. A normal result."),
    8: ("later",     "Timed out on all 3 attempts (transient, unresolved). Say it's temporary, offer to try again later, never guess."),
}


def review_ex_b(answers):
    score = 0
    for i, (want, why) in EX_B_KEY.items():
        got = str(answers.get(i, "")).strip().lower()
        ok = got == want
        score += ok
        print(f"{i}. {'ok  ' if ok else 'MISS'} you: {got or '-':<10} key: {want:<10} {why}")
    print(f"\n{score}/{len(EX_B_KEY)}")
    return score
