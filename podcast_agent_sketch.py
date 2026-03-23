# ============================================================
# PI — Podcast Inbox Manager Agent
# Josh Dillingham · March 2026
# ============================================================
# Tools: Gmail, WhatsApp, Email
# Guardrails: Never share private data, never make payments,
#             never click links in messages
# ============================================================

import os
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
import anthropic

from dotenv import load_dotenv
load_dotenv()

# Gmail scope — read only for now
SCOPES = ['https://www.googleapis.com/auth/gmail.readonly']

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
        with open('token.json', 'w') as token:
            token.write(creds.to_json())
    return build('gmail', 'v1', credentials=creds)

def check_gmail():
    service = authenticate_gmail()
    results = service.users().messages().list(
        userId='me',
        labelIds=['INBOX'],
        maxResults=20
    ).execute()
    messages = results.get('messages', [])
    
    print(f"\n--- Gmail Inbox ---")
    inquiries = []
    
    for msg in messages:
        message = service.users().messages().get(
            userId='me',
            id=msg['id'],
            format='metadata',
            metadataHeaders=['From', 'Subject']
        ).execute()
        
        headers = message['payload']['headers']
        subject = next((h['value'] for h in headers if h['name'] == 'Subject'), 'No Subject')
        sender = next((h['value'] for h in headers if h['name'] == 'From'), 'Unknown')
        snippet = message.get('snippet', '')
        
        keywords = ['guest', 'injured', 'inquiry', 'inquiries', 'feature', 'interview', 'appear']
        is_inquiry = any(keyword.lower() in subject.lower() or 
                         keyword.lower() in snippet.lower() 
                         for keyword in keywords)
        
        excluded_senders = ['buzzsprout', 'noreply', 'no-reply', 'support@', 'billing@', 'podpage']
        is_excluded = any(excluded.lower() in sender.lower() for excluded in excluded_senders)
        
        if not is_inquiry or is_excluded:
            continue                
        
        print(f"\nFrom: {sender}")
        print(f"Subject: {subject}")
        print(f"Preview: {snippet[:150]}")
        
        inquiries.append({
            'id': msg['id'],
            'sender': sender,
            'subject': subject,
            'snippet': snippet,
            'source': 'gmail'
        })
    
    return inquiries

def summarize_inquiry(inquiry):
    client = anthropic.Anthropic()
    
    prompt = f"""You are PI, a podcast inbox manager for the Playing Injured podcast.
    
A potential guest inquiry has arrived. Summarize it clearly and concisely for the host Josh.

From: {inquiry['sender']}
Subject: {inquiry['subject']}
Message preview: {inquiry['snippet']}

Write a 2-3 sentence summary that tells Josh:
1. Who is reaching out and why
2. Whether they seem like a serious inquiry or a mass pitch
3. What Josh should know before deciding yes or no

Keep it direct and conversational."""

    message = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=300,
        messages=[{"role": "user", "content": prompt}]
    )
    
    return message.content[0].text

# WhatsApp notification to Josh
def notify_josh_whatsapp(inquiry, summary):
    from twilio.rest import Client
    
    account_sid = os.getenv('TWILIO_ACCOUNT_SID')
    auth_token = os.getenv('TWILIO_AUTH_TOKEN')
    from_number = os.getenv('TWILIO_WHATSAPP_FROM')
    to_number = os.getenv('MY_WHATSAPP_NUMBER')
    
    client = Client(account_sid, auth_token)
    
    message = client.messages.create(
        body=f"🎙️ PI — New Guest Inquiry\n\nFrom: {inquiry['sender']}\nSubject: {inquiry['subject']}\n\n{summary}\n\nReply YES to accept or NO to decline.",
        from_=from_number,
        to=to_number
    )
    
    print(f"WhatsApp sent! Message SID: {message.sid}")
    return message.sid

# Run it
if __name__ == "__main__":
    inquiries = check_gmail()
    for inquiry in inquiries:
        print(f"\n--- PI Summary ---")
        summary = summarize_inquiry(inquiry)
        print(summary)
        notify_josh_whatsapp(inquiry, summary)