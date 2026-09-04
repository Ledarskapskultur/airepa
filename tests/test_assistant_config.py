from app.assistant_config import (
    OPENING_LINE,
    SYSTEM_PROMPT,
    TOOL_SCHEMAS,
    build_assistant_payload,
)


def test_prompten_presenterar_assistenten_som_ai():
    assert "AI-assistent" in OPENING_LINE
    assert OPENING_LINE in SYSTEM_PROMPT


def test_prompten_avvisar_innehallsfragor():
    for ord_ in ("priser", "kursinnehåll", "kursdatum"):
        assert ord_ in SYSTEM_PROMPT
    assert "Det svarar Carl-Fredrik bäst på själv" in SYSTEM_PROMPT


def test_de_tre_verktygen_finns():
    assert [t["name"] for t in TOOL_SCHEMAS] == [
        "hamta_lediga_tider",
        "boka_mote",
        "skicka_meddelande",
    ]


def test_obligatoriska_falt_enligt_kravspec():
    per_namn = {t["name"]: t for t in TOOL_SCHEMAS}
    assert per_namn["boka_mote"]["parameters"]["required"] == ["tid_id", "namn", "telefon"]
    assert per_namn["skicka_meddelande"]["parameters"]["required"] == [
        "namn",
        "telefon",
        "arende",
    ]
    assert "required" not in per_namn["hamta_lediga_tider"]["parameters"]


def test_payload_matchar_installningarna(settings):
    settings.public_base_url = "https://airepa.example.se"
    settings.vapi_voice_id = "voice_abc"
    p = build_assistant_payload(settings)

    assert p["server"]["url"] == "https://airepa.example.se/vapi/webhook"
    assert p["server"]["secret"] == "test-hemlighet"
    assert p["maxDurationSeconds"] == 360
    assert p["silenceTimeoutSeconds"] == 20
    assert p["transcriber"] == {"provider": "deepgram", "model": "nova-2", "language": "sv"}
    assert p["voice"]["voiceId"] == "voice_abc"
    assert p["firstMessage"] == OPENING_LINE
    assert p["model"]["messages"][0]["content"] == SYSTEM_PROMPT
    assert len(p["model"]["tools"]) == 3
    assert all(t["server"]["url"].endswith("/vapi/webhook") for t in p["model"]["tools"])


def test_inget_ljud_spelas_in(settings):
    assert build_assistant_payload(settings)["artifactPlan"]["recordingEnabled"] is False
