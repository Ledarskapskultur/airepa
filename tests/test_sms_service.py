import httpx
import pytest
import respx

from app.sms_service import ELKS_SMS_URL, RESEND_URL, NotifyService


@pytest.fixture
def notify(settings):
    return NotifyService(settings)


@respx.mock
async def test_sms_skickas_till_46elks(notify):
    route = respx.post(ELKS_SMS_URL).mock(
        return_value=httpx.Response(200, json={"id": "s1", "status": "created"})
    )
    assert await notify.send_sms("+46701234567", "Hej!") is True

    begaran = route.calls[0].request
    kropp = dict(pair.split("=", 1) for pair in begaran.content.decode().split("&"))
    assert kropp["from"] == "CFZ"
    assert kropp["to"] == "%2B46701234567"
    assert begaran.headers["authorization"].startswith("Basic ")


@respx.mock
async def test_sms_fel_kastar_inte_vidare(notify):
    respx.post(ELKS_SMS_URL).mock(return_value=httpx.Response(401, text="unauthorized"))
    assert await notify.send_sms("+46701234567", "Hej!") is False


@respx.mock
async def test_natverksfel_ger_false(notify):
    respx.post(ELKS_SMS_URL).mock(side_effect=httpx.ConnectError("nere"))
    assert await notify.send_sms("+46701234567", "Hej!") is False


async def test_sms_utan_inloggning_skickas_inte(settings):
    settings.elks_api_user = ""
    assert await NotifyService(settings).send_sms("+46701234567", "Hej!") is False


@respx.mock
async def test_notify_owner_gar_till_agarens_mobil(notify):
    route = respx.post(ELKS_SMS_URL).mock(return_value=httpx.Response(200, json={}))
    assert await notify.notify_owner("Ny bokning") is True
    assert "to=%2B46701112233" in route.calls[0].request.content.decode()


@respx.mock
async def test_notify_owner_kan_ga_via_mejl(settings):
    settings.notify_channel = "email"
    settings.resend_api_key = "re_test"
    settings.email_from = "assistent@example.se"
    settings.owner_email = "cf@example.se"
    route = respx.post(RESEND_URL).mock(return_value=httpx.Response(200, json={"id": "e1"}))

    assert await NotifyService(settings).notify_owner("Ny bokning", amne="Bokning") is True
    kropp = route.calls[0].request.content.decode()
    assert "cf@example.se" in kropp
    assert "Bokning" in kropp
