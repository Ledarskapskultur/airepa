#!/usr/bin/env python3
"""Engångsscript: ger dig GOOGLE_REFRESH_TOKEN till .env.

Kör en gång på din egen dator (behöver en webbläsare):

    uv run python scripts/auth_google.py

Du behöver först en OAuth-klient av typen "Desktop app" i Google Cloud
Console, och GOOGLE_CLIENT_ID + GOOGLE_CLIENT_SECRET i .env. Se
docs/steg0-konton.md.
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.calendar_service import SCOPES  # noqa: E402
from app.config import get_settings  # noqa: E402


def main() -> int:
    s = get_settings()
    if not (s.google_client_id and s.google_client_secret):
        print("Saknar GOOGLE_CLIENT_ID och GOOGLE_CLIENT_SECRET i .env.")
        print("Skapa en OAuth-klient (Desktop app) i Google Cloud Console först.")
        return 1

    from google_auth_oauthlib.flow import InstalledAppFlow

    flow = InstalledAppFlow.from_client_config(
        {
            "installed": {
                "client_id": s.google_client_id,
                "client_secret": s.google_client_secret,
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
                "redirect_uris": ["http://localhost"],
            }
        },
        scopes=SCOPES,
    )
    # prompt=consent tvingar fram en refresh token även om du godkänt förut.
    creds = flow.run_local_server(port=0, prompt="consent", access_type="offline")

    if not creds.refresh_token:
        print("Google gav ingen refresh token. Ta bort appens behörighet på")
        print("https://myaccount.google.com/permissions och kör igen.")
        return 1

    print("\nKlart. Lägg in raden nedan i .env:\n")
    print(f"GOOGLE_REFRESH_TOKEN={creds.refresh_token}\n")
    print("Logga in med det konto som äger kalendern du vill boka i.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
