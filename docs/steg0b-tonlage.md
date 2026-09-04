# Steg 0b – Provlyssna och välj röst

Görs **innan** verktygen kopplas på. Syftet är bara att höra om tonläget känns
rätt och att välja röst.

## Gör så här

1. Gå till https://dashboard.vapi.ai → **Assistants** → *Create Assistant* →
   börja från *Blank*.
2. **Model**: Anthropic Claude eller OpenAI GPT – välj den senaste som finns i
   listan. Temperature 0.3.
3. **System prompt**: klistra in hela prompten. Den finns ordagrant i
   `app/assistant_config.py` (`SYSTEM_PROMPT`), eller kör:
   `uv run python -c "from app.assistant_config import SYSTEM_PROMPT; print(SYSTEM_PROMPT)"`
4. **First message**: klistra in öppningsraden (`OPENING_LINE` i samma fil).
5. **Voice**: ElevenLabs, filtrera på svenska. Modell `eleven_turbo_v2_5`.
6. **Transcriber**: Deepgram, modell `nova-2`, språk `sv`.
7. **Advanced**: Max duration 360 sekunder, Silence timeout 20 sekunder.
8. Lägg **inte** till några verktyg ännu.
9. Tryck **Talk** och prata med assistenten.

## Prova minst det här

- Säg "hej" och lyssna på öppningen. Låter den som en receptionist eller som
  en säljare?
- Fråga "vad kostar en UGL-kurs?" → ska hänvisa till ett bokat samtal.
- Säg "jag vill boka en tid" → ska fråga om vilken tid som passar. (Utan
  verktyg kan den inte hämta tider – det är väntat i det här steget.)
- Avbryt mitt i en mening → ska sluta prata direkt.

## Anteckna innan du går vidare

| Fråga | Ditt svar |
|---|---|
| Vald röst (namn) | |
| Röst-ID (kopieras från Vapi) | → `VAPI_VOICE_ID` i `.env` |
| Modell som lät bäst på svenska | → `VAPI_MODEL_PROVIDER` + `VAPI_MODEL` |
| Talar den för fort eller för långsamt? | |
| Något i prompten som ska ändras? | |

Promptjusteringar görs i `app/assistant_config.py`, inte i dashboarden – annars
skriver `setup_vapi.py` över dem i steg 6.

När det här är klart: gå vidare till steg 1–7. Den assistent du skapade för
hand kan du radera, eller låta `setup_vapi.py` ta över genom att lägga dess id
i `VAPI_ASSISTANT_ID`.
