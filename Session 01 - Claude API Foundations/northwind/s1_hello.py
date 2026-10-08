"""Step 2: prove your API key works. No tools yet."""
from common import MODEL, SYSTEM, client

response = client.messages.create(
    model=MODEL,
    max_tokens=256,
    system=SYSTEM,
    messages=[{"role": "user", "content": "In one sentence, what does a support agent do?"}],
)

print("stop_reason:", response.stop_reason)
for block in response.content:
    print(block.type, "->", getattr(block, "text", ""))
print("usage:", response.usage.input_tokens, "in,", response.usage.output_tokens, "out")
