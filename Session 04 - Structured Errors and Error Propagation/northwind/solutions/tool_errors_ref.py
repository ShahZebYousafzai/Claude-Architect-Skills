"""Reference solution: the structured error layer (Session 4, TODOs 1 to 4).

Try the notebook exercise first. The last notebook cell writes YOUR functions (or these)
to northwind/tool_errors.py, and common.py then uses it automatically.

Design
------
The backend raises typed exceptions (errors.py). This layer, at the TOOL BOUNDARY,
turns each one into a payload Claude can reason about:

    {
      "isError": true,
      "errorCategory": "transient" | "validation" | "business" | "permission",
      "isRetryable": true | false,
      "message": "what went wrong and what to do next (written for the agent)",
      "customer_message": "safe wording for the customer (business/permission only)",
      "details": {...machine-readable context...}
    }

MCP defines only the isError flag on a tool result. errorCategory / isRetryable /
customer_message are OUR convention inside the content (the exam guide uses these
names). The Claude API equivalent of isError is "is_error": true on the tool_result
block, which as_tool_result sets below.
"""
import json
import time

import common
from errors import InvalidInput, NotFound, PermissionDenied, PolicyViolation, ServiceTimeout

CATEGORIES = ("transient", "validation", "business", "permission")
DEFAULT_RETRYABLE = {"transient": True, "validation": False, "business": False, "permission": False}


# ------------------------------------------------------------------ TODO 1
def structured_error(category, message, *, retryable=None, customer_message=None, **details):
    """Build one error payload. Retryable defaults by category (only transient is)."""
    if category not in CATEGORIES:
        raise ValueError(f"Unknown error category {category!r}; use one of {CATEGORIES}")
    payload = {
        "isError": True,
        "errorCategory": category,
        "isRetryable": DEFAULT_RETRYABLE[category] if retryable is None else bool(retryable),
        "message": message,
    }
    if customer_message:
        payload["customer_message"] = customer_message
    if details:
        payload["details"] = details
    return payload


def is_error(result):
    return isinstance(result, dict) and result.get("isError") is True


# ------------------------------------------------------------------ TODO 2
def call_with_retry(fn, tool_input, *, max_attempts=3, base_delay=0.2, sleep=time.sleep):
    """Call fn(**tool_input). Retry ONLY ServiceTimeout, with exponential backoff.

    Returns (result, attempts). Re-raises the last ServiceTimeout once attempts run out,
    and re-raises every other exception immediately (retrying a bad ID is pointless).
    """
    for attempt in range(1, max_attempts + 1):
        try:
            return fn(**tool_input), attempt
        except ServiceTimeout as exc:
            if attempt == max_attempts:
                exc.details["attempts"] = attempt
                raise
            sleep(base_delay * (2 ** (attempt - 1)))   # 0.2s, 0.4s, 0.8s ... (add jitter in production)


# ------------------------------------------------------------------ TODO 3
def run_tool_structured(name, tool_input, *, max_attempts=3, base_delay=0.2, sleep=time.sleep):
    """Run a tool and translate every failure into a structured error payload."""
    fn = common.TOOL_FUNCTIONS.get(name)
    if fn is None:
        return structured_error(
            "validation", f"There is no tool named '{name}'.",
            available_tools=sorted(common.TOOL_FUNCTIONS))
    try:
        result, _attempts = call_with_retry(fn, tool_input, max_attempts=max_attempts,
                                            base_delay=base_delay, sleep=sleep)
        return result                          # success, including VALID EMPTY results
    except ServiceTimeout as exc:
        attempts = exc.details.get("attempts", max_attempts)
        return structured_error(
            "transient",
            f"{exc.message}. Already retried {attempts} time(s) with backoff. Do not guess the data. "
            "Tell the customer there is a temporary problem looking this up and offer to try again "
            "in a few minutes.",
            attempts=attempts, retry_after_seconds=60, service=exc.details.get("service"))
    except InvalidInput as exc:
        return structured_error(
            "validation",
            f"{exc.message}. Fix the input if you can see the intended value; otherwise ask the "
            "customer for it. Do not retry the same input.",
            **exc.details)
    except NotFound as exc:
        hint = ("Ask the customer to check the number, or call get_customer with their email to "
                "list their real order IDs." if exc.details.get("resource") == "order"
                else "Ask the customer to check the email or ID they gave.")
        return structured_error("validation", f"{exc.message}. Do not retry with the same value. {hint}",
                                **exc.details)
    except PolicyViolation as exc:
        details = {k: v for k, v in exc.details.items()}
        return structured_error(
            "business",
            f"{exc.message}. This is a policy decision, not a failure: do not retry and do not work "
            "around it (for example by splitting the amount). Explain it to the customer using "
            "customer_message and offer the allowed alternative.",
            customer_message=exc.customer_message, **details)
    except PermissionDenied as exc:
        return structured_error(
            "permission",
            f"{exc.message}. You cannot do this. Do not retry. Tell the customer you are passing the "
            "request to a colleague who can, and escalate.",
            customer_message="I'm not able to do that myself, so I'm passing it to a colleague who can.",
            suggested_action="escalate_to_human", **exc.details)
    except TypeError as exc:
        # Claude sent arguments the function does not accept (wrong or missing parameter).
        return structured_error("validation", f"Bad arguments for {name}: {exc}. Check the tool's input schema.")


# ------------------------------------------------------------------ TODO 4
def as_tool_result(tool_use_block, result):
    """Wrap output for Claude. Set is_error so the API knows the call failed."""
    block = {
        "type": "tool_result",
        "tool_use_id": tool_use_block.id,
        "content": json.dumps(result),
    }
    if is_error(result):
        block["is_error"] = True
    return block


# common.py imports `run_tool` from this module when it exists.
def run_tool(name, tool_input):
    return run_tool_structured(name, tool_input)
