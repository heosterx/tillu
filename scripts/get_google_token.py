"""
One-time script to get Google OAuth refresh token for Calendar + Gmail.

Usage:
    pip install google-auth-oauthlib
    python scripts/get_google_token.py

Then copy the printed values into your .env file.
"""
import os
import json
from google_auth_oauthlib.flow import InstalledAppFlow

# Scopes needed by TILLU
SCOPES = [
    "https://www.googleapis.com/auth/calendar.readonly",
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.send",       # optional: for sending replies
]

# ── Fill these in from your Google Cloud Console ──────────────────────────────
CLIENT_ID     = os.environ.get("GOOGLE_CLIENT_ID", "YOUR_CLIENT_ID.apps.googleusercontent.com")
CLIENT_SECRET = os.environ.get("GOOGLE_CLIENT_SECRET", "YOUR_CLIENT_SECRET")
# ──────────────────────────────────────────────────────────────────────────────

def main():
    if "YOUR_CLIENT" in CLIENT_ID:
        print("ERROR: Set GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET env vars first.")
        print("  $env:GOOGLE_CLIENT_ID='your-id.apps.googleusercontent.com'")
        print("  $env:GOOGLE_CLIENT_SECRET='your-secret'")
        return

    # Build client config inline (no need to download JSON file)
    client_config = {
        "installed": {
            "client_id": CLIENT_ID,
            "client_secret": CLIENT_SECRET,
            "redirect_uris": ["urn:ietf:wg:oauth:2.0:oob", "http://localhost"],
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
        }
    }

    flow = InstalledAppFlow.from_client_config(client_config, SCOPES)

    # Opens browser for consent — copy the code back here
    creds = flow.run_local_server(port=0)

    print("\n" + "="*60)
    print("✅ SUCCESS — Add these to your .env and .env.production:")
    print("="*60)
    print(f"\nGOOGLE_CLIENT_ID={CLIENT_ID}")
    print(f"GOOGLE_CLIENT_SECRET={CLIENT_SECRET}")
    print(f"GMAIL_REFRESH_TOKEN={creds.refresh_token}")
    print("\n" + "="*60)
    print("The refresh token never expires unless you revoke it.")
    print("Keep it secret — it grants read access to Calendar + Gmail.")
    print("="*60 + "\n")


if __name__ == "__main__":
    main()
