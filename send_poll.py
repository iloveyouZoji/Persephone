#!/usr/bin/env python3
"""
CLI helper to send a poll using Twilio (alternative to API)
Usage:
  python send_poll.py <poll_id> numbers.json

numbers.json example: ["+15551234567","+15559876543"]
"""
import os, sys, json
from twilio.rest import Client
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from models import Base, Poll
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///polls.db")
TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID")
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN")
TWILIO_NUMBER = os.getenv("TWILIO_NUMBER")

if not (TWILIO_ACCOUNT_SID and TWILIO_AUTH_TOKEN and TWILIO_NUMBER):
    print("Set TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, TWILIO_NUMBER in env")
    sys.exit(1)

if len(sys.argv) < 3:
    print("Usage: send_poll.py <poll_id> numbers.json")
    sys.exit(1)

poll_id = int(sys.argv[1])
nums_file = sys.argv[2]
numbers = json.load(open(nums_file))

engine = create_engine(DATABASE_URL)
Session = sessionmaker(bind=engine)
db = Session()
poll = db.query(Poll).get(poll_id)
if not poll:
    print("Poll not found")
    sys.exit(1)

message = poll.template.format(question=poll.question, choices=", ".join([f"{c.code}={c.label}" for c in poll.choices])) if poll.template else f"{poll.question}\n" + " / ".join([f"{c.code}={c.label}" for c in poll.choices]) + "\nReply with the code (e.g. A)"

client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
for n in numbers:
    try:
        m = client.messages.create(body=message, from_=TWILIO_NUMBER, to=n)
        print("Sent to", n, "sid", m.sid)
    except Exception as e:
        print("Error sending to", n, e)