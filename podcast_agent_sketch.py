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
        # Get full message details
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
        
        # Filter for podcast guest inquiries only
        keywords = ['guest', 'injured', 'inquiry', 'inquiries', 'feature', 'interview', 'appear']
        is_inquiry = any(keyword.lower() in subject.lower() or 
                         keyword.lower() in snippet.lower() 
                         for keyword in keywords)

        # Filter for podcast guest inquiries only
        keywords = ['guest', 'injured', 'inquiry', 'inquiries', 'feature', 'interview', 'appear']
        is_inquiry = any(keyword.lower() in subject.lower() or 
                         keyword.lower() in snippet.lower() 
                         for keyword in keywords)
        
        # Exclude known non-inquiry senders
        excluded_senders = ['buzzsprout', 'noreply', 'no-reply', 'support@', 'billing@']
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

# Run it
if __name__ == "__main__":
    check_gmail()

   