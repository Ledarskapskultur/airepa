"""Google Calendar: hitta lediga tider och skapa bokningar.

OAuth med refresh token för Carl-Fredriks eget konto. Ett service account
kommer inte åt en privat Gmail-kalender, därför användarens egna credentials.
Kör scripts/auth_google.py en gång för att få fram GOOGLE_REFRESH_TOKEN.
"""

from __future__ import annotations

import logging
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from app.config import Settings, get_settings
from app.slots import Busy, Slot, berakna_lediga_tider, nasta_arbetsdag

logger = logging.getLogger(__name__)

TOKEN_URI = "https://oauth2.googleapis.com/token"
SCOPES = ["https://www.googleapis.com/auth/calendar"]


class CalendarService:
    def __init__(self, settings: Settings | None = None, service=None):
        self.settings = settings or get_settings()
        self.tz = ZoneInfo(self.settings.tz)
        self._service = service

    # -- Google-koppling ---------------------------------------------------

    def service(self):
        if self._service is None:
            self._service = self._build_service()
        return self._service

    def _build_service(self):
        from google.oauth2.credentials import Credentials
        from googleapiclient.discovery import build

        s = self.settings
        if not (s.google_client_id and s.google_client_secret and s.google_refresh_token):
            raise RuntimeError(
                "Google Calendar saknar konfiguration. Sätt GOOGLE_CLIENT_ID, "
                "GOOGLE_CLIENT_SECRET och GOOGLE_REFRESH_TOKEN (se scripts/auth_google.py)."
            )
        creds = Credentials(
            token=None,
            refresh_token=s.google_refresh_token,
            client_id=s.google_client_id,
            client_secret=s.google_client_secret,
            token_uri=TOKEN_URI,
            scopes=SCOPES,
        )
        return build("calendar", "v3", credentials=creds, cache_discovery=False)

    # -- Läsning -----------------------------------------------------------

    def _hamta_handelser(self, fran: datetime, till: datetime) -> list[dict]:
        resultat: list[dict] = []
        sida = None
        while True:
            svar = (
                self.service()
                .events()
                .list(
                    calendarId=self.settings.google_calendar_id,
                    timeMin=fran.isoformat(),
                    timeMax=till.isoformat(),
                    singleEvents=True,
                    orderBy="startTime",
                    maxResults=250,
                    pageToken=sida,
                )
                .execute()
            )
            resultat.extend(svar.get("items", []))
            sida = svar.get("nextPageToken")
            if not sida:
                return resultat

    def _tolka_handelser(self, handelser: list[dict]) -> tuple[list[Busy], set[date]]:
        """Delar upp i tidsatta möten och heldagshändelser (som blockerar hela dagen)."""
        upptaget: list[Busy] = []
        blockerade: set[date] = set()
        for h in handelser:
            if h.get("status") == "cancelled":
                continue
            # Tider man tackat nej till blockerar inte kalendern.
            if any(
                d.get("self") and d.get("responseStatus") == "declined"
                for d in h.get("attendees", [])
            ):
                continue
            if h.get("transparency") == "transparent":
                continue

            start, slut = h.get("start", {}), h.get("end", {})
            if "date" in start:  # heldagshändelse, t.ex. en kursdag
                d = date.fromisoformat(start["date"])
                sista = date.fromisoformat(slut.get("date", start["date"]))
                while d < sista:
                    blockerade.add(d)
                    d += timedelta(days=1)
            elif "dateTime" in start and "dateTime" in slut:
                upptaget.append(
                    Busy(
                        start=datetime.fromisoformat(start["dateTime"]).astimezone(self.tz),
                        end=datetime.fromisoformat(slut["dateTime"]).astimezone(self.tz),
                    )
                )
        return upptaget, blockerade

    def _fonster(self, nu: datetime) -> tuple[datetime, datetime]:
        s = self.settings
        forsta = nasta_arbetsdag(nu.date())
        sista = nu.date() + timedelta(days=s.max_days_ahead)
        fran = datetime.combine(forsta, datetime.min.time(), tzinfo=self.tz)
        till = datetime.combine(sista + timedelta(days=1), datetime.min.time(), tzinfo=self.tz)
        return fran, till

    def find_free_slots(self, onskad_period: str = "", nu: datetime | None = None) -> list[Slot]:
        s = self.settings
        nu = nu or datetime.now(self.tz)
        fran, till = self._fonster(nu)
        upptaget, blockerade = self._tolka_handelser(self._hamta_handelser(fran, till))
        return berakna_lediga_tider(
            nu,
            upptaget,
            blockerade,
            tz=self.tz,
            onskad_period=onskad_period,
            start_hour=s.workday_start_hour,
            end_hour=s.workday_end_hour,
            meeting_minutes=s.meeting_minutes,
            buffer_minutes=s.buffer_minutes,
            max_days_ahead=s.max_days_ahead,
            max_slots=s.max_slots,
        )

    def is_free(self, start: datetime) -> bool:
        """Kollar en enskild tid, direkt mot kalendern (tiden kan ha tagits under samtalet)."""
        s = self.settings
        marginal = timedelta(minutes=s.buffer_minutes + s.meeting_minutes + 60)
        handelser = self._hamta_handelser(start - marginal, start + marginal)
        upptaget, blockerade = self._tolka_handelser(handelser)
        if start.date() in blockerade:
            return False
        from app.slots import ar_ledig

        return ar_ledig(
            start,
            upptaget,
            meeting_minutes=s.meeting_minutes,
            buffer_minutes=s.buffer_minutes,
        )

    # -- Skrivning ---------------------------------------------------------

    def create_event(
        self,
        start: datetime,
        namn: str,
        telefon: str,
        arende: str = "",
    ) -> str:
        """Skapar mötet och returnerar Googles event-id."""
        s = self.settings
        slut = start + timedelta(minutes=s.meeting_minutes)
        beskrivning = f"Telefon: {telefon}"
        if arende:
            beskrivning += f"\nÄrende: {arende}"
        beskrivning += "\n\nBokat av AI-telefonassistenten."

        handelse = (
            self.service()
            .events()
            .insert(
                calendarId=s.google_calendar_id,
                body={
                    "summary": f"Telefonmöte: {namn}",
                    "description": beskrivning,
                    "start": {"dateTime": start.isoformat(), "timeZone": s.tz},
                    "end": {"dateTime": slut.isoformat(), "timeZone": s.tz},
                },
            )
            .execute()
        )
        logger.info("Skapade kalenderhändelse %s för %s", handelse.get("id"), namn)
        return handelse.get("id", "")

    def parse_slot_id(self, tid_id: str) -> datetime:
        """'2026-09-08T10:00' -> tidszonsmedveten datetime i Europe/Stockholm."""
        return datetime.fromisoformat(tid_id).replace(tzinfo=self.tz)
