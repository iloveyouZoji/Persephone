# Persephone

Persephone is a lightweight SMS polling server built with Flask and SQLAlchemy. It provides a simple REST API to create polls, send them to phone numbers via Twilio, collect replies via a Twilio webhook, and retrieve results. It is designed for quick setup and easy integration into small projects or prototypes.

## Features
- Create polls with multiple choices
- Send poll messages to lists of phone numbers via Twilio
- Receive replies via a Twilio webhook and record votes (one vote per phone number per poll)
- Opt-out handling (STOP/UNSUBSCRIBE/QUIT/END)
- Admin-protected API endpoints

## Quick start

1. Install dependencies:
   pip install -r requirements.txt

2. Set environment variables (minimum):
   - TWILIO_ACCOUNT_SID
   - TWILIO_AUTH_TOKEN
   - TWILIO_NUMBER (the Twilio phone number to send from)
   - ADMIN_API_KEY (used by admin endpoints; value checked against X-API-KEY header)
   - DATABASE_URL (optional; defaults to `sqlite:///polls.db`)
   - PORT (optional; defaults to 5000)

3. Run the app (development):
   python server.py

For production, run behind a WSGI server (gunicorn, uWSGI) and manage environment variables securely.

## Configuration (environment variables)
- TWILIO_ACCOUNT_SID — Twilio account SID (required for sending)
- TWILIO_AUTH_TOKEN — Twilio auth token (required for sending)
- TWILIO_NUMBER — Twilio phone number (required for sending)
- DATABASE_URL — SQLAlchemy DB URL (defaults to `sqlite:///polls.db`)
- ADMIN_API_KEY — Admin API key (defaults to `changeme`; set to a strong secret)
- PORT — HTTP port to listen on (defaults to `5000`)

Admin endpoints require the X-API-KEY HTTP header to equal ADMIN_API_KEY.

## API

All admin endpoints must include header: `X-API-KEY: <ADMIN_API_KEY>`

- POST /api/polls
  - Create a new poll
  - Body (JSON):
    {
      "title": "Favorite color",
      "question": "What's your favorite color?",
      "choices": ["A:Red", "B:Blue", "C:Green"],
      "template": "Poll: {question} Reply with A/B/C"  // optional
    }
  - Alternative choice format: objects like {"code":"A","label":"Red"}
  - Returns: created poll JSON

- GET /api/polls
  - List polls

- GET /api/polls/<id>
  - Get poll details

- POST /api/polls/<id>/send
  - Send the poll text to a list of numbers via Twilio
  - Body (JSON): { "numbers": ["+1555...","+1666..."] }
  - Returns delivery results per number

- GET /api/polls/<id>/results
  - Admin-only: returns counts and a recent list of recorded votes

- POST /sms
  - Twilio webhook endpoint for inbound SMS (expects form-encoded POST with `From`, `Body`, `To`)
  - Server maps replies to the most recent poll by default. It:
    - Records raw messages
    - Handles opt-out keywords: STOP, UNSUBSCRIBE, QUIT, END
    - Ignores votes from opted-out numbers
    - Accepts a choice by code (e.g., "A") or by label
    - Upserts the vote (one vote per phone number per poll)

## Behavior notes
- Default message format when sending a poll:
  "<question>\nA=Red / B=Blue\nReply with the code (e.g. A)"
- Opt-out: incoming "STOP", "UNSUBSCRIBE", "QUIT", or "END" adds the number to the opt-out list and deletes any existing vote for that poll.
- Votes are stored per poll and per subscriber; updating a vote replaces the previous choice.
- The app uses SQLAlchemy's create_all at startup; for production schema migration use a tool like Alembic.

## Example requests

Create a poll:
curl -X POST http://localhost:5000/api/polls \
  -H "Content-Type: application/json" \
  -H "X-API-KEY: <ADMIN_API_KEY>" \
  -d '{"title":"Colors","question":"Pick a color","choices":["A:Red","B:Blue","C:Green"]}'

Send a poll:
curl -X POST http://localhost:5000/api/polls/1/send \
  -H "Content-Type: application/json" \
  -H "X-API-KEY: <ADMIN_API_KEY>" \
  -d '{"numbers":["+15551234567","+15557654321"]}'

Twilio should be configured to POST inbound messages to:
https://<your-host>/sms

## Development & testing
- The project uses Flask and SQLAlchemy. The DB defaults to a local SQLite file (`polls.db`) for quick development.
- To reset the DB in development, remove the SQLite file and restart the app (it will recreate tables).
- Consider adding automated tests and a migration workflow for production use.

## Security
- Do not use the default ADMIN_API_KEY in production. Store secrets in a secure secret manager or environment configuration.
- Ensure your webhook endpoint is secured (use HTTPS) and validate Twilio requests if exposing publicly.

## Contributing
Contributions are welcome. Please open issues or pull requests with descriptive titles and tests where applicable.

## License
MIT License
