"""Step 4: complete one tool-use cycle by hand.

request -> tool_use -> run the tool -> tool_result -> final answer
"""
from common import MODEL, SYSTEM, TOOLS, as_tool_result, client, run_tool, show

messages = [{"role": "user", "content": "Where is order 12345?"}]

# Call 1: Claude decides it needs the tool.
first = client.messages.create(
    model=MODEL, max_tokens=1024, system=SYSTEM, tools=TOOLS, messages=messages
)
print("--- call 1 ---")
show(first)

tool_uses = [b for b in first.content if b.type == "tool_use"]
if first.stop_reason != "tool_use" or not tool_uses:
    raise SystemExit("Claude did not ask for a tool. Re-run, or check the prompt.")

# Your code runs the tool. Claude never does.
results = []
for tool_use in tool_uses:
    output = run_tool(tool_use.name, tool_use.input)
    print("\nYour code ran", tool_use.name, "->", output)
    results.append(as_tool_result(tool_use, output))

# Append TWO turns: the assistant's tool_use turn, then a user turn with the results.
messages.append({"role": "assistant", "content": first.content})
messages.append({"role": "user", "content": results})

# Call 2: the API is stateless, so we send the whole history again.
second = client.messages.create(
    model=MODEL, max_tokens=1024, system=SYSTEM, tools=TOOLS, messages=messages
)
print("\n--- call 2 ---")
show(second)
print("\nMessages sent on call 2:", len(messages))
