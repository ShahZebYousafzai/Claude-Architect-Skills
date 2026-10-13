"""Step 3: one request with one tool. Look at what comes back. Do not run the tool yet."""
from common import MODEL, SYSTEM, TOOLS, client, show

messages = [{"role": "user", "content": "Where is order 12345?"}]

response = client.messages.create(
    model=MODEL,
    max_tokens=1024,
    system=SYSTEM,
    tools=TOOLS,
    messages=messages,
)

show(response)
