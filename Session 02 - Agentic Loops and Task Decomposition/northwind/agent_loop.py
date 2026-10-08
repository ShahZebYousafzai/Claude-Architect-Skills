"""Reference solution: the Northwind agentic loop (Session 2, Exercise 1).

Copy to northwind/agent_loop.py once you have tried the notebook exercise yourself.
Later sessions import run_agent from here and extend it.
"""
from common import MODEL, SYSTEM, TOOLS, as_tool_result, client as default_client, run_tool

# A guard rail, NOT the termination condition. stop_reason decides when we are done.
MAX_ITERATIONS = 15


def run_agent(user_message, client=default_client, max_iterations=MAX_ITERATIONS, verbose=True):
    """Run the loop until Claude says end_turn. Returns (final_text, messages)."""
    messages = [{"role": "user", "content": user_message}]

    for step in range(1, max_iterations + 1):
        response = client.messages.create(
            model=MODEL, max_tokens=1024, system=SYSTEM, tools=TOOLS, messages=messages
        )
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
                if block.type == "tool_use":
                    output = run_tool(block.name, block.input)
                    if verbose:
                        print(f"          tool {block.name}({block.input}) -> {str(output)[:80]}")
                    results.append(as_tool_result(block, output))
            # 3. One user turn carrying all the tool_result blocks.
            messages.append({"role": "user", "content": results})
            continue

        # Any other stop_reason (max_tokens, refusal, ...) is not "done" and not "keep going".
        raise RuntimeError(f"Unhandled stop_reason: {response.stop_reason}")

    raise RuntimeError(f"Hit the {max_iterations}-iteration guard rail without end_turn")
