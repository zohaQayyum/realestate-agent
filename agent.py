import os
import json
from datetime import datetime
from anthropic import Anthropic
from dotenv import load_dotenv

load_dotenv()
client = Anthropic()

PROPERTIES = """
1. 3-bed apartment, DHA Phase 5, Lahore — 10 Marla — PKR 4.5 crore (sale) — available
2. 2-bed flat, Bahria Town, Lahore — 5 Marla — PKR 85,000/month (rent) — available
3. 5-bed house, Gulberg, Lahore — 1 Kanal — PKR 9 crore (sale) — available
4. Studio apartment, Johar Town, Lahore — PKR 45,000/month (rent) — under negotiation
"""

SYSTEM_PROMPT = f"""You are a friendly real estate assistant for a Lahore property agency.
Your job:
- Answer questions about our listings (price, location, size, availability).
- Qualify the lead by naturally finding out: are they buying or renting, their budget, and their timeline.
- When they show interest, offer to book a viewing and collect their name and preferred time.
- Once you have their name AND preferred time for a specific property, use the book_viewing tool.
- Be warm and concise. Never invent properties not in the list.

Our current listings:
{PROPERTIES}

If someone asks about something we don't have, say so and offer the closest match.
"""

TOOLS = [
    {
        "name": "book_viewing",
        "description": "Save a property viewing booking once the lead gives their name and preferred time.",
        "input_schema": {
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "Lead's name"},
                "property": {"type": "string", "description": "Which property they want to see"},
                "preferred_time": {"type": "string", "description": "Their preferred day/time"},
                "phone": {"type": "string", "description": "Phone number if given, else empty"},
            },
            "required": ["name", "property", "preferred_time"],
        },
    }
]

def book_viewing(name, property, preferred_time, phone=""):
    """Saves the booking to a file."""
    booking = {
        "name": name,
        "property": property,
        "preferred_time": preferred_time,
        "phone": phone,
        "booked_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
    }
    with open("bookings.txt", "a", encoding="utf-8") as f:
        f.write(json.dumps(booking) + "\n")
    return f"Booking confirmed for {name} — {property} at {preferred_time}."

def main():
    print("Real Estate Agent (type 'quit' to exit)\n")
    history = []

    while True:
        user_input = input("Lead: ")
        if user_input.lower() in ("quit", "exit"):
            break

        history.append({"role": "user", "content": user_input})

        # Keep looping until the model is done (it may pause to call the tool)
        while True:
            response = client.messages.create(
                model="claude-haiku-4-5",
                max_tokens=1024,
                system=SYSTEM_PROMPT,
                tools=TOOLS,
                messages=history,
            )

            # Print any text the agent said
            for block in response.content:
                if block.type == "text":
                    print(f"\nAgent: {block.text}\n")

            history.append({"role": "assistant", "content": response.content})

            # Did the agent decide to book?
            tool_use = next((b for b in response.content if b.type == "tool_use"), None)

            if tool_use:
                result = book_viewing(**tool_use.input)
                print(f"[SYSTEM: {result}]\n")
                # Send the result back to the agent
                history.append({
                    "role": "user",
                    "content": [{
                        "type": "tool_result",
                        "tool_use_id": tool_use.id,
                        "content": result,
                    }],
                })
                continue  # let the agent respond after booking
            else:
                break  # normal reply, wait for next user input

if __name__ == "__main__":
    main()
    