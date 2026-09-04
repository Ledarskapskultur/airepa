from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

from app.calendar_service import CalendarService
from tests.fakes import FakeCalendarAPI

TZ = ZoneInfo("Europe/Stockholm")


def handelse(start: str, slut: str, **extra) -> dict:
    return {"start": {"dateTime": start}, "end": {"dateTime": slut}, **extra}


def heldag(datum: str, till: str) -> dict:
    return {"start": {"date": datum}, "end": {"date": till}}


@pytest.fixture
def kalender(settings):
    def bygg(items=None):
        api = FakeCalendarAPI(items or [])
        return CalendarService(settings, service=api), api

    return bygg


def test_lediga_tider_hoppar_over_bokad_tid(kalender):
    cal, _ = kalender([handelse("2026-09-07T09:00:00+02:00", "2026-09-07T10:00:00+02:00")])
    tider = cal.find_free_slots(nu=datetime(2026, 9, 4, 12, tzinfo=TZ))
    ider = [t.id for t in tider]
    assert "2026-09-07T09:00" not in ider
    assert ider[0] == "2026-09-07T08:00"


def test_heldagshandelse_blockerar_kursdagen(kalender):
    cal, _ = kalender([heldag("2026-09-07", "2026-09-08")])
    tider = cal.find_free_slots(nu=datetime(2026, 9, 4, 12, tzinfo=TZ))
    assert all(not t.id.startswith("2026-09-07") for t in tider)


def test_flerdagars_heldagshandelse_blockerar_alla_dagar(kalender):
    cal, _ = kalender([heldag("2026-09-07", "2026-09-10")])
    tider = cal.find_free_slots(nu=datetime(2026, 9, 4, 12, tzinfo=TZ))
    assert all(t.start.date().day >= 10 for t in tider)


def test_avbokad_handelse_blockerar_inte(kalender):
    cal, _ = kalender(
        [
            handelse(
                "2026-09-07T08:00:00+02:00", "2026-09-07T09:00:00+02:00", status="cancelled"
            )
        ]
    )
    tider = cal.find_free_slots(nu=datetime(2026, 9, 4, 12, tzinfo=TZ))
    assert tider[0].id == "2026-09-07T08:00"


def test_handelse_man_tackat_nej_till_blockerar_inte(kalender):
    cal, _ = kalender(
        [
            handelse(
                "2026-09-07T08:00:00+02:00",
                "2026-09-07T09:00:00+02:00",
                attendees=[{"self": True, "responseStatus": "declined"}],
            )
        ]
    )
    assert cal.find_free_slots(nu=datetime(2026, 9, 4, 12, tzinfo=TZ))[0].id == "2026-09-07T08:00"


def test_tider_hamtas_i_ratt_kalender_och_fonster(kalender):
    cal, api = kalender()
    cal.find_free_slots(nu=datetime(2026, 9, 4, 12, tzinfo=TZ))
    anrop = api.list_calls[0]
    assert anrop["calendarId"] == "primary"
    assert anrop["singleEvents"] is True
    assert anrop["timeMin"].startswith("2026-09-07")
    assert anrop["timeMax"].startswith("2026-09-19")


def test_is_free_ser_nytt_mote(kalender):
    start = datetime(2026, 9, 7, 10, 0, tzinfo=TZ)
    cal, _ = kalender([handelse("2026-09-07T10:00:00+02:00", "2026-09-07T10:30:00+02:00")])
    assert cal.is_free(start) is False


def test_is_free_pa_tom_kalender(kalender):
    cal, _ = kalender()
    assert cal.is_free(datetime(2026, 9, 7, 10, 0, tzinfo=TZ)) is True


def test_is_free_respekterar_bufferten(kalender):
    # Möte 10:30–11:00 ligger direkt efter en tid som börjar 10:00 – för tätt.
    cal, _ = kalender([handelse("2026-09-07T10:30:00+02:00", "2026-09-07T11:00:00+02:00")])
    assert cal.is_free(datetime(2026, 9, 7, 10, 0, tzinfo=TZ)) is False


def test_create_event_skickar_ratt_falt(kalender):
    cal, api = kalender()
    event_id = cal.create_event(
        datetime(2026, 9, 7, 10, 0, tzinfo=TZ), "Anna Berg", "+46701234567", "Fråga om UGL"
    )
    assert event_id == "evt_1"
    body = api.inserted[0]["body"]
    assert body["summary"] == "Telefonmöte: Anna Berg"
    assert "+46701234567" in body["description"]
    assert "Fråga om UGL" in body["description"]
    assert body["start"]["dateTime"].startswith("2026-09-07T10:00")
    assert body["end"]["dateTime"].startswith("2026-09-07T10:30")
    assert body["start"]["timeZone"] == "Europe/Stockholm"


def test_parse_slot_id_ger_stockholmstid(kalender):
    cal, _ = kalender()
    start = cal.parse_slot_id("2026-09-07T10:00")
    assert start.hour == 10
    assert start.utcoffset().total_seconds() == 2 * 3600  # sommartid
