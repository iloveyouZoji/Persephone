#!/usr/bin/env python3
"""
SMS Poll server (Flask) - main app
Endpoints (JSON):
- POST /api/polls              create poll {title, question, choices: ["A:Red","B:Blue"], template (optional)}
- GET  /api/polls              list polls
- GET  /api/polls/<id>         poll detail
- POST /api/polls/<id>/send    send poll to numbers {numbers: ["+1555..."]}
- GET  /api/polls/<id>/results results JSON
- POST /sms                   Twilio webhook for inbound messages (form-encoded)
"""
import os
import json
from datetime import datetime
from flask import Flask, request, jsonify, abort, g
from twilio.rest import Client
from twilio.twiml.messaging_response import MessagingResponse
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, scoped_session
from models import Base, Poll, Choice, Vote, RawMessage, OptOut

# Config from env
TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID")
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN")
TWILIO_NUMBER = os.getenv("TWILIO_NUMBER")
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///polls.db")
ADMIN_API_KEY = os.getenv("ADMIN_API_KEY", "changeme")
PORT = int(os.getenv("PORT", 5000))

if not (TWILIO_ACCOUNT_SID and TWILIO_AUTH_TOKEN and TWILIO_NUMBER):
    print("Warning: TWILIO credentials not fully set. Sending will fail until set in .env.")

app = Flask(__name__)

# DB setup
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {})
SessionLocal = scoped_session(sessionmaker(bind=engine))
Base.metadata.create_all(bind=engine)

# Twilio client
twilio_client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN) if TWILIO_ACCOUNT_SID else None

# Simple admin auth
def require_admin():
    api_key = request.headers.get("X-API-KEY", "")
    if api_key != ADMIN_API_KEY:
        abort(401)

# DB session per request
@app.before_request
def _db_session():
    g.db = SessionLocal()

@app.teardown_request
def _db_cleanup(exc):
    db = g.get("db", None)
    if db:
        if exc:
            db.rollback()
        db.close()

# Helpers
def poll_to_dict(poll):
    return {
        "id": poll.id,
        "title": poll.title,
        "question": poll.question,
        "created_at": poll.created_at.isoformat(),
        "choices": [{"id": c.id, "label": c.label, "code": c.code} for c in poll.choices],
    }

# APIs
@app.route("/api/polls", methods=["POST"])
def create_poll():
    require_admin()
    payload = request.get_json() or {}
    title = payload.get("title") or payload.get("question", "Poll")
    question = payload.get("question") or title
    raw_choices = payload.get("choices") or []
    template = payload.get("template")  # e.g. "Poll: {question} Reply with A/B/C"
    if not raw_choices or not isinstance(raw_choices, list):
        return jsonify({"error": "choices required (list)"}), 400

    db = g.db
    poll = Poll(title=title, question=question, template=template)
    db.add(poll)
    db.flush()  # get id

    # choices expected like "A:Red" or {"code":"A","label":"Red"}
    for rc in raw_choices:
        if isinstance(rc, dict):
            code = rc.get("code")
            label = rc.get("label")
        else:
            parts = str(rc).split(":", 1)
            if len(parts) == 2:
                code, label = parts[0].strip().upper(), parts[1].strip()
            else:
                code = parts[0].strip().upper()
                label = parts[0].strip()
        choice = Choice(poll_id=poll.id, code=code, label=label)
        db.add(choice)
    db.commit()
    db.refresh(poll)
    return jsonify(poll_to_dict(poll)), 201

@app.route("/api/polls", methods=["GET"])
def list_polls():
    db = g.db
    polls = db.query(Poll).order_by(Poll.created_at.desc()).all()
    return jsonify([poll_to_dict(p) for p in polls])

@app.route("/api/polls/<int:poll_id>", methods=["GET"])
def get_poll(poll_id):
    db = g.db
    poll = db.query(Poll).get(poll_id)
    if not poll:
        return jsonify({"error": "not found"}), 404
    return jsonify(poll_to_dict(poll))

@app.route("/api/polls/<int:poll_id>/send", methods=["POST"])
def send_poll(poll_id):
    require_admin()
    db = g.db
    poll = db.query(Poll).get(poll_id)
    if not poll:
        return jsonify({"error": "not found"}), 404
    body = request.get_json() or {}
    numbers = body.get("numbers")
    if not isinstance(numbers, list) or not numbers:
        return jsonify({"error": "numbers list required"}), 400

    # template message
    if poll.template:
        message = poll.template.format(question=poll.question, choices=", ".join([f"{c.code}={c.label}" for c in poll.choices]))
    else:
        # default
        message = f"{poll.question}\n" + " / ".join([f"{c.code}={c.label}" for c in poll.choices]) + "\nReply with the code (e.g. A)"

    results = []
    for to_number in numbers:
        try:
            if not twilio_client:
                raise RuntimeError("Twilio not configured")
            msg = twilio_client.messages.create(body=message, from_=TWILIO_NUMBER, to=to_number)
            results.append({"to": to_number, "sid": msg.sid, "status": msg.status})
        except Exception as e:
            results.append({"to": to_number, "error": str(e)})
    return jsonify({"results": results})

@app.route("/sms", methods=["POST"])
def inbound_sms():
    # Twilio will POST form-encoded body with From, Body, To
    from_number = request.form.get("From")
    body = (request.form.get("Body") or "").strip()
    to_number = request.form.get("To")
    timestamp = datetime.utcnow()

    db = g.db

    # find active poll(s) by To number or choose latest poll
    # For simplicity, we map all inbound replies to the most recent poll
    poll = db.query(Poll).order_by(Poll.created_at.desc()).first()
    resp = MessagingResponse()

    if not poll:
        # no polls created yet
        resp.message("No active poll available. Sorry.")
        # record raw message
        db.add(RawMessage(from_number=from_number, to_number=to_number, body=body, received_at=timestamp, poll_id=None))
        db.commit()
        return str(resp)

    # record raw message
    raw = RawMessage(from_number=from_number, to_number=to_number, body=body, received_at=timestamp, poll_id=poll.id)
    db.add(raw)
    db.flush()

    # check opt-out keywords
    if body.strip().upper() in ("STOP", "UNSUBSCRIBE", "QUIT", "END"):
        # add to opt-out table and delete any existing vote for that poll
        op = db.query(OptOut).get(from_number)
        if not op:
            op = OptOut(number=from_number, created_at=timestamp)
            db.add(op)
        db.query(Vote).filter(Vote.poll_id == poll.id, Vote.from_number == from_number).delete()
        db.commit()
        resp.message("You have been unsubscribed and will no longer receive poll messages. Reply START to opt back in.")
        return str(resp)

    # Do not accept votes from opted-out numbers
    if db.query(OptOut).filter(OptOut.number == from_number).first():
        resp.message("You have unsubscribed. Reply START to opt back in.")
        db.commit()
        return str(resp)

    # extract choice - simple: first token or letter
    token = body.split()[0].strip().upper()
    # match token to a choice code
    choice = None
    for c in poll.choices:
        if token == c.code.upper():
            choice = c
            break
    # fallback: if user sent full label, try matching labels
    if not choice:
        for c in poll.choices:
            if token.lower() == c.label.lower():
                choice = c
                break

    if not choice:
        resp.message("Sorry, I couldn't understand your reply. Reply with one of: " + ", ".join([c.code for c in poll.choices]))
        db.commit()
        return str(resp)

    # upsert vote (one per phone per poll)
    existing = db.query(Vote).filter(Vote.poll_id == poll.id, Vote.from_number == from_number).first()
    if existing:
        existing.choice_id = choice.id
        existing.updated_at = datetime.utcnow()
        action = "updated"
    else:
        v = Vote(poll_id=poll.id, choice_id=choice.id, from_number=from_number, created_at=timestamp)
        db.add(v)
        action = "recorded"
    db.commit()
    resp.message(f"Thanks — your vote '{choice.code}={choice.label}' was {action}.")
    return str(resp)

@app.route("/api/polls/<int:poll_id>/results", methods=["GET"])
def poll_results(poll_id):
    require_admin()
    db = g.db
    poll = db.query(Poll).get(poll_id)
    if not poll:
        return jsonify({"error": "not found"}), 404
    # counts
    counts = {}
    for c in poll.choices:
        counts[c.code] = db.query(Vote).filter(Vote.poll_id == poll.id, Vote.choice_id == c.id).count()
    # optionally include raw votes (paginated?) - include recent 50
    raw_votes = []
    rows = db.query(Vote).filter(Vote.poll_id == poll.id).order_by(Vote.created_at.desc()).limit(200).all()
    for r in rows:
        raw_votes.append({"from": r.from_number, "choice": r.choice.code if r.choice else None, "at": r.created_at.isoformat()})
    return jsonify({"poll": poll_to_dict(poll), "counts": counts, "votes": raw_votes})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=PORT, debug=True)