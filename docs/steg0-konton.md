# Steg 0 – Konton och nycklar du behöver skaffa

Det här är den enda delen ingen kan göra åt dig. Räkna med ungefär en timme.
Allt fylls i i din `.env` (kopiera `.env.example` till `.env` först).

## Fas 1 – webbmikrofon, inget telefonnummer

### 1. Vapi (röstplattformen)
- Skapa konto: https://dashboard.vapi.ai
- Gratiskrediterna (ca 10 USD) räcker gott för hela fas 1.
- **Organization → API Keys**:
  - *Private key* → `VAPI_API_KEY` (används av servern och `setup_vapi.py`)
  - *Public key* → `VAPI_PUBLIC_KEY` (används av webbsidan, får synas publikt)
- `VAPI_WEBHOOK_SECRET`: hitta på en lång slumpsträng själv, t.ex.
  `openssl rand -hex 24`. Samma sträng läggs in i Vapi som *Server URL Secret*
  (det gör `setup_vapi.py` åt dig).
- `VAPI_ASSISTANT_ID` fylls i efter steg 0b/6.

### 2. ElevenLabs (rösten)
- Ingår via Vapi om du använder Vapis egna röstkrediter. Vill du ha ett eget
  konto med fler röster: https://elevenlabs.io
- Röst-ID:t du väljer i steg 0b läggs in som `VAPI_VOICE_ID`.

### 3. Google Cloud (kalendern)
- Skapa projekt: https://console.cloud.google.com/projectcreate
- Aktivera **Google Calendar API**:
  https://console.cloud.google.com/apis/library/calendar-json.googleapis.com
- **APIs & Services → OAuth consent screen**: välj *External*, lägg till din
  egen e-postadress som testanvändare. Appen behöver inte publiceras.
- **APIs & Services → Credentials → Create credentials → OAuth client ID**,
  typ **Desktop app**:
  - Client ID → `GOOGLE_CLIENT_ID`
  - Client secret → `GOOGLE_CLIENT_SECRET`
- Kör sedan en gång på din egen dator:
  `uv run python scripts/auth_google.py` → ger dig `GOOGLE_REFRESH_TOKEN`.
- `GOOGLE_CALENDAR_ID`: `primary` om det är din vanliga kalender. Annars hittar
  du id:t i Google Kalender under *Inställningar → din kalender → Integrera
  kalender*.

> Varför OAuth och inte ett service account? Ett service account kommer inte åt
> en privat Gmail-kalender utan Workspace-delegering. Med refresh token bokar
> assistenten i din egen kalender direkt.

### 4. Supabase (loggning)
- Skapa projekt: https://supabase.com/dashboard
- **Project Settings → API**:
  - Project URL → `SUPABASE_URL`
  - `service_role`-nyckeln → `SUPABASE_SERVICE_KEY`
    (**hemlig** – bara på servern, aldrig i webbsidan)
- Kör innehållet i `migrations/001_init.sql` i **SQL Editor**.

### 5. 46elks (SMS)
- Skapa konto: https://46elks.se – du behöver **inget telefonnummer** i fas 1,
  bara kontot för att skicka SMS.
- **Dashboard → API-nycklar**:
  - API username → `ELKS_API_USER`
  - API password → `ELKS_API_PASSWORD`
- `ELKS_FROM_NUMBER=CFZ` – alfanumerisk avsändare i fas 1 (max 11 tecken).
  Obs: mottagaren kan inte svara på ett SMS med alfanumerisk avsändare.
- `OWNER_PHONE` = din mobil i `+46`-format.

**Vill du vänta med 46elks?** Sätt `NOTIFY_CHANNEL=email` och skaffa i stället
en gratisnyckel hos https://resend.com → `RESEND_API_KEY`, `EMAIL_FROM`,
`OWNER_EMAIL`. Då mejlas bokningar och meddelanden till dig i stället.
Bekräftelsen till uppringaren kräver dock SMS – utan 46elks får uppringaren
bara assistentens muntliga bekräftelse.

### 6. Hosting
- **Railway** (https://railway.app) eller **Vercel** – gratisnivå räcker.
- Sätt samma miljövariabler där som i din `.env`.
- Adressen du får → `PUBLIC_BASE_URL`, t.ex. `https://airepa.up.railway.app`.

## Fas 2 – tillkommer när fas 1 är godkänd

| Vad | Var | Kostnad |
|---|---|---|
| Svenskt telefonnummer | 46elks dashboard → Nummer | ca 20–50 kr/mån |
| SIP-trunk mot Vapi | Vapi → Phone Numbers → *Import SIP* | ingår |
| Vidarekoppling vid "ej svar" | Ställs in i din mobil, ingen kod | 0 kr |

När numret finns: byt `ELKS_FROM_NUMBER` till numret i `+46`-format, så kan
mottagare svara på SMS:en. Se `docs/steg9-telefoni.md`.

## Snabb checklista

```
[ ] VAPI_API_KEY, VAPI_PUBLIC_KEY, VAPI_WEBHOOK_SECRET
[ ] GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET, GOOGLE_REFRESH_TOKEN, GOOGLE_CALENDAR_ID
[ ] SUPABASE_URL, SUPABASE_SERVICE_KEY + migrationen körd
[ ] ELKS_API_USER, ELKS_API_PASSWORD, ELKS_FROM_NUMBER, OWNER_PHONE
[ ] PUBLIC_BASE_URL (efter deploy)
[ ] VAPI_VOICE_ID (efter steg 0b)
[ ] VAPI_ASSISTANT_ID (efter setup_vapi.py)
```
