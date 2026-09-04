import json

import httpx
import pytest
import respx

from app.db import Database

BAS = "https://proj.supabase.co"


@pytest.fixture
def db(settings):
    settings.supabase_url = BAS
    settings.supabase_service_key = "service-key"
    return Database(settings)


async def test_utan_konfiguration_gor_ingenting(settings):
    d = Database(settings)
    assert d.enabled is False
    assert await d.hamta_eller_skapa_samtal("call_1") is None
    assert await d.spara_meddelande(
        samtal_id=None, namn="A", telefon="1", arende="x", bradskande=False
    ) is None


@respx.mock
async def test_befintligt_samtal_ateranvands(db):
    route = respx.get(f"{BAS}/rest/v1/samtal").mock(
        return_value=httpx.Response(200, json=[{"id": "uuid-1"}])
    )
    assert await db.hamta_eller_skapa_samtal("call_1") == "uuid-1"
    assert "eq.call_1" in str(route.calls[0].request.url)


@respx.mock
async def test_nytt_samtal_skapas(db):
    respx.get(f"{BAS}/rest/v1/samtal").mock(return_value=httpx.Response(200, json=[]))
    respx.post(f"{BAS}/rest/v1/samtal").mock(
        return_value=httpx.Response(201, json=[{"id": "uuid-2"}])
    )
    assert await db.hamta_eller_skapa_samtal("call_2", "+46709998877") == "uuid-2"


@respx.mock
async def test_service_key_foljer_med(db):
    route = respx.get(f"{BAS}/rest/v1/samtal").mock(
        return_value=httpx.Response(200, json=[{"id": "u"}])
    )
    await db.hamta_eller_skapa_samtal("call_1")
    headers = route.calls[0].request.headers
    assert headers["apikey"] == "service-key"
    assert headers["authorization"] == "Bearer service-key"


@respx.mock
async def test_fel_fran_supabase_kastas_inte_vidare(db):
    """Ett lasfel far inte leda till att en dubblettrad skapas."""
    respx.get(f"{BAS}/rest/v1/samtal").mock(return_value=httpx.Response(500, text="boom"))
    skapa = respx.post(f"{BAS}/rest/v1/samtal")
    assert await db.hamta_eller_skapa_samtal("call_1") is None
    assert not skapa.called


@respx.mock
async def test_avsluta_samtal_skriver_inte_over_bokning(db):
    respx.get(f"{BAS}/rest/v1/samtal").mock(
        return_value=httpx.Response(200, json=[{"id": "u", "utfall": "bokning"}])
    )
    patch = respx.patch(f"{BAS}/rest/v1/samtal").mock(return_value=httpx.Response(200, json=[]))

    await db.avsluta_samtal("call_1", transkript="...", avbrutet=True)
    kropp = json.loads(patch.calls[0].request.content)
    assert "utfall" not in kropp
    assert kropp["transkript"] == "..."


@respx.mock
async def test_samtal_utan_utfall_blir_avbrutet(db):
    respx.get(f"{BAS}/rest/v1/samtal").mock(
        return_value=httpx.Response(200, json=[{"id": "u", "utfall": "okant"}])
    )
    patch = respx.patch(f"{BAS}/rest/v1/samtal").mock(return_value=httpx.Response(200, json=[]))

    await db.avsluta_samtal("call_1", transkript="...", avbrutet=True)
    assert json.loads(patch.calls[0].request.content)["utfall"] == "avbrutet"
