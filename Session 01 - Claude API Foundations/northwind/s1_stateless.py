"""Step 5: see statelessness for yourself. No tools needed."""
from common import MODEL, SYSTEM, client


def ask(messages):
    response = client.messages.create(
        model=MODEL, max_tokens=200, system=SYSTEM, messages=messages
    )
    return response.content[0].text


first_turn = {"role": "user", "content": "Hi, I bought a tent, order 12345."}
follow_up = {"role": "user", "content": "Which order did I just mention?"}

# Turn 1
reply_1 = ask([first_turn])
print("Turn 1 reply:", reply_1)

# Turn 2 WITHOUT history: the API has no memory of turn 1.
print("\nWithout history:", ask([follow_up]))

# Turn 2 WITH history: we resend everything.
history = [first_turn, {"role": "assistant", "content": reply_1}, follow_up]
print("\nWith history:   ", ask(history))
