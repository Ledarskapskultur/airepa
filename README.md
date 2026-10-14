# AI-telefonassistent för Carl-Fredrik Zettermark

Svar när Carl-Fredrik inte kan. Assistenten gör exakt två saker:

1. **Bokar** ett 30-minuters telefonmöte i Google Calendar.
2. **Tar ett meddelande** och skickar det vidare som SMS.

Den svarar inte på frågor om priser, kursinnehåll eller kursdatum. Allt sådant
hänvisas till ett bokat samtal. Den presenterar sig alltid som AI-assistent.
Inget ljud spelas in – bara transkript sparas.

## Så hänger det ihop

```
Fas 1 (nu)                        Fas 2 (senare)
Besökare på webbsida              Uppringare
  │ mikrofon, Vapi web-SDK          │
  ▼                                 ▼
                                 46elks (svenskt nummer, SIP → Vapi)
  │                                 │
  └──────────────┬──────────────────┘
                 ▼
        Vapi (STT + LLM + TTS + avbrott)
                 │  webhook vid verktygsanrop
                 ▼
     Den här servern (FastAPI)  ──▶ Google Calendar
                 │               ──▶ 46elks SMS
                 ▼
        Supabase (samtal, bokningar, meddelanden)
```

## Kom igång

```bash
git clone <repo> && cd airepa
uv venv --python 3.12
uv pip install -e ".[dev]"
cp .env.example .env          # fyll i, se docs/steg0-konton.md
uv run pytest                 # ska vara grönt utan några nycklar alls
uv run uvicorn app.main:app --reload
```

Sidan ligger då på http://localhost:8000 och webhooken på
`POST /vapi/webhook`.

Ordningen att göra saker i står i `docs/steg0-konton.md` (konton) och
`docs/steg0b-tonlage.md` (välj röst). Först därefter:

```bash
uv run python scripts/auth_google.py     # ger GOOGLE_REFRESH_TOKEN
uv run python scripts/setup_vapi.py      # skapar assistenten hos Vapi
```

`setup_vapi.py` läser prompten och verktygen från `app/assistant_config.py`, så
prompten versionshanteras här i repot – ändra den där, inte i dashboarden.

## Vad som ligger var

| Fil | Vad den gör |
|---|---|
| `app/main.py` | FastAPI: webhook, `/health`, `/config.js`, webbsidan |
| `app/webhook.py` | Tar emot Vapis anrop, kollar signatur, routar |
| `app/tools.py` | De tre verktygen |
| `app/calendar_service.py` | Google Calendar: lediga tider och bokning |
| `app/slots.py` | Ren logik för lediga tider (inga API-anrop) |
| `app/preferences.py` | Tolkar "i nästa vecka", "på eftermiddagen" |
| `app/swedish.py` | Talvänliga tider och telefonnummer |
| `app/sms_service.py` | 46elks SMS, med mejl som fallback |
| `app/db.py` | Supabase |
| `app/assistant_config.py` | Systemprompt och verktygsdefinitioner |
| `web/index.html` | Knappen "Prata med assistenten" |
| `migrations/001_init.sql` | Tabellerna |
| `docs/` | Konton, röstval, testprotokoll, telefoni |
| `phone-assistant/` | Separat Claude Code-skill: Claude ringer Carl-Fredrik via Bland.ai för beslut, se dess README |

## Bokningsreglerna

- Vardagar 08:00–17:00, Europe/Stockholm.
- Tidigast nästa arbetsdag, längst 14 dagar fram.
- 30 minuters möte, 15 minuters buffert före och efter befintliga möten.
- Heldagshändelser (kursdagar) blockerar hela dagen.
- Högst två förslag per dag, så tiderna sprids ut – men ett uttalat önskemål
  går alltid före spridningen.
- Tiderna läses upp talvänligt: "måndag 8 september klockan halv tre".

Reglerna sitter i `Settings` (`app/config.py`) och går att ändra utan att röra
logiken.

## Webbwidgeten

`web/index.html` startar samtalet via Vapis web-SDK och visar löpande
transkript. Den publika nyckeln hämtas från serverns `/config.js`, som bara
exponerar `VAPI_PUBLIC_KEY` och `VAPI_ASSISTANT_ID` – aldrig något hemligt.

Ska sidan bäddas in på ledarskapskultur.se:

```html
<iframe src="https://din-server.se/" width="100%" height="520"
        style="border:0" allow="microphone"></iframe>
```

`allow="microphone"` är nödvändigt, annars får sidan inte fråga efter mikrofonen.

## Tester

```bash
uv run pytest              # 82 tester, inga externa anrop
uv run ruff check .
```

Kalender, SMS och databas är attrapper i testerna (`tests/fakes.py`), och
webhooken testas mot inspelade Vapi-payloads i `tests/fixtures/`.

## Säkerhet

- Webhooken kräver `VAPI_WEBHOOK_SECRET`, antingen som delad hemlighet i
  `x-vapi-secret` eller som HMAC-signatur i `x-vapi-signature`. Utan rätt
  värde: 401.
- `service_role`-nyckeln och Vapis private key stannar på servern.
- Tabellerna har RLS på, så bara servern kommer åt dem.
- Inget samtalsljud sparas, bara transkript.

## Status

| Steg | |
|---|---|
| 0 – Kontolista | ✅ `docs/steg0-konton.md` |
| 0b – Röst och tonläge | ⏳ görs manuellt av Carl-Fredrik |
| 1 – Projektskelett | ✅ |
| 2 – Google Calendar | ✅ |
| 3 – SMS | ✅ |
| 4 – Supabase | ✅ migration + `db.py` |
| 5 – Webhook | ✅ |
| 6 – Vapi-konfiguration | ✅ `scripts/setup_vapi.py` |
| 7 – Webbwidget | ✅ kod klar, återstår deploy + skarpt test |
| 8 – Testprotokoll | ✅ `docs/testprotokoll.md` |
| 9 – Telefoni | ⏳ fas 2, `docs/steg9-telefoni.md` |
