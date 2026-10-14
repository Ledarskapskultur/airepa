#!/usr/bin/env python3
"""Personlig AI-telefon för Claude Code via Bland.ai.

Ringer ENBART ägarens eget, verifierade mobilnummer, ställer en kort fråga på
svenska, väntar in samtalet och skriver ut svaret som JSON på stdout.

Bara standardbiblioteket – fungerar med valfri python3 >= 3.9.

Kommandon:
    setup-key                 Ange BLAND_API_KEY dolt (lagras i nyckelring eller 0600-fil)
    set-number <nummer>       Spara ditt svenska mobilnummer (+467XXXXXXXX)
    check                     Kontrollera API-anslutningen – ringer INTE
    test --confirm            Testsamtal (kräver godkännande)
    ask --question ... --confirm   Ställ en fråga per telefon
    verify <call_id>          Markera numret som verifierat efter lyckat testsamtal
    status|transcript|stop <call_id>
    usage                     Samtal och kostnad i dag
    config                    Visa inställningar (aldrig nyckeln)

Nyckeln skrivs aldrig ut, loggas aldrig och skickas bara i authorization-headern
till api.bland.ai.
"""

from __future__ import annotations

import argparse
import datetime as dt
import getpass
import json
import os
import re
import shutil
import stat
import subprocess
import sys
import time
import urllib.error
import urllib.request
from collections.abc import Callable
from pathlib import Path
from typing import Any

API_BASE = os.environ.get("BLAND_API_BASE", "https://api.bland.ai/v1")
KEYRING_SERVICE = "claude-phone-assistant"
KEYRING_ACCOUNT = "BLAND_API_KEY"

CONFIG_DIR = Path(os.environ.get("PHONE_ASSISTANT_CONFIG_DIR", "~/.config/phone-assistant")).expanduser()
STATE_DIR = Path(os.environ.get("PHONE_ASSISTANT_STATE_DIR", "~/.local/state/phone-assistant")).expanduser()

TEST_SENTENCE = (
    "Hej! Det här är din AI-assistent som ringer via Claude Code. Jag vill kontrollera "
    "att vår telefonkoppling fungerar. Vilken uppgift vill du att jag ska hjälpa dig med idag?"
)

DEFAULTS: dict[str, Any] = {
    "owner_number": "",
    "verified_at": None,
    "language": "sv",
    "voice": "",                       # tomt = Bland:s standardröst
    "max_duration_minutes": 3,         # hård gräns per samtal
    "max_calls_per_day": 5,
    "max_calls_per_hour": 3,
    "cost_per_minute_usd": 0.14,       # konservativ uppskattning, används före samtalet
    "max_cost_per_call_usd": 0.50,
    "max_cost_per_day_usd": 2.00,
    "min_balance_usd": 1.00,
    "poll_interval_seconds": 5,
    "http_timeout_seconds": 20,
    "bland_extra": {},                 # valfria extra fält till POST /v1/calls
}

TERMINAL_STATUSES = {"completed", "complete", "failed", "error", "canceled", "cancelled",
                     "no-answer", "no_answer", "busy", "ended", "stopped"}

SWEDISH_MOBILE = re.compile(r"^\+467\d{8}$")


class PhoneError(Exception):
    """Fel som visas för användaren. Får aldrig innehålla nyckeln."""


# --------------------------------------------------------------------------- utils

def _redact(text: str, key: str | None) -> str:
    if key and key in text:
        text = text.replace(key, "***")
    return re.sub(r"(sk-|org_)[A-Za-z0-9_\-]{8,}", r"\1***", text)


def _now() -> dt.datetime:
    return dt.datetime.now(dt.UTC)


def _out(obj: Any) -> None:
    print(json.dumps(obj, ensure_ascii=False, indent=2))


def normalize_swedish_mobile(raw: str) -> str:
    """'070-123 45 67', '0046701234567', '+46 70 123 45 67' -> '+46701234567'."""
    s = re.sub(r"[\s\-().]", "", raw or "")
    if s.startswith("00"):
        s = "+" + s[2:]
    elif s.startswith("0"):
        s = "+46" + s[1:]
    elif s.startswith("46"):
        s = "+" + s
    if s.startswith("+460"):
        s = "+46" + s[4:]
    if not SWEDISH_MOBILE.match(s):
        raise PhoneError(
            "Ogiltigt nummer. Ange ett svenskt mobilnummer, t.ex. +46701234567."
        )
    return s


def mask_number(number: str) -> str:
    return number[:5] + "*" * max(0, len(number) - 7) + number[-2:] if number else ""


# ------------------------------------------------------------------------- config

def config_path() -> Path:
    return CONFIG_DIR / "config.json"


def load_config() -> dict[str, Any]:
    cfg = dict(DEFAULTS)
    p = config_path()
    if p.exists():
        cfg.update(json.loads(p.read_text(encoding="utf-8")))
    return cfg


def save_config(cfg: dict[str, Any]) -> None:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    p = config_path()
    p.write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8")
    os.chmod(p, 0o600)


# ------------------------------------------------------------------------ secrets

def _key_file() -> Path:
    return CONFIG_DIR / "bland_api_key"


def get_api_key() -> str | None:
    """Ordning: miljövariabel -> macOS Keychain -> Linux Secret Service -> 0600-fil."""
    env = os.environ.get("BLAND_API_KEY", "").strip()
    if env:
        return env
    if sys.platform == "darwin" and shutil.which("security"):
        r = subprocess.run(
            ["security", "find-generic-password", "-s", KEYRING_SERVICE, "-a", KEYRING_ACCOUNT, "-w"],
            capture_output=True, text=True,
        )
        if r.returncode == 0 and r.stdout.strip():
            return r.stdout.strip()
    if shutil.which("secret-tool"):
        r = subprocess.run(
            ["secret-tool", "lookup", "service", KEYRING_SERVICE, "account", KEYRING_ACCOUNT],
            capture_output=True, text=True,
        )
        if r.returncode == 0 and r.stdout.strip():
            return r.stdout.strip()
    f = _key_file()
    if f.exists():
        mode = stat.S_IMODE(f.stat().st_mode)
        if mode & 0o077:
            raise PhoneError(f"{f} har för öppna rättigheter. Kör: chmod 600 {f}")
        return f.read_text(encoding="utf-8").strip() or None
    return None


def key_source() -> str:
    if os.environ.get("BLAND_API_KEY", "").strip():
        return "miljövariabel BLAND_API_KEY"
    if _key_file().exists():
        return f"fil {_key_file()} (0600)"
    return "nyckelring" if get_api_key() else "saknas"


def store_key_macos_interactive() -> bool:
    """Låter `security` själv fråga efter nyckeln dolt, så den aldrig syns i processlistan."""
    if sys.platform != "darwin" or not shutil.which("security"):
        return False
    print("macOS frågar nu efter nyckeln två gånger (inmatningen visas inte).")
    r = subprocess.run(["security", "add-generic-password", "-U", "-s", KEYRING_SERVICE,
                        "-a", KEYRING_ACCOUNT, "-w"])
    return r.returncode == 0


def store_api_key(key: str) -> str:
    if shutil.which("secret-tool"):
        r = subprocess.run(
            ["secret-tool", "store", "--label=Bland.ai API key", "service", KEYRING_SERVICE,
             "account", KEYRING_ACCOUNT],
            input=key, capture_output=True, text=True,
        )
        if r.returncode == 0:
            return "Secret Service (secret-tool)"
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    os.chmod(CONFIG_DIR, 0o700)
    f = _key_file()
    fd = os.open(f, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as fh:
        fh.write(key)
    os.chmod(f, 0o600)
    return f"fil {f} (0600)"


# --------------------------------------------------------------------------- HTTP

Transport = Callable[[str, str, dict[str, str], bytes | None, float], tuple[int, bytes]]


def _urllib_transport(method: str, url: str, headers: dict[str, str], body: bytes | None,
                      timeout: float) -> tuple[int, bytes]:
    req = urllib.request.Request(url, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status, resp.read()
    except urllib.error.HTTPError as e:
        return e.code, e.read()


class Bland:
    def __init__(self, key: str, timeout: float = 20, transport: Transport | None = None):
        self._key = key
        self._timeout = timeout
        self._transport = transport or _urllib_transport

    def _req(self, method: str, path: str, payload: dict | None = None) -> dict:
        headers = {"authorization": self._key, "accept": "application/json",
                   "user-agent": "claude-phone-assistant/1.0"}
        body = None
        if payload is not None:
            headers["content-type"] = "application/json"
            body = json.dumps(payload).encode()
        last_exc: Exception | None = None
        for attempt in range(3):
            try:
                status, raw = self._transport(method, API_BASE + path, headers, body, self._timeout)
            except Exception as e:  # nätverk, DNS, timeout
                last_exc = e
                # Upprepa aldrig ett POST som kan ha startat ett samtal.
                if method != "GET":
                    break
                time.sleep(2 ** attempt)
                continue
            text = raw.decode("utf-8", "replace")
            try:
                data = json.loads(text) if text else {}
            except json.JSONDecodeError:
                data = {"raw": text[:300]}
            if status in (401, 403):
                raise PhoneError("Bland.ai nekade nyckeln (401/403). Kontrollera BLAND_API_KEY.")
            if status == 429 or (status >= 500 and method == "GET"):
                last_exc = PhoneError(f"Bland.ai svarade {status}")
                time.sleep(2 ** attempt)
                continue
            if status >= 400:
                msg = data.get("message") or data.get("error") or data.get("errors") or data
                raise PhoneError(_redact(f"Bland.ai fel {status}: {msg}", self._key))
            return data if isinstance(data, dict) else {"data": data}
        raise PhoneError(_redact(f"Kunde inte nå Bland.ai: {last_exc}", self._key))

    def me(self) -> dict:
        return self._req("GET", "/me")

    def send_call(self, payload: dict) -> dict:
        return self._req("POST", "/calls", payload)

    def get_call(self, call_id: str) -> dict:
        return self._req("GET", f"/calls/{call_id}")

    def stop_call(self, call_id: str) -> dict:
        return self._req("POST", f"/calls/{call_id}/stop", {})


def extract_balance(me: dict) -> float | None:
    for path in (("billing", "current_balance"), ("billing", "balance"), ("current_balance",),
                 ("balance",), ("user", "billing", "current_balance")):
        node: Any = me
        for k in path:
            node = node.get(k) if isinstance(node, dict) else None
        if isinstance(node, (int, float, str)):
            try:
                return float(node)
            except ValueError:
                pass
    return None


# ------------------------------------------------------------------------ ledger

def _ledger() -> Path:
    return STATE_DIR / "calls.jsonl"


def read_ledger() -> list[dict]:
    p = _ledger()
    if not p.exists():
        return []
    rows = []
    for line in p.read_text(encoding="utf-8").splitlines():
        if line.strip():
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return rows


def append_ledger(row: dict) -> None:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    with _ledger().open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(row, ensure_ascii=False) + "\n")


def usage_today(now: dt.datetime | None = None) -> dict[str, Any]:
    now = now or _now()
    latest: dict[str, dict] = {}
    for r in read_ledger():
        k = r.get("call_id") or r.get("started_at", "")
        latest[k] = {**latest.get(k, {}), **r}
    calls_day = calls_hour = 0
    cost = 0.0
    for r in latest.values():
        started = r.get("started_at")
        if not started:
            continue
        t = dt.datetime.fromisoformat(started)
        if now - t < dt.timedelta(hours=24):
            calls_day += 1
            c = r.get("price_usd")
            cost += float(c) if c is not None else float(r.get("estimated_cost_usd") or 0)
        if now - t < dt.timedelta(hours=1):
            calls_hour += 1
    return {"calls_last_24h": calls_day, "calls_last_hour": calls_hour,
            "cost_last_24h_usd": round(cost, 4)}


def enforce_limits(cfg: dict, minutes: float) -> float:
    """Kastar PhoneError om något tak nås. Returnerar uppskattad maxkostnad."""
    u = usage_today()
    if u["calls_last_24h"] >= cfg["max_calls_per_day"]:
        raise PhoneError(f"Dygnstaket på {cfg['max_calls_per_day']} samtal är nått.")
    if u["calls_last_hour"] >= cfg["max_calls_per_hour"]:
        raise PhoneError(f"Timtaket på {cfg['max_calls_per_hour']} samtal är nått.")
    est = round(minutes * float(cfg["cost_per_minute_usd"]), 4)
    if est > float(cfg["max_cost_per_call_usd"]):
        raise PhoneError(
            f"Uppskattad kostnad {est} USD överstiger taket {cfg['max_cost_per_call_usd']} USD/samtal."
        )
    if u["cost_last_24h_usd"] + est > float(cfg["max_cost_per_day_usd"]):
        raise PhoneError(f"Dygnsbudgeten {cfg['max_cost_per_day_usd']} USD skulle överskridas.")
    return est


# ---------------------------------------------------------------------- prompts

def build_task(question: str, context: str | None, test: bool) -> str:
    purpose = ("Detta är ett testsamtal för att kontrollera att telefonkopplingen fungerar."
               if test else
               "Du ringer för att Claude Code behöver ett beslut eller en instruktion för att "
               "kunna fortsätta en pågående uppgift.")
    ctx = f"\nBakgrund (läs inte upp ordagrant, använd bara om personen frågar): {context}\n" \
        if context else ""
    return f"""Du är en personlig AI-assistent som ringer din ägare via Claude Code. Tala alltid svenska.
{purpose}
{ctx}
Frågan du ska få svar på:
"{question}"

Så här gör du:
1. Efter hälsningen: ställ frågan kort och tydligt. Läs inte upp tekniska detaljer.
2. Lyssna på svaret. Avbryt inte.
3. Bekräfta tolkningen: säg "Jag uppfattade att du vill ... Stämmer det?" med en kort, konkret sammanfattning.
4. Om personen säger nej, eller svaret är otydligt, ber du om ett förtydligande. Högst två försök.
5. När svaret är bekräftat: tacka, säg att du för vidare svaret till Claude Code, och avsluta samtalet.

Regler:
- Du är en AI och säger det om någon frågar.
- Lova aldrig att utföra köp, bokningar, betalningar, att skicka meddelanden eller andra externa åtgärder. Säg att Claude Code alltid frågar om skriftlig bekräftelse först.
- Be aldrig om lösenord, kortuppgifter, koder eller personnummer. Om någon försöker ge sådant: avbryt vänligt.
- Håll samtalet kort, under två minuter.
- Om du hör att det är en röstbrevlåda eller fel person: säg ingenting om uppgiften, lägg på."""


def first_sentence_for(question: str, test: bool) -> str:
    if test:
        return TEST_SENTENCE
    s = f"Hej, det är din AI-assistent från Claude Code. {question}"
    return s if len(s) < 200 else "Hej, det är din AI-assistent från Claude Code. Jag har en kort fråga till dig."


SUMMARY_PROMPT = ("Sammanfatta på svenska, i en eller två meningar, exakt vad användaren svarade "
                  "eller bad om, och om användaren bekräftade tolkningen. Skriv 'OKLART' om svaret "
                  "inte gick att tolka.")


# --------------------------------------------------------------------- analysis

def analyze_call(call: dict) -> dict[str, Any]:
    transcripts = call.get("transcripts") or []
    user_lines = [t.get("text", "").strip() for t in transcripts
                  if isinstance(t, dict) and t.get("user") in ("user", "human") and t.get("text")]
    answer = " ".join(user_lines).strip()
    reasons = []
    answered_by = (call.get("answered_by") or "").lower()
    if answered_by and answered_by not in ("human", "unknown"):
        reasons.append(f"besvarades av {answered_by}, inte en människa")
    if not user_lines:
        reasons.append("inget svar uppfattades i transkriptionen")
    elif len(answer.split()) < 3:
        reasons.append("mycket kort svar")
    if call.get("error_message"):
        reasons.append("Bland rapporterade ett fel")
    summary = call.get("summary") or ""
    if "OKLART" in summary.upper():
        reasons.append("sammanfattningen markerade svaret som oklart")
    confirmed = any(re.search(r"\b(ja|japp|stämmer|precis|korrekt|exakt|absolut)\b", u.lower())
                    for u in user_lines[1:]) if len(user_lines) > 1 else False
    return {
        "user_answer": answer,
        "summary": summary,
        "confirmed_on_call": confirmed,
        "needs_clarification": bool(reasons),
        "uncertainty_reasons": reasons,
    }


def format_transcript(call: dict) -> str:
    rows = []
    for t in call.get("transcripts") or []:
        who = {"user": "Du", "human": "Du", "assistant": "AI", "agent": "AI"}.get(t.get("user"), None)
        if who and t.get("text"):
            rows.append(f"{who}: {t['text'].strip()}")
    return "\n".join(rows) or (call.get("concatenated_transcript") or "")


def save_transcript(call_id: str, call: dict, analysis: dict) -> Path:
    d = STATE_DIR / "transcripts"
    d.mkdir(parents=True, exist_ok=True)
    p = d / f"{call_id}.json"
    p.write_text(json.dumps({"call_id": call_id, "transcript": format_transcript(call),
                             "analysis": analysis, "raw": call}, ensure_ascii=False, indent=2),
                 encoding="utf-8")
    os.chmod(p, 0o600)
    return p


# ---------------------------------------------------------------------- calling

def _client(cfg: dict, transport: Transport | None = None) -> Bland:
    key = get_api_key()
    if not key:
        raise PhoneError("BLAND_API_KEY saknas. Kör 'setup-key' eller sätt miljövariabeln.")
    return Bland(key, timeout=float(cfg["http_timeout_seconds"]), transport=transport)


def place_call(cfg: dict, question: str, context: str | None, test: bool,
               transport: Transport | None = None, sleep: Callable[[float], None] = time.sleep,
               wait: bool = True) -> dict[str, Any]:
    number = cfg.get("owner_number")
    if not number:
        raise PhoneError("Inget eget nummer är konfigurerat. Kör 'set-number +467...'.")
    normalize_swedish_mobile(number)  # dubbelkoll mot manipulerad config
    if not test and not cfg.get("verified_at"):
        raise PhoneError("Numret är inte verifierat. Gör testsamtalet först och kör sedan 'verify'.")
    question = question.strip()
    if not question or len(question) > 400:
        raise PhoneError("Frågan måste vara 1–400 tecken.")

    minutes = float(cfg["max_duration_minutes"])
    if not 0.5 <= minutes <= 10:
        raise PhoneError("max_duration_minutes måste ligga mellan 0.5 och 10.")
    est = enforce_limits(cfg, minutes)
    client = _client(cfg, transport)

    balance = extract_balance(client.me())
    if balance is not None and balance < max(float(cfg["min_balance_usd"]), est):
        raise PhoneError(f"För lågt saldo hos Bland.ai ({balance:.2f} USD).")

    payload: dict[str, Any] = {
        "phone_number": number,
        "task": build_task(question, context, test),
        "first_sentence": first_sentence_for(question, test),
        "language": cfg["language"],
        "max_duration": minutes,
        "wait_for_greeting": True,
        "record": False,
        "temperature": 0.3,
        "summary_prompt": SUMMARY_PROMPT,
        "metadata": {"source": "claude-code-phone-assistant", "kind": "test" if test else "ask"},
    }
    if cfg.get("voice"):
        payload["voice"] = cfg["voice"]
    for k, v in (cfg.get("bland_extra") or {}).items():
        if k not in ("phone_number", "max_duration"):  # säkerhetsfälten går inte att åsidosätta
            payload[k] = v

    resp = client.send_call(payload)
    call_id = resp.get("call_id")
    if not call_id:
        raise PhoneError(f"Bland.ai startade inget samtal: {resp.get('message') or resp}")
    started = _now().isoformat()
    append_ledger({"call_id": call_id, "started_at": started, "kind": payload["metadata"]["kind"],
                   "to": mask_number(number), "question": question,
                   "estimated_cost_usd": est, "status": "queued"})
    if not wait:
        return {"call_id": call_id, "status": "queued"}
    return wait_for_call(cfg, client, call_id, minutes, sleep)


def wait_for_call(cfg: dict, client: Bland, call_id: str, minutes: float,
                  sleep: Callable[[float], None] = time.sleep) -> dict[str, Any]:
    deadline = time.monotonic() + minutes * 60 + 180  # ringtid + köande
    call: dict = {}
    while True:
        call = client.get_call(call_id)
        status = str(call.get("status") or call.get("queue_status") or "").lower()
        if call.get("completed") or status in TERMINAL_STATUSES:
            break
        if time.monotonic() > deadline:
            try:
                client.stop_call(call_id)
            except PhoneError:
                pass
            call = client.get_call(call_id)
            status = "timeout"
            break
        sleep(float(cfg["poll_interval_seconds"]))

    analysis = analyze_call(call)
    price = call.get("price")
    try:
        price = float(price) if price is not None else None
    except (TypeError, ValueError):
        price = None
    path = save_transcript(call_id, call, analysis)
    append_ledger({"call_id": call_id, "status": status, "price_usd": price,
                   "answered_by": call.get("answered_by"),
                   "human_answered": bool(analysis["user_answer"]),
                   "call_length_min": call.get("call_length"),
                   "finished_at": _now().isoformat()})
    return {
        "call_id": call_id,
        "status": status,
        "answered_by": call.get("answered_by"),
        "call_length_min": call.get("call_length"),
        "price_usd": price,
        "transcript": format_transcript(call),
        **analysis,
        "transcript_file": str(path),
        "error_message": call.get("error_message"),
    }


# -------------------------------------------------------------------------- CLI

def cmd_check(cfg: dict, transport: Transport | None = None) -> dict:
    result: dict[str, Any] = {
        "api_key": key_source(),
        "owner_number": mask_number(cfg.get("owner_number", "")) or "saknas",
        "number_verified": bool(cfg.get("verified_at")),
        "limits": {k: cfg[k] for k in ("max_duration_minutes", "max_calls_per_day",
                                        "max_calls_per_hour", "max_cost_per_call_usd",
                                        "max_cost_per_day_usd")},
        "usage": usage_today(),
        "called_anyone": False,
    }
    client = _client(cfg, transport)
    me = client.me()
    result["api_connection"] = "ok"
    result["balance_usd"] = extract_balance(me)
    result["account_fields"] = sorted(me.keys())
    return result


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="phone_assistant", description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("setup-key")
    sn = sub.add_parser("set-number")
    sn.add_argument("number")
    sub.add_parser("check")
    sub.add_parser("config")
    sub.add_parser("usage")
    t = sub.add_parser("test")
    t.add_argument("--confirm", action="store_true")
    a = sub.add_parser("ask")
    a.add_argument("--question", required=True)
    a.add_argument("--context")
    a.add_argument("--confirm", action="store_true")
    for name in ("status", "transcript", "stop", "verify"):
        p = sub.add_parser(name)
        p.add_argument("call_id")
    sl = sub.add_parser("set-limit")
    sl.add_argument("name", choices=["max_duration_minutes", "max_calls_per_day",
                                     "max_calls_per_hour", "max_cost_per_call_usd",
                                     "max_cost_per_day_usd", "cost_per_minute_usd",
                                     "min_balance_usd", "language", "voice"])
    sl.add_argument("value")
    args = ap.parse_args(argv)
    cfg = load_config()

    try:
        if args.cmd == "setup-key":
            if not sys.stdin.isatty():
                raise PhoneError("setup-key måste köras i en riktig terminal (dold inmatning).")
            if store_key_macos_interactive():
                where = "macOS Keychain"
            else:
                key = getpass.getpass("Klistra in BLAND_API_KEY (visas inte): ").strip()
                if len(key) < 10:
                    raise PhoneError("Nyckeln ser för kort ut – inget sparades.")
                where = store_api_key(key)
            print(f"Nyckeln sparades i {where}. Kör nu: check")
        elif args.cmd == "set-number":
            n = normalize_swedish_mobile(args.number)
            if cfg.get("owner_number") != n:
                cfg["verified_at"] = None
            cfg["owner_number"] = n
            save_config(cfg)
            _out({"owner_number": mask_number(n), "verified": bool(cfg.get("verified_at"))})
        elif args.cmd == "set-limit":
            v: Any = args.value
            if args.name not in ("language", "voice"):
                v = float(v) if "." in v else int(v)
            cfg[args.name] = v
            save_config(cfg)
            _out({args.name: v})
        elif args.cmd == "config":
            shown = {k: v for k, v in cfg.items()}
            shown["owner_number"] = mask_number(cfg.get("owner_number", ""))
            shown["api_key"] = key_source()
            _out(shown)
        elif args.cmd == "usage":
            _out(usage_today())
        elif args.cmd == "check":
            _out(cmd_check(cfg))
        elif args.cmd == "test":
            if not args.confirm:
                raise PhoneError("Testsamtal kräver --confirm efter ditt uttryckliga godkännande.")
            _out(place_call(cfg, "Vilken uppgift vill du att jag ska hjälpa dig med idag?",
                            None, test=True))
        elif args.cmd == "ask":
            if not args.confirm:
                raise PhoneError("Samtal kräver --confirm efter ditt uttryckliga godkännande.")
            _out(place_call(cfg, args.question, args.context, test=False))
        elif args.cmd == "verify":
            rows = [r for r in read_ledger() if r.get("call_id") == args.call_id]
            merged: dict = {}
            for r in rows:
                merged.update(r)
            if merged.get("kind") != "test" or merged.get("status") not in TERMINAL_STATUSES:
                raise PhoneError("Hittar inget avslutat testsamtal med det id:t.")
            if not merged.get("human_answered"):
                raise PhoneError("Testsamtalet fick inget svar från en människa – ring ett nytt.")
            cfg["verified_at"] = _now().isoformat()
            save_config(cfg)
            _out({"verified": True, "owner_number": mask_number(cfg["owner_number"])})
        elif args.cmd in ("status", "transcript"):
            call = _client(cfg).get_call(args.call_id)
            analysis = analyze_call(call)
            if args.cmd == "transcript":
                save_transcript(args.call_id, call, analysis)
            _out({"call_id": args.call_id, "status": call.get("status"),
                  "completed": call.get("completed"), "transcript": format_transcript(call),
                  **analysis, "price_usd": call.get("price")})
        elif args.cmd == "stop":
            _out(_client(cfg).stop_call(args.call_id))
    except PhoneError as e:
        _out({"ok": False, "error": _redact(str(e), os.environ.get("BLAND_API_KEY"))})
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
