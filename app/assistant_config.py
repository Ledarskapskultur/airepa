"""Systemprompt och verktygsdefinitioner för Vapi-assistenten.

Ligger i repot så att prompten versionshanteras. scripts/setup_vapi.py
skickar upp innehållet härifrån till Vapi.
"""

from __future__ import annotations

from app.config import Settings

OPENING_LINE = (
    "Hej, du har nått Carl-Fredriks AI-assistent. Han är upptagen just nu – "
    "jag kan boka in ett samtal med honom eller ta ett meddelande. Vad passar bäst?"
)

SYSTEM_PROMPT = """Du är telefonassistent till Carl-Fredrik Zettermark, UGL-handledare och ledarskapsutvecklare på Ledarskapskultur. Du talar svenska, kort och vänligt, som en erfaren receptionist – aldrig som säljare.

Öppna alltid med: "Hej, du har nått Carl-Fredriks AI-assistent. Han är upptagen just nu – jag kan boka in ett samtal med honom eller ta ett meddelande. Vad passar bäst?"

Du kan göra exakt två saker:
1. Boka ett 30-minuters telefonmöte med Carl-Fredrik.
2. Ta ett meddelande som han får direkt.

Du svarar INTE på frågor om priser, kursinnehåll, kursdatum, om en kurs passar någon, eller annat om verksamheten. Säg då: "Det svarar Carl-Fredrik bäst på själv – vill du att jag bokar in ett samtal?"

Vid bokning:
- Fråga om det finns någon tid som passar bäst, anropa sedan hamta_lediga_tider.
- Läs upp högst tre tider, en i taget, naturligt.
- När uppringaren valt: be om förnamn och efternamn, sedan mobilnummer. Upprepa numret siffra för siffra och be om bekräftelse.
- Fråga kort vad samtalet gäller (en mening räcker).
- Anropa boka_mote. Bekräfta tiden och säg att en SMS-bekräftelse kommer.

Vid meddelande:
- Be om namn, telefonnummer (upprepa och bekräfta), vad ärendet gäller, och om det brådskar.
- Anropa skicka_meddelande. Säg att Carl-Fredrik återkommer inom en arbetsdag, eller samma dag om det brådskar.

Om uppringaren vill prata med en människa direkt: säg att Carl-Fredrik inte kan nås just nu och erbjud bokning, annars meddelande.

Om uppringaren ringt fel eller inte vill något: tacka vänligt och avsluta.

Avsluta alltid med att i en mening sammanfatta vad som händer härnäst, och säg hej då.

Håll varje replik kort. Ställ en fråga i taget. Använd inte listor eller punkter i tal."""


TOOL_SCHEMAS: list[dict] = [
    {
        "name": "hamta_lediga_tider",
        "description": (
            "Hämtar upp till tre lediga tider för ett 30-minuters telefonmöte. "
            "Anropa när uppringaren vill boka ett samtal."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "onskad_period": {
                    "type": "string",
                    "description": (
                        "Uppringarens önskemål i fritext, t.ex. 'i nästa vecka', "
                        "'på eftermiddagen', 'så snart som möjligt'. Kan vara tom."
                    ),
                }
            },
        },
    },
    {
        "name": "boka_mote",
        "description": (
            "Bokar ett 30-minuters telefonmöte i kalendern. Anropa först när uppringaren "
            "har valt en tid och du har bekräftat namn och mobilnummer."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "tid_id": {"type": "string", "description": "id från hamta_lediga_tider"},
                "namn": {"type": "string"},
                "telefon": {
                    "type": "string",
                    "description": "Mobilnummer, svenskt format",
                },
                "arende": {
                    "type": "string",
                    "description": "Kort beskrivning av vad samtalet gäller, en mening",
                },
            },
            "required": ["tid_id", "namn", "telefon"],
        },
    },
    {
        "name": "skicka_meddelande",
        "description": (
            "Skickar ett meddelande till Carl-Fredrik. Anropa när uppringaren inte vill "
            "boka utan bara lämna ett ärende."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "namn": {"type": "string"},
                "telefon": {"type": "string"},
                "arende": {
                    "type": "string",
                    "description": "Ärendet sammanfattat i 1–2 meningar",
                },
                "bradskande": {"type": "boolean"},
            },
            "required": ["namn", "telefon", "arende"],
        },
    },
]


def build_assistant_payload(settings: Settings) -> dict:
    """Assistenten som den ska se ut hos Vapi."""
    server_url = f"{settings.public_base_url.rstrip('/')}/vapi/webhook"
    server = {"url": server_url}
    if settings.vapi_webhook_secret:
        server["secret"] = settings.vapi_webhook_secret

    voice: dict = {"provider": settings.vapi_voice_provider}
    if settings.vapi_voice_provider == "11labs":
        voice["voiceId"] = settings.vapi_voice_id
        voice["model"] = settings.vapi_voice_model
    else:
        voice["voiceId"] = settings.vapi_voice_id

    return {
        "name": "Carl-Fredriks telefonassistent",
        "firstMessage": OPENING_LINE,
        "firstMessageMode": "assistant-speaks-first",
        "model": {
            "provider": settings.vapi_model_provider,
            "model": settings.vapi_model,
            "temperature": 0.3,
            "messages": [{"role": "system", "content": SYSTEM_PROMPT}],
            "tools": [
                {"type": "function", "function": schema, "server": server}
                for schema in TOOL_SCHEMAS
            ],
        },
        "voice": voice,
        "transcriber": {
            "provider": "deepgram",
            "model": "nova-2",
            "language": "sv",
        },
        "server": server,
        "serverMessages": ["tool-calls", "end-of-call-report", "status-update"],
        "maxDurationSeconds": settings.max_call_seconds,
        "silenceTimeoutSeconds": settings.silence_timeout_seconds,
        "backgroundSound": "off",
        "endCallMessage": "Tack för samtalet. Ha en fin dag!",
        # Endast transkript sparas, inget ljud.
        "artifactPlan": {"recordingEnabled": False, "transcriptPlan": {"enabled": True}},
    }
