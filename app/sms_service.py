"""Utgående meddelanden. SMS via 46elks, med e-post via Resend som fallback."""

from __future__ import annotations

import logging

import httpx

from app.config import Settings, get_settings

logger = logging.getLogger(__name__)

ELKS_SMS_URL = "https://api.46elks.com/a1/sms"
RESEND_URL = "https://api.resend.com/emails"


class NotifyError(RuntimeError):
    pass


class NotifyService:
    def __init__(self, settings: Settings | None = None):
        self.settings = settings or get_settings()

    # -- SMS ---------------------------------------------------------------

    async def send_sms(self, till: str, meddelande: str) -> bool:
        s = self.settings
        if not (s.elks_api_user and s.elks_api_password):
            logger.warning("46elks saknar inloggning – SMS till %s skickades inte", till)
            return False
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                svar = await client.post(
                    ELKS_SMS_URL,
                    auth=(s.elks_api_user, s.elks_api_password),
                    data={"from": s.elks_from_number, "to": till, "message": meddelande},
                )
            if svar.status_code >= 400:
                logger.error("46elks svarade %s: %s", svar.status_code, svar.text)
                return False
            logger.info("SMS skickat till %s", till)
            return True
        except httpx.HTTPError as exc:
            logger.error("SMS till %s misslyckades: %s", till, exc)
            return False

    # -- E-post ------------------------------------------------------------

    async def send_email(self, till: str, amne: str, text: str) -> bool:
        s = self.settings
        if not (s.resend_api_key and s.email_from and till):
            logger.warning("Resend saknar konfiguration – mejl till %s skickades inte", till)
            return False
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                svar = await client.post(
                    RESEND_URL,
                    headers={"Authorization": f"Bearer {s.resend_api_key}"},
                    json={"from": s.email_from, "to": [till], "subject": amne, "text": text},
                )
            if svar.status_code >= 400:
                logger.error("Resend svarade %s: %s", svar.status_code, svar.text)
                return False
            return True
        except httpx.HTTPError as exc:
            logger.error("Mejl till %s misslyckades: %s", till, exc)
            return False

    # -- Gemensamt ---------------------------------------------------------

    async def notify_owner(self, meddelande: str, amne: str = "AI-assistenten") -> bool:
        """Till Carl-Fredrik, via den kanal som är vald i NOTIFY_CHANNEL."""
        s = self.settings
        if s.notify_channel == "email":
            return await self.send_email(s.owner_email, amne, meddelande)
        return await self.send_sms(s.owner_phone, meddelande)

    async def notify_caller(self, telefon: str, meddelande: str) -> bool:
        """Till uppringaren. Alltid SMS – vi har bara ett telefonnummer."""
        return await self.send_sms(telefon, meddelande)
