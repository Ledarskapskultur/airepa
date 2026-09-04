"""Supabase (PostgREST). Loggning av samtal, bokningar och meddelanden.

Loggning får aldrig fälla ett pågående samtal: alla fel fångas och loggas.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

import httpx

from app.config import Settings, get_settings

logger = logging.getLogger(__name__)


class Database:
    def __init__(self, settings: Settings | None = None):
        self.settings = settings or get_settings()

    @property
    def enabled(self) -> bool:
        return bool(self.settings.supabase_url and self.settings.supabase_service_key)

    def _headers(self, prefer: str = "return=representation") -> dict[str, str]:
        nyckel = self.settings.supabase_service_key
        return {
            "apikey": nyckel,
            "Authorization": f"Bearer {nyckel}",
            "Content-Type": "application/json",
            "Prefer": prefer,
        }

    def _url(self, tabell: str) -> str:
        return f"{self.settings.supabase_url.rstrip('/')}/rest/v1/{tabell}"

    async def _request(self, metod: str, tabell: str, **kwargs) -> list[dict] | None:
        if not self.enabled:
            logger.debug("Supabase är inte konfigurerat – hoppar över %s %s", metod, tabell)
            return None
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                svar = await client.request(
                    metod, self._url(tabell), headers=self._headers(), **kwargs
                )
            if svar.status_code >= 400:
                logger.error("Supabase %s %s: %s %s", metod, tabell, svar.status_code, svar.text)
                return None
            return svar.json() if svar.content else []
        except (httpx.HTTPError, ValueError) as exc:
            logger.error("Supabase %s %s misslyckades: %s", metod, tabell, exc)
            return None

    # -- samtal ------------------------------------------------------------

    async def hamta_eller_skapa_samtal(
        self, vapi_call_id: str, fran_nummer: str | None = None
    ) -> str | None:
        """Returnerar samtalets uuid. Skapar raden om den inte finns."""
        if not vapi_call_id:
            return None
        rader = await self._request(
            "GET",
            "samtal",
            params={"vapi_call_id": f"eq.{vapi_call_id}", "select": "id", "limit": "1"},
        )
        if rader is None:
            return None  # läsfel: skapa inte en dubblett på en gissning
        if rader:
            return rader[0]["id"]
        skapade = await self._request(
            "POST",
            "samtal",
            json={
                "vapi_call_id": vapi_call_id,
                "fran_nummer": fran_nummer,
                "startad_at": datetime.now().astimezone().isoformat(),
                "utfall": "okant",
            },
        )
        return skapade[0]["id"] if skapade else None

    async def uppdatera_samtal(self, vapi_call_id: str, **falt: Any) -> None:
        if not vapi_call_id:
            return
        rensat = {k: v for k, v in falt.items() if v is not None}
        if not rensat:
            return
        await self._request(
            "PATCH", "samtal", params={"vapi_call_id": f"eq.{vapi_call_id}"}, json=rensat
        )

    async def satt_utfall(self, vapi_call_id: str, utfall: str) -> None:
        await self.uppdatera_samtal(vapi_call_id, utfall=utfall)

    # -- bokningar ---------------------------------------------------------

    async def spara_bokning(
        self,
        *,
        samtal_id: str | None,
        namn: str,
        telefon: str,
        arende: str,
        start_at: datetime,
        google_event_id: str,
        sms_skickat: bool,
    ) -> str | None:
        rader = await self._request(
            "POST",
            "bokningar",
            json={
                "samtal_id": samtal_id,
                "namn": namn,
                "telefon": telefon,
                "arende": arende or None,
                "start_at": start_at.isoformat(),
                "google_event_id": google_event_id or None,
                "sms_skickat": sms_skickat,
            },
        )
        return rader[0]["id"] if rader else None

    # -- meddelanden -------------------------------------------------------

    async def spara_meddelande(
        self,
        *,
        samtal_id: str | None,
        namn: str,
        telefon: str,
        arende: str,
        bradskande: bool,
    ) -> str | None:
        rader = await self._request(
            "POST",
            "meddelanden",
            json={
                "samtal_id": samtal_id,
                "namn": namn or None,
                "telefon": telefon or None,
                "arende": arende,
                "bradskande": bradskande,
            },
        )
        return rader[0]["id"] if rader else None

    async def avsluta_samtal(
        self,
        vapi_call_id: str,
        *,
        fran_nummer: str | None = None,
        startad_at: str | None = None,
        avslutad_at: str | None = None,
        varaktighet_sek: int | None = None,
        transkript: str | None = None,
        sammanfattning: str | None = None,
        avbrutet: bool = False,
    ) -> None:
        """Skriver slutrapporten. Skriver aldrig över ett utfall som redan är satt."""
        if not vapi_call_id:
            return
        await self.hamta_eller_skapa_samtal(vapi_call_id, fran_nummer)
        falt: dict[str, Any] = {
            "fran_nummer": fran_nummer,
            "startad_at": startad_at,
            "avslutad_at": avslutad_at,
            "varaktighet_sek": varaktighet_sek,
            "transkript": transkript,
            "sammanfattning": sammanfattning,
        }
        if avbrutet:
            rader = await self._request(
                "GET",
                "samtal",
                params={"vapi_call_id": f"eq.{vapi_call_id}", "select": "utfall", "limit": "1"},
            )
            nuvarande = rader[0]["utfall"] if rader else None
            if nuvarande in (None, "okant"):
                falt["utfall"] = "avbrutet"
        await self.uppdatera_samtal(vapi_call_id, **falt)
