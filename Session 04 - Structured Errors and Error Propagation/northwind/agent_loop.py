"""The Northwind agentic loop as of the end of Session 3 (Session 4 starting state).

Session 3 adds three optional parameters, all backwards compatible with Session 2 calls:
  tools        a scoped toolset for this agent (least privilege). Default: every tool.
  system       a different system prompt. Default: common.SYSTEM.
  tool_choice  sent on the FIRST request only. Later requests fall back to "auto",
               so Claude can still finish with end_turn.

Session 4 change (already applied): tool results are wrapped with common.as_tool_result
looked up at call time, so the structured error layer can replace it.
"""
import common
from common import MODEL, SYSTEM, TOOLS, client as default_client

# A guard rail, NOT the termination condition. stop_reason decides when we are done.
MAX_ITERATIONS = 15


def run_agent(user_message, client=default_client, max_iterations=MAX_ITERATIONS, verbose=True,
              tools=None, system=None, tool_choice=None):
    """Run the loop until Claude says end_turn. Returns (final_text, messages)."""
    tools = TOOLS if tools is None else tools
    system = SYSTEM if system is None else system
    allowed = {t["name"] for t in tools}
    messages = [{"role": "user", "content": user_message}]

    for step in range(1, max_iterations + 1):
        request = dict(model=MODEL, max_tokens=1024, system=system, tools=tools, messages=messages)
        # Forced/any choice guarantees the FIRST call only. Forcing every turn would stop
        # Claude from ever answering (it could never reach end_turn).
        if tool_choice is not None and step == 1:
            request["tool_choice"] = tool_choice
        response = client.messages.create(**request)
        if verbose:
            print(f"[step {step}] stop_reason={response.stop_reason}")

        if response.stop_reason == "end_turn":
            final_text = "".join(b.text for b in response.content if b.type == "text")
            return final_text, messages + [{"role": "assistant", "content": response.content}]

        if response.stop_reason == "tool_use":
            # 1. The assistant turn, exactly as Claude produced it (text AND tool_use blocks).
            messages.append({"role": "assistant", "content": response.content})
            # 2. Run EVERY tool_use block. Claude may ask for several in one response.
            results = []
            for block in response.content:
                if block.type != "tool_use":
                    continue
                if block.name in allowed:
                    output = common.run_tool(block.name, block.input)
                else:
                    # Least privilege enforced in code too, not only by leaving the tool out.
                    output = {"error": f"Tool '{block.name}' is not available to this agent"}
                if verbose:
                    print(f"          tool {block.name}({block.input}) -> {str(output)[:80]}")
                results.append(common.as_tool_result(block, output))
            # 3. One user turn carrying all the tool_result blocks.
            messages.append({"role": "user", "content": results})
            continue

        # Any other stop_reason (max_tokens, refusal, ...) is not "done" and not "keep going".
        raise RuntimeError(f"Unhandled stop_reason: {response.stop_reason}")

    raise RuntimeError(f"Hit the {max_iterations}-iteration guard rail without end_turn")
