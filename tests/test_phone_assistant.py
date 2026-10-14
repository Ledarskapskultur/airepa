"""Tester för phone-assistant. Inga riktiga anrop: transporten är en attrapp."""

import importlib.util
import json
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parent.parent / "phone-assistant" / "phone_assistant.py"
KEY = "sk-hemlig-testnyckel-1234567890"


@pytest.fixture
def pa(tmp_path, monkeypatch):
    monkeypatch.setenv("PHONE_ASSISTANT_CONFIG_DIR", str(tmp_path / "cfg"))
    monkeypatch.setenv("PHONE_ASSISTANT_STATE_DIR", str(tmp_path / "state"))
    monkeypatch.setenv("BLAND_API_KEY", KEY)
    spec = importlib.util.spec_from_file_location("phone_assistant", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class FakeBland:
    _next_id = 0

    def __init__(self, call=None, balance=10.0, polls_before_done=1):
        FakeBland._next_id += 1
        self.call_id = f"c-{FakeBland._next_id}"
        self.requests = []
        self.balance = balance
        self.polls_left = polls_before_done
        self.call = call or {
            "status": "completed", "completed": True, "answered_by": "human",
            "call_length": 1.2, "price": 0.11, "summary": "Vill ha hjälp med offerten.",
            "transcripts": [
                {"user": "assistant", "text": "Hej! Det här är din AI-assistent ..."},
                {"user": "user", "text": "Jag vill att du gör klart offerten till Volvo."},
                {"user": "assistant", "text": "Jag uppfattade att du vill ... Stämmer det?"},
                {"user": "user", "text": "Ja, det stämmer."},
            ],
        }

    def __call__(self, method, url, headers, body, timeout):
        self.requests.append((method, url, headers, json.loads(body) if body else None))
        if url.endswith("/me"):
            return 200, json.dumps({"billing": {"current_balance": self.balance}}).encode()
        if method == "POST" and url.endswith("/calls"):
            return 200, json.dumps({"status": "success", "call_id": self.call_id}).encode()
        if url.endswith(f"/calls/{self.call_id}"):
            if self.polls_left > 0:
                self.polls_left -= 1
                return 200, json.dumps({"status": "started", "completed": False}).encode()
            return 200, json.dumps(self.call).encode()
        return 404, b"{}"


def cfg(pa, **kw):
    c = dict(pa.DEFAULTS, owner_number="+46701234567", verified_at="2026-01-01T00:00:00+00:00")
    c.update(kw)
    return c


@pytest.mark.parametrize("raw", ["070-123 45 67", "+46 70 123 45 67", "0046701234567",
                                 "46701234567", "+460701234567"])
def test_normalize_swedish_mobile(pa, raw):
    assert pa.normalize_swedish_mobile(raw) == "+46701234567"


@pytest.mark.parametrize("raw", ["08-123 456 78", "+4512345678", "0701", "", "+4670123456789"])
def test_rejects_non_swedish_mobile(pa, raw):
    with pytest.raises(pa.PhoneError):
        pa.normalize_swedish_mobile(raw)


def test_check_does_not_call(pa):
    fake = FakeBland()
    res = pa.cmd_check(cfg(pa), transport=fake)
    assert res["api_connection"] == "ok"
    assert res["balance_usd"] == 10.0
    assert res["called_anyone"] is False
    assert [r[0] for r in fake.requests] == ["GET"]
    assert KEY not in json.dumps(res)


def test_ask_full_flow(pa):
    fake = FakeBland()
    res = pa.place_call(cfg(pa), "Vad vill du?", None, test=False, transport=fake,
                        sleep=lambda s: None)
    post = next(r for r in fake.requests if r[0] == "POST")
    body = post[3]
    assert post[2]["authorization"] == KEY
    assert body["phone_number"] == "+46701234567"
    assert body["language"] == "sv"
    assert body["max_duration"] == 3
    assert body["record"] is False
    assert res["status"] == "completed"
    assert "Volvo" in res["user_answer"]
    assert res["confirmed_on_call"] is True
    assert res["needs_clarification"] is False
    assert res["price_usd"] == 0.11
    saved = json.loads(Path(res["transcript_file"]).read_text())
    assert "Du: Ja, det stämmer." in saved["transcript"]


def test_test_call_uses_exact_greeting(pa):
    fake = FakeBland()
    pa.place_call(cfg(pa, verified_at=None), "x", None, test=True, transport=fake,
                  sleep=lambda s: None)
    body = next(r for r in fake.requests if r[0] == "POST")[3]
    assert body["first_sentence"] == (
        "Hej! Det här är din AI-assistent som ringer via Claude Code. Jag vill kontrollera att "
        "vår telefonkoppling fungerar. Vilken uppgift vill du att jag ska hjälpa dig med idag?"
    )


def test_ask_requires_verified_number(pa):
    with pytest.raises(pa.PhoneError, match="inte verifierat"):
        pa.place_call(cfg(pa, verified_at=None), "Fråga?", None, test=False,
                      transport=FakeBland())


def test_ask_requires_number(pa):
    with pytest.raises(pa.PhoneError, match="nummer"):
        pa.place_call(cfg(pa, owner_number=""), "Fråga?", None, test=False,
                      transport=FakeBland())


def test_tampered_number_rejected(pa):
    with pytest.raises(pa.PhoneError):
        pa.place_call(cfg(pa, owner_number="+1900555000"), "Fråga?", None, test=False,
                      transport=FakeBland())


def test_extra_cannot_override_number_or_duration(pa):
    fake = FakeBland()
    c = cfg(pa, bland_extra={"phone_number": "+15550000000", "max_duration": 60, "voice": "x"})
    pa.place_call(c, "Fråga?", None, test=False, transport=fake, sleep=lambda s: None)
    body = next(r for r in fake.requests if r[0] == "POST")[3]
    assert body["phone_number"] == "+46701234567"
    assert body["max_duration"] == 3
    assert body["voice"] == "x"


def test_call_limit_per_day(pa):
    c = cfg(pa, max_calls_per_day=2, max_calls_per_hour=10)
    for _ in range(2):
        pa.place_call(c, "Fråga?", None, test=False, transport=FakeBland(),
                      sleep=lambda s: None)
    with pytest.raises(pa.PhoneError, match="Dygnstaket"):
        pa.place_call(c, "Fråga?", None, test=False, transport=FakeBland())


def test_cost_cap_per_call(pa):
    with pytest.raises(pa.PhoneError, match="kostnad"):
        pa.place_call(cfg(pa, max_duration_minutes=10), "Fråga?", None, test=False,
                      transport=FakeBland())


def test_low_balance_blocks_call(pa):
    fake = FakeBland(balance=0.2)
    with pytest.raises(pa.PhoneError, match="saldo"):
        pa.place_call(cfg(pa), "Fråga?", None, test=False, transport=fake)
    assert all(r[0] == "GET" for r in fake.requests)


def test_unclear_answer_flags_clarification(pa):
    call = {"status": "completed", "completed": True, "answered_by": "voicemail",
            "transcripts": [{"user": "assistant", "text": "Hej"}]}
    res = pa.place_call(cfg(pa), "Fråga?", None, test=False, transport=FakeBland(call=call),
                        sleep=lambda s: None)
    assert res["needs_clarification"] is True
    assert res["uncertainty_reasons"]


def test_401_is_reported_without_key(pa):
    def deny(method, url, headers, body, timeout):
        return 401, json.dumps({"message": f"bad key {KEY}"}).encode()
    with pytest.raises(pa.PhoneError) as e:
        pa.cmd_check(cfg(pa), transport=deny)
    assert KEY not in str(e.value)


def test_post_is_never_retried_on_network_error(pa):
    calls = []

    def flaky(method, url, headers, body, timeout):
        calls.append(method)
        if url.endswith("/me"):
            return 200, b'{"billing": {"current_balance": 5}}'
        raise TimeoutError("timeout")
    with pytest.raises(pa.PhoneError):
        pa.place_call(cfg(pa), "Fråga?", None, test=False, transport=flaky)
    assert calls.count("POST") == 1


def test_cli_ask_without_confirm_refuses(pa, capsys):
    assert pa.main(["ask", "--question", "Hej?"]) == 2
    assert "--confirm" in capsys.readouterr().out


def test_verify_requires_human_answered_test_call(pa, capsys):
    pa.save_config(cfg(pa, verified_at=None))
    pa.append_ledger({"call_id": "c-9", "kind": "test", "started_at": "2026-01-01T00:00:00+00:00"})
    pa.append_ledger({"call_id": "c-9", "status": "completed", "human_answered": False})
    assert pa.main(["verify", "c-9"]) == 2
    pa.append_ledger({"call_id": "c-9", "human_answered": True})
    assert pa.main(["verify", "c-9"]) == 0
    assert pa.load_config()["verified_at"]


def test_changing_number_resets_verification(pa):
    pa.save_config(cfg(pa))
    pa.main(["set-number", "0731234567"])
    c = pa.load_config()
    assert c["owner_number"] == "+46731234567"
    assert c["verified_at"] is None


def test_config_never_shows_key(pa, capsys):
    pa.main(["config"])
    out = capsys.readouterr().out
    assert KEY not in out
    assert "miljövariabel" in out
