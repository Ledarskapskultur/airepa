"""De tre verktygen assistenten kan anropa."""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass

from app.calendar_service import CalendarService
from app.config import Settings, get_settings
from app.db import Database
from app.sms_service import NotifyService
from app.swedish import normalisera_telefon, tid_text

logger = logging.getLogger(__name__)


@dataclass
class CallContext:
    vapi_call_id: str = ""
    fran_nummer: str = ""


class Tools:
    def __init__(
        self,
        settings: Settings | None = None,
        calendar: CalendarService | None = None,
        notify: NotifyService | None = None,
        db: Database | None = None,
    ):
        self.settings = settings or get_settings()
        self.calendar = calendar or CalendarService(self.settings)
        self.notify = notify or NotifyService(self.settings)
        self.db = db or Database(self.settings)

    async def dispatch(self, namn: str, args: dict, ctx: CallContext) -> dict:
        hanterare = {
            "hamta_lediga_tider": self.hamta_lediga_tider,
            "boka_mote": self.boka_mote,
            "skicka_meddelande": self.skicka_meddelande,
        }.get(namn)
        if hanterare is None:
            logger.warning("Okänt verktyg: %s", namn)
            return {"status": "fel", "meddelande": f"Okänt verktyg: {namn}"}
        try:
            return await hanterare(args or {}, ctx)
        except Exception:
            logger.exception("Verktyget %s kraschade", namn)
            return {
                "status": "fel",
                "meddelande": (
                    "Något gick fel på min sida. Be uppringaren om ursäkt och "
                    "erbjud att ta ett meddelande i stället."
                ),
            }

    # -- 1 -----------------------------------------------------------------

    async def hamta_lediga_tider(self, args: dict, ctx: CallContext) -> dict:
        onskad = (args.get("onskad_period") or "").strip()
        tider = await asyncio.to_thread(self.calendar.find_free_slots, onskad)
        if not tider:
            return {
                "tider": [],
                "meddelande": (
                    "Inga lediga tider de närmaste två veckorna. Erbjud att ta ett "
                    "meddelande i stället."
                ),
            }
        return {"tider": [t.as_dict() for t in tider]}

    # -- 2 -----------------------------------------------------------------

    async def boka_mote(self, args: dict, ctx: CallContext) -> dict:
        tid_id = (args.get("tid_id") or "").strip()
        namn = (args.get("namn") or "").strip()
        telefon = normalisera_telefon(args.get("telefon") or "")
        arende = (args.get("arende") or "").strip()

        if not (tid_id and namn and telefon):
            return {
                "status": "fel",
                "meddelande": "Jag saknar tid, namn eller telefonnummer. Fråga om det som fattas.",
            }

        try:
            start = self.calendar.parse_slot_id(tid_id)
        except ValueError:
            return {
                "status": "fel",
                "meddelande": "Tiden gick inte att tolka. Hämta lediga tider igen.",
            }

        if not await asyncio.to_thread(self.calendar.is_free, start):
            return {"status": "upptagen"}

        event_id = await asyncio.to_thread(
            self.calendar.create_event, start, namn, telefon, arende
        )

        text = tid_text(start)
        till_uppringare = (
            f"Hej {namn}! Ditt telefonmöte med Carl-Fredrik Zettermark är bokat {text}. "
            "Han ringer dig på detta nummer. Hälsningar, Ledarskapskultur"
        )
        till_agare = f"Ny bokning: {namn}, {telefon}, {text}."
        if arende:
            till_agare += f" Ärende: {arende}"

        # Båda meddelandena parallellt, så bekräftelsen är framme inom sekunder.
        uppringare_ok, _ = await asyncio.gather(
            self.notify.notify_caller(telefon, till_uppringare),
            self.notify.notify_owner(till_agare, amne="Ny bokning"),
        )

        samtal_id = await self.db.hamta_eller_skapa_samtal(ctx.vapi_call_id, ctx.fran_nummer)
        await self.db.spara_bokning(
            samtal_id=samtal_id,
            namn=namn,
            telefon=telefon,
            arende=arende,
            start_at=start,
            google_event_id=event_id,
            sms_skickat=bool(uppringare_ok),
        )
        await self.db.satt_utfall(ctx.vapi_call_id, "bokning")

        return {"status": "ok", "tid_text": text}

    # -- 3 -----------------------------------------------------------------

    async def skicka_meddelande(self, args: dict, ctx: CallContext) -> dict:
        namn = (args.get("namn") or "").strip()
        telefon = normalisera_telefon(args.get("telefon") or "")
        arende = (args.get("arende") or "").strip()
        bradskande = bool(args.get("bradskande"))

        if not arende:
            return {
                "status": "fel",
                "meddelande": "Jag saknar ärendet. Fråga vad det gäller.",
            }

        prefix = "BRÅDSKANDE: " if bradskande else ""
        text = f"{prefix}Meddelande från {namn} ({telefon}): {arende}"
        skickat = await self.notify.notify_owner(text, amne="Nytt meddelande")

        samtal_id = await self.db.hamta_eller_skapa_samtal(ctx.vapi_call_id, ctx.fran_nummer)
        await self.db.spara_meddelande(
            samtal_id=samtal_id,
            namn=namn,
            telefon=telefon,
            arende=arende,
            bradskande=bradskande,
        )
        await self.db.satt_utfall(ctx.vapi_call_id, "meddelande")

        return {"status": "ok" if skickat else "ok_ej_levererat"}
