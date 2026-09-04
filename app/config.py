"""Inställningar, läses från miljövariabler eller .env."""

from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    # Vapi
    vapi_api_key: str = ""
    vapi_webhook_secret: str = ""
    vapi_public_key: str = ""
    vapi_assistant_id: str = ""

    # 46elks
    elks_api_user: str = ""
    elks_api_password: str = ""
    elks_from_number: str = "CFZ"

    # Mottagare
    owner_phone: str = ""
    owner_name: str = "Carl-Fredrik Zettermark"
    notify_channel: Literal["sms", "email"] = "sms"

    # E-postfallback
    resend_api_key: str = ""
    email_from: str = ""
    owner_email: str = ""

    # Google Calendar
    google_calendar_id: str = "primary"
    google_client_id: str = ""
    google_client_secret: str = ""
    google_refresh_token: str = ""

    # Supabase
    supabase_url: str = ""
    supabase_service_key: str = ""

    # Vapi-assistentens uppsättning (se scripts/setup_vapi.py)
    vapi_model_provider: str = "anthropic"
    vapi_model: str = "claude-sonnet-4-5"
    vapi_voice_provider: str = "11labs"
    vapi_voice_id: str = ""  # väljs av Carl-Fredrik i steg 0b
    vapi_voice_model: str = "eleven_turbo_v2_5"
    max_call_seconds: int = 360
    silence_timeout_seconds: int = 20

    # Övrigt
    tz: str = "Europe/Stockholm"
    public_base_url: str = ""

    # Bokningsregler
    workday_start_hour: int = 8
    workday_end_hour: int = 17
    meeting_minutes: int = 30
    buffer_minutes: int = 15
    max_days_ahead: int = 14
    max_slots: int = 3


@lru_cache
def get_settings() -> Settings:
    return Settings()
