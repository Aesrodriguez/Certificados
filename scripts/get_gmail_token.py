"""
One-time script to get a Gmail OAuth2 refresh_token.

Run this ONCE on your local machine to get the refresh_token,
then add it to Render's environment variables. You never need to run it again
unless you revoke the token.

Requirements (only for this script, not for production):
    pip install google-auth-oauthlib

Steps:
    1. Go to https://console.cloud.google.com/
    2. Create a project (or reuse one)
    3. APIs & Services → Enable APIs → search "Gmail API" → Enable
    4. APIs & Services → Credentials → Create credentials → OAuth client ID
       - Application type: Desktop app
       - Name: Clara Certificados
    5. Download the JSON file and note client_id and client_secret
    6. Add http://localhost to Authorized redirect URIs
    7. Run:  python scripts/get_gmail_token.py
    8. A browser opens → log in with andres1809rodriguez@gmail.com → Allow
    9. Copy the values printed at the end into Render environment variables
"""

import json
import sys

try:
    from google_auth_oauthlib.flow import InstalledAppFlow
except ImportError:
    sys.exit(
        "Install google-auth-oauthlib first:\n"
        "  pip install google-auth-oauthlib\n"
        "(Only needed to run this script, not in production)"
    )

CLIENT_ID = input("Paste your GMAIL_CLIENT_ID: ").strip()
CLIENT_SECRET = input("Paste your GMAIL_CLIENT_SECRET: ").strip()

client_config = {
    "installed": {
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "redirect_uris": ["http://localhost"],
        "auth_uri": "https://accounts.google.com/o/oauth2/auth",
        "token_uri": "https://oauth2.googleapis.com/token",
    }
}

flow = InstalledAppFlow.from_client_config(
    client_config,
    scopes=["https://www.googleapis.com/auth/gmail.send"],
)
creds = flow.run_local_server(port=0)

print("\n" + "=" * 60)
print("Add these to Render → Environment variables:")
print("=" * 60)
print(f"GMAIL_CLIENT_ID     = {CLIENT_ID}")
print(f"GMAIL_CLIENT_SECRET = {CLIENT_SECRET}")
print(f"GMAIL_REFRESH_TOKEN = {creds.refresh_token}")
print(f"GMAIL_SENDER        = andres1809rodriguez@gmail.com")
print("=" * 60)
