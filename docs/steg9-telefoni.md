# Steg 9 – Telefoni (fas 2)

Startas först när fas 1 är godkänd enligt testprotokollet. All kod utom den
här kopplingen är gemensam – assistenten, verktygen och loggningen ändras inte.

## 1. Köp ett svenskt nummer hos 46elks

Dashboard → **Nummer** → köp ett svenskt mobil- eller riktnummer.
Kostar ungefär 20–50 kr/mån.

Byt sedan i `.env`:

```
ELKS_FROM_NUMBER=+46xxxxxxxxx
```

Nu går SMS:en ut från ett riktigt nummer, så mottagaren kan svara.

## 2. Koppla numret till Vapi via SIP

**I Vapi:** Phone Numbers → *Import* → **SIP trunk**. Du får en SIP-URI av
typen `sip:<något>@sip.vapi.ai` och eventuellt användarnamn och lösenord.

**Hos 46elks:** ställ in numret på att vidarekoppla inkommande samtal till den
SIP-adressen. I 46elks görs det med en `voice_start`-URL som svarar:

```json
{ "connect": "sip:ditt-id@sip.vapi.ai" }
```

Enklaste vägen: sätt numrets `voice_start` till en statisk JSON du hostar, eller
lägg till en endpoint i den här servern som returnerar exakt det.

## 3. Peka assistenten på numret

```
uv run python scripts/setup_vapi.py
```

Koppla sedan numret till assistenten i Vapis dashboard (Phone Numbers → välj
numret → *Assistant*), eller via Vapis API.

## 4. Vidarekoppling från Carl-Fredriks mobil

Ställs in i mobilen, ingår inte i koden. På de flesta svenska operatörer:

| Vad | Kod att ringa | Stäng av med |
|---|---|---|
| Vid ej svar (efter ~20 sek) | `**61*+46XXXXXXXXX#` | `##61#` |
| Vid upptaget | `**67*+46XXXXXXXXX#` | `##67#` |
| Vid ej anträffbar (flyg/tunnelbana) | `**62*+46XXXXXXXXX#` | `##62#` |

Byt `+46XXXXXXXXX` mot ditt 46elks-nummer. Ringer du koderna från mobilen
sparas inställningen i nätet, inte i telefonen.

**Sätt inte** ovillkorlig vidarekoppling (`**21*`) – då når ingen dig direkt.

På iPhone finns "vid ej svar" också under Inställningar → Appar → Telefon →
Vidarekoppla samtal, men den knappen sätter oftast ovillkorlig vidarekoppling.
Använd koderna ovan i stället.

## 5. Kör testprotokollet igen

Hela `docs/testprotokoll.md`, men per telefon. Extra att kontrollera:

```
[ ] Uppringarens nummer hamnar i `samtal.fran_nummer`
[ ] Assistenten svarar inom ett par sekunder efter vidarekopplingen
[ ] Ljudkvaliteten håller (ingen eko, inga avhugg)
[ ] Svarslatensen känns under 1,5 sekunder
[ ] Din mobil ringer fortfarande normalt först
```

## Kostnad att räkna med

Vid 30 samtal i månaden à ca 3 minuter:

| Post | Ungefär |
|---|---|
| 46elks nummer | 25 kr/mån |
| 46elks inkommande samtal | 0,20–0,50 kr/min |
| Vapi (STT + LLM + TTS) | ca 0,10 USD/min |
| SMS | ca 0,35 kr/st |
| Hosting + Supabase | 0 kr på gratisnivå |

Grovt: 150–250 kr/månad, inom taket på 300 kr.
