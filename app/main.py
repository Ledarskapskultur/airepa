"""FastAPI-appen: webhook, hälsokoll och webbwidgeten."""

from __future__ import annotations

import logging
from pathlib import Path

from fastapi import FastAPI, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.config import get_settings
from app.webhook import router as webhook_router

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

app = FastAPI(title="AI-telefonassistent", version="0.1.0")

# Webbwidgeten kan bäddas in på ledarskapskultur.se.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

app.include_router(webhook_router)


@app.get("/health")
async def health():
    s = get_settings()
    return {
        "status": "ok",
        "kalender": bool(s.google_refresh_token),
        "sms": bool(s.elks_api_user),
        "supabase": bool(s.supabase_url),
        "assistent": bool(s.vapi_assistant_id),
    }


@app.get("/config.js")
async def web_config():
    """Publik konfiguration till webbwidgeten. Bara publik nyckel, inga hemligheter."""
    s = get_settings()
    js = (
        "window.AIREPA_CONFIG = {\n"
        f'  publicKey: "{s.vapi_public_key}",\n'
        f'  assistantId: "{s.vapi_assistant_id}"\n'
        "};\n"
    )
    return Response(content=js, media_type="application/javascript")


WEB_DIR = Path(__file__).resolve().parent.parent / "web"
if WEB_DIR.is_dir():
    app.mount("/", StaticFiles(directory=WEB_DIR, html=True), name="web")
