import os, json
from datetime import datetime
from flask import Flask, request, jsonify, render_template
from anthropic import Anthropic
from dotenv import load_dotenv
import smtplib
from email.mime.text import MIMEText

def send_email(subject, body):
    sender = os.environ["GMAIL_ADDRESS"]
    password = os.environ["GMAIL_APP_PASSWORD"]
    msg = MIMEText(body)
    msg["Subject"] = subject
    msg["From"] = sender
    msg["To"] = sender  # apne aap ko bhej rahe (client ka email yahan aayega)
    with smtplib.SMTP("smtp.gmail.com", 587, timeout=10) as server:
      server.starttls()
      server.login(sender, password)
      server.sendmail(sender, sender, msg.as_string())

load_dotenv()
client = Anthropic()
app = Flask(__name__)

PROPERTIES = """
1. 3-bed apartment, DHA Phase 5, Lahore — 10 Marla — PKR 4.5 crore (sale) — available
2. 2-bed flat, Bahria Town, Lahore — 5 Marla — PKR 85,000/month (rent) — available
3. 5-bed house, Gulberg, Lahore — 1 Kanal — PKR 9 crore (sale) — available
4. Studio apartment, Johar Town, Lahore — PKR 45,000/month (rent) — under negotiation
"""

SYSTEM_PROMPT = f"""You are a friendly real estate assistant for a Lahore property agency.
Your job:
- Answer questions about our listings (price, location, size, availability).
- Qualify the lead: are they buying or renting, their budget, and their timeline.
- When they show interest, offer to book a viewing and collect their name and preferred time.
- Once you have their name AND preferred time for a specific property, use the book_viewing tool.
- Be warm and concise. Never invent properties not in the list.

Our current listings:
{PROPERTIES}
"""

TOOLS = [{
    "name": "book_viewing",
    "description": "Save a property viewing booking once the lead gives their name and preferred time.",
    "input_schema": {
        "type": "object",
        "properties": {
            "name": {"type": "string"},
            "property": {"type": "string"},
            "preferred_time": {"type": "string"},
            "phone": {"type": "string"},
        },
        "required": ["name", "property", "preferred_time"],
    },
}]

def book_viewing(name, property, preferred_time, phone=""):
  booking = {"name": name, "property": property, "preferred_time": preferred_time,
              "phone": phone, "booked_at": datetime.now().strftime("%Y-%m-%d %H:%M")}
  with open("bookings.txt", "a", encoding="utf-8") as f:
      f.write(json.dumps(booking) + "\n")

  # send Email
  body = (f"New viewing booked!\n\n"
          f"Name: {name}\n"
          f"Property: {property}\n"
          f"Preferred time: {preferred_time}\n"
          f"Phone: {phone or 'not given'}\n"
          f"Booked at: {booking['booked_at']}")
  try:
      send_email("🏠 New Viewing Booking", body)
  except Exception as e:
      print("Email failed:", e)  

  return f"Booking confirmed for {name} — {property} at {preferred_time}."

@app.route("/")
def home():
    return render_template("index.html")

@app.route("/chat", methods=["POST"])
def chat():
    history = request.json["history"]

    while True:
        response = client.messages.create(
            model="claude-haiku-4-5",
            max_tokens=1024,
            system=SYSTEM_PROMPT,
            tools=TOOLS,
            messages=history,
        )
        history.append({"role": "assistant", "content": [b.model_dump() for b in response.content]})

        tool_use = next((b for b in response.content if b.type == "tool_use"), None)
        if tool_use:
            result = book_viewing(**tool_use.input)
            history.append({"role": "user", "content": [{
                "type": "tool_result", "tool_use_id": tool_use.id, "content": result}]})
            continue
        else:
            reply = " ".join(b.text for b in response.content if b.type == "text")
            return jsonify({"reply": reply, "history": history})

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
