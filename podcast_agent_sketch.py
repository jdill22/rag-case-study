# PI — Podcast Inbox Manager Agent
# Tools: Gmail, Podmatch, WhatsApp, Email

# Step 1 — Check for new inquiries
def check_gmail():
    # Read podcast Gmail for new guest inquiries
    pass

def check_podmatch():
    # Read Podmatch for new guest inquiries
    pass

# Step 2 — HITL: Notify Josh via WhatsApp
def notify_josh(guest_name, summary, profile_link, source):
    # Send WhatsApp message with summary + link
    # Include WHERE the inquiry came from (Gmail or Podmatch)
    # Then WAIT for Josh's response
    pass

# Step 3 — Act on Josh's decision
def accept_guest_email(guest_email):
    # Send acceptance email + Calendly link
    pass

def accept_guest_podmatch(guest_podmatch_id):
    # Send acceptance message via Podmatch + Calendly link
    pass

def decline_guest_email(guest_email):
    # Send polite decline via email
    pass

def decline_guest_podmatch(guest_podmatch_id):
    # Send polite decline via Podmatch
    pass

# Agent loop
def run_agent():
    inquiries = check_gmail() + check_podmatch()
    for inquiry in inquiries:
        notify_josh(inquiry)
        # Wait for Josh's decision
        # If fit → accept via correct platform
        # If not fit → decline via correct platform