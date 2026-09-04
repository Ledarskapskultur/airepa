from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

from app.calendar_service import CalendarService
from app.tools import CallContext, Tools
from tests.fakes import FakeCalendarAPI, FakeDb, FakeNotify

TZ = ZoneInfo("Europe/Stockholm")
NU = datetime(2026, 9, 4, 12, tzinfo=TZ)
CTX = CallContext(vapi_call_id="call_1", fran_nummer="+46709998877")


@pytest.fixture
def verktyg(settings, monkeypatch):
    def bygg(items=None):
        api = FakeCalendarAPI(items or [])
        cal = CalendarService(settings, service=api)
        # Frys tiden så testerna inte ändrar sig med kalendern.
        original = cal.find_free_slots
        monkeypatch.setattr(
            cal, "find_free_slots", lambda onskad_period="", nu=None: original(onskad_period, NU)
        )
        notify, db = FakeNotify(), FakeDb()
        return Tools(settings, calendar=cal, notify=notify, db=db), notify, db, api

    return bygg


# -- hamta_lediga_tider -----------------------------------------------------

async def test_hamta_lediga_tider_ger_tre_forslag(verktyg):
    tools, *_ = verktyg()
    svar = await tools.dispatch("hamta_lediga_tider", {"onskad_period": ""}, CTX)
    assert len(svar["tider"]) == 3
    assert set(svar["tider"][0]) == {"id", "text"}
    assert svar["tider"][0]["text"] == "måndag 7 september klockan 8"


async def test_hamta_lediga_tider_utan_lediga_tider(verktyg, monkeypatch):
    tools, *_ = verktyg()
    monkeypatch.setattr(tools.calendar, "find_free_slots", lambda *a, **k: [])
    svar = await tools.dispatch("hamta_lediga_tider", {}, CTX)
    assert svar["tider"] == []
    assert "meddelande" in svar


# -- boka_mote --------------------------------------------------------------

async def test_boka_mote_hela_kedjan(verktyg):
    tools, notify, db, api = verktyg()
    svar = await tools.dispatch(
        "boka_mote",
        {
            "tid_id": "2026-09-07T10:00",
            "namn": "Anna Berg",
            "telefon": "070-123 45 67",
            "arende": "Vill veta mer om UGL",
        },
        CTX,
    )

    assert svar == {"status": "ok", "tid_text": "måndag 7 september klockan 10"}

    # Kalendern
    assert api.inserted[0]["body"]["summary"] == "Telefonmöte: Anna Berg"

    # SMS till uppringaren, i kravspecens ordalydelse
    till, text = notify.till_uppringare[0]
    assert till == "+46701234567"
    assert text == (
        "Hej Anna Berg! Ditt telefonmöte med Carl-Fredrik Zettermark är bokat "
        "måndag 7 september klockan 10. Han ringer dig på detta nummer. "
        "Hälsningar, Ledarskapskultur"
    )

    # SMS till Carl-Fredrik
    assert notify.till_agare[0] == (
        "Ny bokning: Anna Berg, +46701234567, måndag 7 september klockan 10. "
        "Ärende: Vill veta mer om UGL"
    )

    # Loggat
    assert db.bokningar[0]["namn"] == "Anna Berg"
    assert db.bokningar[0]["telefon"] == "+46701234567"
    assert db.bokningar[0]["google_event_id"] == "evt_1"
    assert db.bokningar[0]["sms_skickat"] is True
    assert ("call_1", "bokning") in db.utfall


async def test_boka_mote_pa_upptagen_tid(verktyg):
    upptaget = [
        {
            "start": {"dateTime": "2026-09-07T10:00:00+02:00"},
            "end": {"dateTime": "2026-09-07T10:30:00+02:00"},
        }
    ]
    tools, notify, db, api = verktyg(upptaget)
    svar = await tools.dispatch(
        "boka_mote",
        {"tid_id": "2026-09-07T10:00", "namn": "Anna", "telefon": "0701234567"},
        CTX,
    )
    assert svar == {"status": "upptagen"}
    assert api.inserted == []
    assert notify.till_uppringare == []
    assert db.bokningar == []


async def test_boka_mote_utan_telefon(verktyg):
    tools, notify, _, api = verktyg()
    svar = await tools.dispatch(
        "boka_mote", {"tid_id": "2026-09-07T10:00", "namn": "Anna"}, CTX
    )
    assert svar["status"] == "fel"
    assert api.inserted == []
    assert notify.till_uppringare == []


async def test_boka_mote_med_trasigt_tid_id(verktyg):
    tools, _, _, api = verktyg()
    svar = await tools.dispatch(
        "boka_mote",
        {"tid_id": "på måndag typ", "namn": "Anna", "telefon": "0701234567"},
        CTX,
    )
    assert svar["status"] == "fel"
    assert api.inserted == []


async def test_boka_mote_utan_arende(verktyg):
    tools, notify, _, _ = verktyg()
    svar = await tools.dispatch(
        "boka_mote",
        {"tid_id": "2026-09-07T10:00", "namn": "Anna", "telefon": "0701234567"},
        CTX,
    )
    assert svar["status"] == "ok"
    assert notify.till_agare[0].endswith("klockan 10.")


async def test_bokningen_star_kvar_aven_om_sms_fallerar(verktyg):
    tools, notify, db, api = verktyg()
    notify.lyckas = False
    svar = await tools.dispatch(
        "boka_mote",
        {"tid_id": "2026-09-07T10:00", "namn": "Anna", "telefon": "0701234567"},
        CTX,
    )
    assert svar["status"] == "ok"
    assert api.inserted
    assert db.bokningar[0]["sms_skickat"] is False


# -- skicka_meddelande ------------------------------------------------------

async def test_skicka_meddelande(verktyg):
    tools, notify, db, _ = verktyg()
    svar = await tools.dispatch(
        "skicka_meddelande",
        {
            "namn": "Erik Lund",
            "telefon": "070-123 45 67",
            "arende": "Undrar över en offert.",
            "bradskande": False,
        },
        CTX,
    )
    assert svar == {"status": "ok"}
    assert notify.till_agare[0] == (
        "Meddelande från Erik Lund (+46701234567): Undrar över en offert."
    )
    assert db.meddelanden[0]["bradskande"] is False
    assert ("call_1", "meddelande") in db.utfall


async def test_bradskande_meddelande_markeras(verktyg):
    tools, notify, db, _ = verktyg()
    await tools.dispatch(
        "skicka_meddelande",
        {"namn": "Erik", "telefon": "0701234567", "arende": "Akut.", "bradskande": True},
        CTX,
    )
    assert notify.till_agare[0].startswith("BRÅDSKANDE: ")
    assert db.meddelanden[0]["bradskande"] is True


async def test_meddelande_utan_arende(verktyg):
    tools, notify, db, _ = verktyg()
    svar = await tools.dispatch(
        "skicka_meddelande", {"namn": "Erik", "telefon": "0701234567"}, CTX
    )
    assert svar["status"] == "fel"
    assert notify.till_agare == []
    assert db.meddelanden == []


# -- felhantering -----------------------------------------------------------

async def test_okant_verktyg_ger_fel_utan_krasch(verktyg):
    tools, *_ = verktyg()
    svar = await tools.dispatch("radera_kalendern", {}, CTX)
    assert svar["status"] == "fel"


async def test_krasch_blir_ett_vanligt_svar(verktyg, monkeypatch):
    tools, *_ = verktyg()

    def sprangs(*a, **k):
        raise RuntimeError("Google nere")

    monkeypatch.setattr(tools.calendar, "find_free_slots", sprangs)
    svar = await tools.dispatch("hamta_lediga_tider", {}, CTX)
    assert svar["status"] == "fel"
    assert "meddelande" in svar
