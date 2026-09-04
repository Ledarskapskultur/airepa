import hashlib
import hmac
import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest
from fastapi.testclient import TestClient

import app.webhook as webhook
from app.calendar_service import CalendarService
from app.tools import Tools
from tests.fakes import FakeCalendarAPI, FakeDb, FakeNotify

TZ = ZoneInfo("Europe/Stockholm")
NU = datetime(2026, 9, 4, 12, tzinfo=TZ)
FIXTURES = Path(__file__).parent / "fixtures"
HEMLIGHET = "test-hemlighet"


def payload(namn: str) -> dict:
    return json.loads((FIXTURES / f"{namn}.json").read_text())


@pytest.fixture
def klient(settings, monkeypatch):
    import app.main as main_module
    from app.main import app

    api = FakeCalendarAPI()
    cal = CalendarService(settings, service=api)
    original = cal.find_free_slots
    monkeypatch.setattr(
        cal, "find_free_slots", lambda onskad_period="", nu=None: original(onskad_period, NU)
    )
    notify, db = FakeNotify(), FakeDb()
    tools = Tools(settings, calendar=cal, notify=notify, db=db)

    monkeypatch.setattr(webhook, "_tools", tools)
    monkeypatch.setattr(webhook, "get_settings", lambda: settings)
    monkeypatch.setattr(main_module, "get_settings", lambda: settings)

    with TestClient(app) as c:
        yield c, tools, notify, db, api


def posta(klient, data: dict, *, secret: str | None = HEMLIGHET, signatur: str | None = None):
    kropp = json.dumps(data).encode()
    headers = {"content-type": "application/json"}
    if secret is not None:
        headers["x-vapi-secret"] = secret
    if signatur is not None:
        headers["x-vapi-signature"] = signatur
    return klient.post("/vapi/webhook", content=kropp, headers=headers)


# -- signatur ---------------------------------------------------------------

def test_utan_hemlighet_avvisas(klient):
    c, *_ = klient
    assert posta(c, payload("status_update"), secret=None).status_code == 401


def test_fel_hemlighet_avvisas(klient):
    c, *_ = klient
    assert posta(c, payload("status_update"), secret="fel").status_code == 401


def test_hmac_signatur_accepteras(klient):
    c, *_ = klient
    data = payload("status_update")
    kropp = json.dumps(data).encode()
    sig = hmac.new(HEMLIGHET.encode(), kropp, hashlib.sha256).hexdigest()
    svar = c.post(
        "/vapi/webhook",
        content=kropp,
        headers={"content-type": "application/json", "x-vapi-signature": sig},
    )
    assert svar.status_code == 200


def test_fel_hmac_avvisas(klient):
    c, *_ = klient
    assert posta(c, payload("status_update"), secret=None, signatur="ab" * 32).status_code == 401


# -- verktygsanrop ----------------------------------------------------------

def test_hamta_lediga_tider_via_webhook(klient):
    c, *_ = klient
    svar = posta(c, payload("tool_call_lediga_tider"))
    assert svar.status_code == 200

    resultat = svar.json()["results"][0]
    assert resultat["toolCallId"] == "call_abc123"
    tider = json.loads(resultat["result"])["tider"]
    assert len(tider) == 3
    assert all("id" in t and "text" in t for t in tider)


def test_boka_mote_via_webhook_med_argument_som_strang(klient):
    c, _, notify, db, api = klient
    svar = posta(c, payload("tool_call_boka_mote"))
    assert svar.status_code == 200

    resultat = json.loads(svar.json()["results"][0]["result"])
    assert resultat == {"status": "ok", "tid_text": "måndag 7 september klockan 10"}
    assert api.inserted[0]["body"]["summary"] == "Telefonmöte: Anna Berg"
    assert len(notify.till_uppringare) == 1
    assert len(notify.till_agare) == 1
    assert db.bokningar[0]["namn"] == "Anna Berg"


def test_aldre_function_call_format_fungerar(klient):
    c, _, notify, db, _ = klient
    svar = posta(c, payload("function_call_legacy"))
    assert svar.status_code == 200
    assert json.loads(svar.json()["result"])["status"] == "ok"
    assert notify.till_agare[0].startswith("BRÅDSKANDE: ")
    assert db.meddelanden[0]["arende"] == "Undrar över en offert."


def test_okant_meddelandetyp_kvitteras(klient):
    c, *_ = klient
    svar = posta(c, payload("status_update"))
    assert svar.status_code == 200
    assert svar.json() == {"status": "ok"}


def test_trasig_json_ger_400(klient):
    c, *_ = klient
    svar = c.post(
        "/vapi/webhook",
        content=b"{inte json",
        headers={"content-type": "application/json", "x-vapi-secret": HEMLIGHET},
    )
    assert svar.status_code == 400


# -- slutrapport ------------------------------------------------------------

def test_end_of_call_report_sparas(klient):
    c, _, _, db, _ = klient
    svar = posta(c, payload("end_of_call_report"))
    assert svar.status_code == 200

    rad = db.avslutade[0]
    assert rad["vapi_call_id"] == "5f1a2b3c-0000-4444-8888-99887766aabb"
    assert rad["fran_nummer"] == "+46709998877"
    assert rad["varaktighet_sek"] == 155
    assert "Jag skulle vilja boka en tid." in rad["transkript"]
    assert rad["sammanfattning"].startswith("Uppringaren bokade")
    assert rad["avbrutet"] is True


# -- övriga endpoints -------------------------------------------------------

def test_health(klient):
    c, *_ = klient
    assert c.get("/health").json()["status"] == "ok"


def test_config_js_exponerar_bara_publik_nyckel(klient, settings):
    c, *_ = klient
    settings.vapi_public_key = "pk_test"
    settings.vapi_assistant_id = "asst_test"
    svar = c.get("/config.js")
    assert "pk_test" in svar.text
    assert "asst_test" in svar.text
    assert settings.vapi_api_key not in svar.text or not settings.vapi_api_key


def test_webbsidan_serveras(klient):
    c, *_ = klient
    svar = c.get("/")
    assert svar.status_code == 200
    assert "Prata med assistenten" in svar.text
