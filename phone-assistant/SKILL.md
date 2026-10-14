---
name: phone-assistant
description: Ring användarens eget verifierade mobilnummer via Bland.ai, ställ en kort fråga på svenska, ta emot det muntliga svaret och för tillbaka det till det pågående arbetet. Använd BARA när användaren uttryckligen ber dig ringa ("ring mig", "ring och fråga", "/phone-assistant"), eller när du behöver ett beslut och användaren först har godkänt samtalet i chatten.
---

# phone-assistant

Personlig AI-telefon. Skriptet ligger bredvid den här filen:

```bash
PA="python3 ~/.claude/skills/phone-assistant/phone_assistant.py"
```

Allt skriptet skriver ut är JSON. Nyckeln skrivs aldrig ut.

## Hårda regler (bryt aldrig mot dem)

1. **Ring aldrig utan godkännande.** Före varje `ask` eller `test` ställer du frågan till
   användaren i chatten (AskUserQuestion om verktyget finns) och visar exakt vilken fråga som
   ska läsas upp, samtalets maxlängd och den uppskattade maxkostnaden. Lägg till `--confirm`
   först efter ett tydligt "ja". Ett godkännande gäller ett enda samtal.
2. **Bara det egna numret.** Skriptet ringer bara `owner_number` i konfigurationen. Det finns
   ingen flagga för att ringa någon annan. Försök inte kringgå det, och ändra inte config-filen.
3. **Gränser.** Respektera skriptets tak för samtal per timme och dygn, samtalslängd och
   kostnad. Om ett tak nås: rapportera det, höj det inte själv. Bara användaren kör `set-limit`.
4. **Inga externa åtgärder enbart på muntligt svar.** Köp, bokningar, betalningar, att skicka
   mejl, SMS eller meddelanden, att publicera, radera eller driftsätta: det kräver alltid en
   skriftlig bekräftelse i chatten efter samtalet, även om svaret i samtalet lät tydligt.
5. **Osäker transkription → be om förtydligande.** Om `needs_clarification` är `true`, eller om
   svaret kan tolkas på flera sätt, agerar du inte. Visa transkriptionen och fråga i chatten.
   Ring igen bara med ett nytt godkännande.
6. **Inga hemligheter i samtal.** Läs aldrig upp nycklar, lösenord, kunddata eller annat
   känsligt. Fråga aldrig efter koder eller kortuppgifter i telefon.

## Arbetsflöde

### 1. Förkontroll (ringer inte)
```bash
$PA check
```
Kontrollera `api_connection: "ok"`, `owner_number`, `number_verified: true` och saldo.
- `BLAND_API_KEY saknas`: be användaren köra `! python3 ~/.claude/skills/phone-assistant/phone_assistant.py setup-key`
  själv i sin terminal (`!`-prefixet i Claude Code), eller sätta miljövariabeln. Be **aldrig**
  användaren klistra in nyckeln i chatten.
- `Inget eget nummer`: fråga efter numret och kör `$PA set-number +467XXXXXXXX`.
- Inte verifierat: gör testsamtalet (avsnitt 4).

### 2. Formulera frågan
Kort, en sak i taget, går att svara på muntligt, högst cirka 25 ord. Ge gärna 2–3 alternativ.
Exempel: "Ska jag använda Postgres eller SQLite för den nya tjänsten?"
Bakgrund som AI:n kan använda om du frågar läggs i `--context` (kort, inget känsligt).

### 3. Be om godkännande och ring
Visa: frågan, maxlängd (`max_duration_minutes`) och uppskattad maxkostnad
(`max_duration_minutes × cost_per_minute_usd`). Efter ett ja:
```bash
$PA ask --question "…" --context "…" --confirm
```
Kommandot väntar tills samtalet är slut (högst samtalslängden plus cirka 3 minuter). Kör det i
förgrunden med tillräcklig timeout (`timeout: 600000`).

AI:n i telefon ställer frågan, lyssnar, upprepar sin tolkning ("Jag uppfattade att du vill …
Stämmer det?") och ber om förtydligande om svaret är otydligt.

### 4. Testsamtal (första gången)
Efter godkännande: `$PA test --confirm`. AI:n säger exakt:
> "Hej! Det här är din AI-assistent som ringer via Claude Code. Jag vill kontrollera att vår
> telefonkoppling fungerar. Vilken uppgift vill du att jag ska hjälpa dig med idag?"

Visa `transcript` och `user_answer`. Fråga om det stämmer. Kör `$PA verify <call_id>` först
när användaren bekräftar att det var hen som svarade. Utan det fungerar `ask` inte.

### 5. Tolka resultatet och fortsätt
Resultatets fält: `status`, `transcript`, `user_answer`, `summary`, `confirmed_on_call`,
`needs_clarification`, `uncertainty_reasons`, `price_usd`, `transcript_file`.

1. Visa alltid transkriptionen och kostnaden i chatten.
2. Skriv: **"Jag tolkar ditt svar som: … – jag fortsätter med det."**
3. Om `needs_clarification` är `true`, eller `confirmed_on_call` är `false` och svaret
   påverkar något svåråterkalleligt: fråga i chatten innan du fortsätter.
4. Om svaret innebär en extern åtgärd (regel 4): be om skriftlig bekräftelse först.
5. Fortsätt annars den ursprungliga uppgiften med svaret som instruktion.

Fel som `status: no-answer`, `busy` eller `timeout`: rapportera och fråga om du ska försöka
igen senare. Ring inte om automatiskt.

## Övriga kommandon
| Kommando | Vad |
|---|---|
| `$PA config` | Visa inställningar (maskat nummer, aldrig nyckeln) |
| `$PA usage` | Samtal och kostnad senaste dygnet |
| `$PA status <id>` / `transcript <id>` | Hämta status eller transkription i efterhand |
| `$PA stop <id>` | Avbryt ett pågående samtal |
| `$PA set-limit <namn> <värde>` | Ändra en gräns. **Bara på användarens begäran.** |

Loggar: `~/.local/state/phone-assistant/calls.jsonl`. Transkriptioner (0600):
`~/.local/state/phone-assistant/transcripts/`. Ljud spelas inte in (`record: false`).
