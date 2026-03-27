# ============================================================
# PI — Podcast Inbox Manager Agent  (HITL Build)
# Josh Dillingham · March 2026
# ============================================================
# Architecture:
#   - Background thread polls Gmail every 5 minutes
#   - Flask webhook at /webhook receives Twilio WhatsApp replies
#   - In-memory session queue: one active inquiry at a time
#
# Deploy to Replit:
#   1. Set all env vars in Replit Secrets (same keys as .env)
#   2. Delete token.json if it exists — Gmail will re-auth with send scope
#   3. Set run command: python agent.py
#   4. Copy the public Replit URL → Twilio WhatsApp sandbox webhook
# ============================================================

import os
import base64
import logging
import threading
import time
from email.mime.text import MIMEText
from email.utils import parseaddr

from flask import Flask, request
from dotenv import load_dotenv
from twilio.rest import Client as TwilioClient
import anthropic
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build

load_dotenv()

# ── Logging ──────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s'
)
log = logging.getLogger(__name__)

# ── Flask app ─────────────────────────────────────────────────
app = Flask(__name__)

# ── Config ────────────────────────────────────────────────────
# Gmail now needs send scope in addition to read.
# If you have an existing token.json with readonly scope only,
# delete it so the OAuth flow re-runs with the new scopes.
SCOPES = [
    'https://www.googleapis.com/auth/gmail.readonly',
    'https://www.googleapis.com/auth/gmail.send',
]

MY_WHATSAPP = os.getenv('MY_WHATSAPP_NUMBER')          # whatsapp:+1XXXXXXXXXX
TWILIO_FROM  = os.getenv('TWILIO_WHATSAPP_FROM')        # whatsapp:+14155238886

# Comma-separated list of past guest emails, e.g. "guest@x.com,other@y.com"
PAST_GUESTS = {
    g.strip().lower()
    for g in os.getenv('PAST_GUESTS', '').split(',')
    if g.strip()
}

POLL_INTERVAL = int(os.getenv('POLL_INTERVAL_SECONDS', '300'))  # default 5 min

# ── Session state ─────────────────────────────────────────────
# Modes:
#   None                    — no active inquiry waiting
#   "awaiting_yes_no"       — Josh should reply YES or NO
#   "awaiting_past_guest"   — Josh should reply with custom text to forward
#
# Only ONE inquiry is active at a time; others queue up.
_session_lock = threading.Lock()
_session = {
    "mode":   None,
    "active": None,   # dict: {id, sender, subject, snippet, source, summary}
    "queue":  [],     # list of dicts (same shape)
}

# Track already-processed Gmail message IDs across poll cycles
_processed_ids: set = set()

# ── Gmail auth ────────────────────────────────────────────────
def authenticate_gmail():
    creds = None
    if os.path.exists('token.json'):
        creds = Credentials.from_authorized_user_file('token.json', SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                'PI-podcast-agent.json', SCOPES)
            creds = flow.run_local_server(port=0)
        with open('token.json', 'w') as f:
            f.write(creds.to_json())
    return build('gmail', 'v1', credentials=creds)

# ── Helpers ───────────────────────────────────────────────────
def extract_first_name(sender: str) -> str:
    """'John Smith <j@x.com>' → 'John'   |   'j@x.com' → 'J'"""
    name, email = parseaddr(sender)
    if name and name.strip():
        return name.strip().split()[0]
    local = email.split('@')[0] if '@' in email else email
    return local.capitalize()

def is_past_guest(sender: str) -> bool:
    _, email = parseaddr(sender)
    return email.lower() in PAST_GUESTS

def _twilio_client():
    return TwilioClient(
        os.getenv('TWILIO_ACCOUNT_SID'),
        os.getenv('TWILIO_AUTH_TOKEN')
    )

# ── WhatsApp ──────────────────────────────────────────────────
def send_whatsapp(to: str, body: str) -> str:
    client = _twilio_client()
    msg = client.messages.create(body=body, from_=TWILIO_FROM, to=to)
    log.info(f"WhatsApp sent → {to} | SID={msg.sid}")
    return msg.sid

def notify_josh_new_inquiry(inquiry: dict, summary: str):
    body = (
        f"PI — New Guest Inquiry\n\n"
        f"From: {inquiry['sender']}\n"
        f"Subject: {inquiry['subject']}\n\n"
        f"{summary}\n\n"
        f"Reply YES to accept or NO to decline."
    )
    send_whatsapp(MY_WHATSAPP, body)

# ── Gmail send ────────────────────────────────────────────────
def send_reply_email(gmail_service, to_address: str, subject: str, body: str):
    msg = MIMEText(body)
    msg['to'] = to_address
    msg['subject'] = f"Re: {subject}"
    raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()
    gmail_service.users().messages().send(
        userId='me', body={'raw': raw}
    ).execute()
    log.info(f"Email sent → {to_address} | Subject: Re: {subject}")

# ── Gmail poll ────────────────────────────────────────────────
def check_gmail(service) -> list:
    results = service.users().messages().list(
        userId='me',
        labelIds=['INBOX'],
        maxResults=20
    ).execute()
    messages = results.get('messages', [])

    inquiry_keywords = ['guest', 'injured', 'inquiry', 'inquiries',
                        'feature', 'interview', 'appear']
    excluded_senders = ['buzzsprout', 'noreply', 'no-reply',
                        'support@', 'billing@', 'podpage']
    inquiries = []

    for msg in messages:
        msg_id = msg['id']
        if msg_id in _processed_ids:
            continue

        message = service.users().messages().get(
            userId='me',
            id=msg_id,
            format='metadata',
            metadataHeaders=['From', 'Subject']
        ).execute()

        headers  = message['payload']['headers']
        subject  = next((h['value'] for h in headers if h['name'] == 'Subject'), 'No Subject')
        sender   = next((h['value'] for h in headers if h['name'] == 'From'), 'Unknown')
        snippet  = message.get('snippet', '')

        is_inquiry = any(
            kw.lower() in subject.lower() or kw.lower() in snippet.lower()
            for kw in inquiry_keywords
        )
        is_excluded = any(ex.lower() in sender.lower() for ex in excluded_senders)

        if not is_inquiry or is_excluded:
            continue

        log.info(f"[POLL] New inquiry — From: {sender} | Subject: {subject}")
        _processed_ids.add(msg_id)

        inquiries.append({
            'id':      msg_id,
            'sender':  sender,
            'subject': subject,
            'snippet': snippet,
            'source':  'gmail',
        })

    return inquiries

def summarize_inquiry(inquiry: dict) -> str:
    client = anthropic.Anthropic()
    prompt = (
        f"You are PI, a podcast inbox manager for the Playing Injured podcast.\n\n"
        f"A potential guest inquiry has arrived. Summarize it clearly and concisely for the host Josh.\n\n"
        f"From: {inquiry['sender']}\n"
        f"Subject: {inquiry['subject']}\n"
        f"Message preview: {inquiry['snippet']}\n\n"
        f"Write a 2-3 sentence summary that tells Josh:\n"
        f"1. Who is reaching out and why\n"
        f"2. Whether they seem like a serious inquiry or a mass pitch\n"
        f"3. What Josh should know before deciding yes or no\n\n"
        f"Keep it direct and conversational."
    )
    response = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=300,
        messages=[{"role": "user", "content": prompt}]
    )
    return response.content[0].text

# ── Session management ────────────────────────────────────────
def _activate_next_locked():
    """
    Called while _session_lock is held.
    Pops next item from queue into active slot.
    Returns the newly activated inquiry, or None if queue is empty.
    """
    if _session["queue"]:
        nxt = _session["queue"].pop(0)
        _session["mode"]   = "awaiting_yes_no"
        _session["active"] = nxt
        log.info(f"[SESSION] Activated next inquiry: {nxt['sender']}")
        return nxt
    else:
        _session["mode"]   = None
        _session["active"] = None
        log.info("[SESSION] Queue empty — no active session.")
        return None

def handle_new_inquiry(inquiry: dict, summary: str):
    inquiry["summary"] = summary

    with _session_lock:
        if is_past_guest(inquiry["sender"]):
            # ── Escalation 2: past guest ──────────────────────
            _, guest_email = parseaddr(inquiry["sender"])
            log.info(f"[ESCALATION 2] Past guest detected: {inquiry['sender']}")

            # If another inquiry is already active, queue this one for now
            # and handle it after the current active session resolves.
            # For past guests we do interrupt immediately — they need special handling.
            # If there's already an active past-guest session, queue.
            if _session["mode"] is not None:
                log.info(f"[SESSION] Past guest inquiry queued (session busy): {inquiry['sender']}")
                _session["queue"].append(inquiry)
                return

            _session["mode"]   = "awaiting_past_guest"
            _session["active"] = inquiry

        elif _session["mode"] is None:
            # ── Normal flow: activate immediately ─────────────
            _session["mode"]   = "awaiting_yes_no"
            _session["active"] = inquiry
            log.info(f"[SESSION] Active inquiry set: {inquiry['sender']}")

        else:
            # ── Normal flow: queue for later ──────────────────
            _session["queue"].append(inquiry)
            log.info(f"[SESSION] Inquiry queued: {inquiry['sender']} "
                     f"(queue depth: {len(_session['queue'])})")
            return

    # Notify outside the lock
    if is_past_guest(inquiry["sender"]):
        name = inquiry["sender"]
        send_whatsapp(
            MY_WHATSAPP,
            f"PI — Past guest reaching out: {name}.\n"
            f"I don't know the context. Reply with how you'd like me to respond and I'll send it."
        )
        log.info(f"[ESCALATION 2] Josh notified about past guest: {name}")
    else:
        notify_josh_new_inquiry(inquiry, summary)

# ── Flask webhook ─────────────────────────────────────────────
@app.route('/webhook', methods=['POST'])
def webhook():
    from_number = request.form.get('From', '').strip()
    body        = request.form.get('Body', '').strip()

    log.info(f"[WEBHOOK] Received from={from_number!r} body={body!r}")

    # ── Sender verification ───────────────────────────────────
    if from_number != MY_WHATSAPP:
        log.warning(f"[WEBHOOK] Rejected — unknown sender: {from_number}")
        return '', 204

    with _session_lock:
        mode   = _session["mode"]
        active = _session["active"]

    if mode is None or active is None:
        log.info("[WEBHOOK] No active session — reply ignored.")
        return '', 204

    # ── Escalation 2: past guest custom reply ─────────────────
    if mode == "awaiting_past_guest":
        log.info(f"[ESCALATION 2] Forwarding Josh's custom reply to {active['sender']}")

        with _session_lock:
            inquiry = _session["active"]
            next_inquiry = _activate_next_locked()

        _, guest_email = parseaddr(inquiry["sender"])
        try:
            gmail_service = authenticate_gmail()
            send_reply_email(gmail_service, guest_email, inquiry["subject"], body)
            log.info(f"[ESCALATION 2] Custom reply sent to {guest_email}")
        except Exception as e:
            log.error(f"[ESCALATION 2] Failed to send email: {e}")

        if next_inquiry:
            _dispatch_inquiry(next_inquiry)

        return '', 204

    # ── Normal flow: YES / NO ─────────────────────────────────
    if mode == "awaiting_yes_no":
        reply = body.upper()

        # ── Escalation 1: ambiguous reply ─────────────────────
        if reply not in ("YES", "NO"):
            log.warning(f"[ESCALATION 1] Ambiguous reply: {body!r}")
            send_whatsapp(
                MY_WHATSAPP,
                "PI couldn't process your reply.\nPlease respond YES or NO."
            )
            return '', 204

        # Valid YES or NO
        with _session_lock:
            inquiry = _session["active"]
            next_inquiry = _activate_next_locked()

        first_name = extract_first_name(inquiry["sender"])
        _, guest_email = parseaddr(inquiry["sender"])

        if reply == "YES":
            email_body = (
                f"Hi {first_name},\n\n"
                f"Appreciate you reaching out. I think this would \n"
                f"be a great fit. Here's our booking link:\n"
                f"https://calendly.com/playinginjured/playing-injured-podcast\n\n"
                f"Pick a time that works best for you! \n"
                f"Looking forward to it!\n\n"
                f"Josh"
            )
            log.info(f"[YES] Sending acceptance to {guest_email}")
        else:
            email_body = (
                f"Hi {first_name},\n\n"
                f"Thank you for reaching out, we appreciate you \n"
                f"thinking of us. We don't think this would be \n"
                f"a great fit at this time.\n\n"
                f"Josh"
            )
            log.info(f"[NO] Sending decline to {guest_email}")

        try:
            gmail_service = authenticate_gmail()
            send_reply_email(gmail_service, guest_email, inquiry["subject"], email_body)
        except Exception as e:
            log.error(f"[WEBHOOK] Failed to send email: {e}")
            send_whatsapp(
                MY_WHATSAPP,
                f"PI — Email send failed for {guest_email}. Error: {e}"
            )

        if next_inquiry:
            _dispatch_inquiry(next_inquiry)

        return '', 204

    log.warning(f"[WEBHOOK] Unexpected mode: {mode!r}")
    return '', 204

def _dispatch_inquiry(inquiry: dict):
    """Notify Josh about the newly activated inquiry (called outside lock)."""
    if inquiry.get("_escalation2"):
        name = inquiry["sender"]
        send_whatsapp(
            MY_WHATSAPP,
            f"PI — Past guest reaching out: {name}.\n"
            f"I don't know the context. Reply with how you'd like me to respond and I'll send it."
        )
    else:
        notify_josh_new_inquiry(inquiry, inquiry.get("summary", ""))

# ── Background poller ─────────────────────────────────────────
def _poller():
    log.info("[POLLER] Starting Gmail poll loop.")
    while True:
        try:
            log.info("[POLLER] Checking Gmail...")
            service   = authenticate_gmail()
            inquiries = check_gmail(service)
            log.info(f"[POLLER] Found {len(inquiries)} new inquiry/inquiries.")
            for inquiry in inquiries:
                summary = summarize_inquiry(inquiry)
                log.info(f"[POLLER] Summary: {summary}")
                handle_new_inquiry(inquiry, summary)
        except Exception as e:
            log.error(f"[POLLER] Error: {e}", exc_info=True)
        time.sleep(POLL_INTERVAL)

# ── Entry point ───────────────────────────────────────────────
if __name__ == '__main__':
    poller_thread = threading.Thread(target=_poller, daemon=True)
    poller_thread.start()
    log.info(f"[MAIN] Flask webhook starting on 0.0.0.0:8080")
    app.run(host='0.0.0.0', port=8080, debug=False)
