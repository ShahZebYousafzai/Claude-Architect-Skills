"""A scripted stand-in for the Anthropic client, for deterministic loop tests.

Why: a live model only sometimes writes text before a tool call, so a loop bug that
depends on that is intermittent. A script makes the bug reproducible every time.
"""
from types import SimpleNamespace as NS


def text(t):
    return NS(type="text", text=t)


def tool_use(id, name, **tool_input):
    return NS(type="tool_use", id=id, name=name, input=tool_input)


def reply(stop_reason, *blocks):
    return NS(stop_reason=stop_reason, content=list(blocks))


class FakeClient:
    """client.messages.create(...) returns the scripted replies in order and records requests."""

    def __init__(self, script):
        self._script = list(script)
        self.requests = []
        self.messages = self

    def create(self, **kwargs):
        # Snapshot the history as sent (lists are mutated by the loop afterwards).
        kwargs["messages"] = [dict(m) for m in kwargs["messages"]]
        self.requests.append(kwargs)
        if not self._script:
            raise AssertionError("Loop asked for more responses than the script has")
        return self._script.pop(0)


def chained_script():
    """Claude says something AND calls a tool, then calls a second tool, then answers."""
    return [
        reply("tool_use",
              text("Let me look up your account first."),
              tool_use("toolu_1", "get_customer", email="alex.rivera@example.com")),
        reply("tool_use", tool_use("toolu_2", "lookup_order", order_id="12345")),
        reply("end_turn", text("Your tent (order 12345) shipped with SwiftShip and arrives 2026-10-02.")),
    ]
