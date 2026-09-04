"""Enkla attrapper: Google Calendar, notifieringar och databas."""

from __future__ import annotations


class FakeEvents:
    def __init__(self, service: FakeCalendarAPI):
        self._service = service

    def list(self, **kwargs):
        self._service.list_calls.append(kwargs)
        return _Exec({"items": list(self._service.items)})

    def insert(self, *, calendarId, body):
        self._service.inserted.append({"calendarId": calendarId, "body": body})
        return _Exec({"id": f"evt_{len(self._service.inserted)}"})


class _Exec:
    def __init__(self, resultat):
        self._resultat = resultat

    def execute(self):
        return self._resultat


class FakeCalendarAPI:
    """Står in för googleapiclient-resursen."""

    def __init__(self, items=None):
        self.items = items or []
        self.inserted: list[dict] = []
        self.list_calls: list[dict] = []

    def events(self):
        return FakeEvents(self)


class FakeNotify:
    def __init__(self, lyckas=True):
        self.lyckas = lyckas
        self.till_uppringare: list[tuple[str, str]] = []
        self.till_agare: list[str] = []

    async def notify_caller(self, telefon, meddelande):
        self.till_uppringare.append((telefon, meddelande))
        return self.lyckas

    async def notify_owner(self, meddelande, amne="AI-assistenten"):
        self.till_agare.append(meddelande)
        return self.lyckas


class FakeDb:
    def __init__(self):
        self.bokningar: list[dict] = []
        self.meddelanden: list[dict] = []
        self.utfall: list[tuple[str, str]] = []
        self.avslutade: list[dict] = []

    async def hamta_eller_skapa_samtal(self, vapi_call_id, fran_nummer=None):
        return f"samtal-{vapi_call_id}" if vapi_call_id else None

    async def spara_bokning(self, **kw):
        self.bokningar.append(kw)
        return "bokning-1"

    async def spara_meddelande(self, **kw):
        self.meddelanden.append(kw)
        return "meddelande-1"

    async def satt_utfall(self, vapi_call_id, utfall):
        self.utfall.append((vapi_call_id, utfall))

    async def avsluta_samtal(self, vapi_call_id, **kw):
        self.avslutade.append({"vapi_call_id": vapi_call_id, **kw})
