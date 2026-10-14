# phone-assistant – Claude Code ringer dig när ett beslut behövs

En personlig Claude Code-skill. Claude ringer ditt eget mobilnummer via Bland.ai, ställer
en kort fråga på svenska, lyssnar på svaret, upprepar tolkningen och för tillbaka svaret till
uppgiften du höll på med.

Det här är ett separat verktyg i repot och hänger inte ihop med Vapi-assistenten i `app/`.

## Filer

| Fil | Vad |
|---|---|
| `SKILL.md` | Skillen. Regler och arbetsflöde för Claude. |
| `phone_assistant.py` | CLI mot Bland.ai v1. Bara standardbiblioteket. |
| `install.sh` | Kopierar till `~/.claude/skills/phone-assistant/` och lägger till godkännanderegler |
| `../tests/test_phone_assistant.py` | Tester mot ett fejkat API. Ringer aldrig. |

## Installation på din egen dator

```bash
cd airepa
bash phone-assistant/install.sh
PA=~/.claude/skills/phone-assistant/phone_assistant.py
python3 $PA setup-key                 # dold inmatning → Keychain / secret-tool / 0600-fil
python3 $PA set-number +467XXXXXXXX
python3 $PA check                     # testar API:t, ringer inte
```

Säg sedan till Claude: *"ring mig för ett testsamtal"*. När samtalet är klart och du har
bekräftat att det var du som svarade kör Claude `verify <call_id>`. Först då fungerar vanliga
samtal.

I en Claude Code-molnsession: lägg `BLAND_API_KEY` som hemlighet eller miljövariabel i
miljöns inställningar, och lägg till `api.bland.ai` under tillåtna domäner.

## Användning i framtida projekt

Skillen ligger i din användarkatalog, så den finns i alla projekt. Säg till exempel:

- "Ring mig och fråga om jag vill ha Postgres eller SQLite."
- "Om du kör fast på designvalet, ring mig." Claude frågar ändå först i chatten.
- `/phone-assistant` för att starta direkt.

## Säkerhet

- Ringer bara `owner_number`. Det finns ingen flagga för att ringa något annat nummer, och
  `bland_extra` kan inte ändra nummer eller samtalslängd.
- Kräver `--confirm`. Dessutom gör `install.sh` att Claude Code frågar dig innan `ask`, `test`,
  `set-number` och `set-limit` körs.
- Vanliga samtal kräver ett verifierat nummer, det vill säga ett testsamtal som en människa
  har svarat på. Byter du nummer nollställs verifieringen.
- Standardgränser: 3 minuter per samtal, 3 samtal per timme, 5 per dygn, 0,50 USD per samtal
  och 2 USD per dygn. Samtal stoppas om saldot hos Bland är under 1 USD. Ändra med
  `set-limit` (Claude ändrar bara på din begäran).
- Om samtalet tar för lång tid stoppas det via API:t. Ett POST upprepas aldrig, så ett
  nätverksfel kan inte leda till dubbla samtal.
- Inget ljud spelas in (`record: false`). Transkriptioner sparas med rättigheten 0600 i
  `~/.local/state/phone-assistant/`.
- Nyckeln skrivs aldrig ut och loggas aldrig. Felmeddelanden maskeras.
- Muntliga svar räcker aldrig för köp, bokningar, meddelanden eller andra externa åtgärder.
  Det krävs alltid skriftlig bekräftelse i chatten.
- Om svaret är osäkert (`needs_clarification`) frågar Claude i chatten i stället för att agera.

## Justeringar

`~/.config/phone-assistant/config.json`: `language` (standard `sv`), `voice` (en röst från ditt
Bland-konto), `cost_per_minute_usd` (sätt det till ditt avtals pris) och `bland_extra` (extra
fält till `POST /v1/calls`).
