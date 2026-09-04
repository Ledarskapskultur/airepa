#!/usr/bin/env python3
"""Skapar eller uppdaterar Vapi-assistenten från app/assistant_config.py.

    uv run python scripts/setup_vapi.py            # skapa eller uppdatera
    uv run python scripts/setup_vapi.py --dry-run  # visa bara vad som skulle skickas

Finns VAPI_ASSISTANT_ID i .env uppdateras den assistenten, annars skapas en ny
och id:t skrivs ut så att du kan lägga in det i .env.
"""

from __future__ import annotations

import argparse
import json
import os
import sys

import httpx

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.assistant_config import build_assistant_payload  # noqa: E402
from app.config import get_settings  # noqa: E402

API = "https://api.vapi.ai/assistant"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    s = get_settings()
    payload = build_assistant_payload(s)

    if args.dry_run:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 0

    fel = []
    if not s.vapi_api_key:
        fel.append("VAPI_API_KEY")
    if not s.public_base_url:
        fel.append("PUBLIC_BASE_URL (dit Vapi skickar verktygsanropen)")
    if not s.vapi_voice_id:
        fel.append("VAPI_VOICE_ID (välj röst i Vapis dashboard, steg 0b)")
    if fel:
        print("Saknar i .env: " + ", ".join(fel))
        return 1

    headers = {"Authorization": f"Bearer {s.vapi_api_key}"}
    with httpx.Client(timeout=30) as client:
        if s.vapi_assistant_id:
            svar = client.patch(f"{API}/{s.vapi_assistant_id}", headers=headers, json=payload)
        else:
            svar = client.post(API, headers=headers, json=payload)

    if svar.status_code >= 400:
        print(f"Vapi svarade {svar.status_code}:\n{svar.text}")
        if "model" in svar.text.lower():
            print(
                "\nTips: modellnamnet kan behöva ändras. Sätt VAPI_MODEL_PROVIDER och "
                "VAPI_MODEL i .env till en modell Vapi stödjer just nu."
            )
        return 1

    data = svar.json()
    print(f"Assistenten är {'uppdaterad' if s.vapi_assistant_id else 'skapad'}: {data.get('id')}")
    if not s.vapi_assistant_id:
        print(f"\nLägg in i .env:\nVAPI_ASSISTANT_ID={data.get('id')}")
    print(f"Verktygen pekar på: {s.public_base_url.rstrip('/')}/vapi/webhook")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
