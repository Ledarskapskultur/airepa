import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# Testerna ska aldrig läsa en riktig .env eller nå ett riktigt API.
os.environ.setdefault("VAPI_WEBHOOK_SECRET", "test-hemlighet")
os.environ.setdefault("OWNER_PHONE", "+46701112233")
os.environ.setdefault("ELKS_API_USER", "u")
os.environ.setdefault("ELKS_API_PASSWORD", "p")
os.environ.setdefault("ELKS_FROM_NUMBER", "CFZ")

import pytest  # noqa: E402

from app.config import Settings  # noqa: E402


@pytest.fixture
def settings() -> Settings:
    return Settings(
        _env_file=None,
        vapi_webhook_secret="test-hemlighet",
        owner_phone="+46701112233",
        elks_api_user="u",
        elks_api_password="p",
        elks_from_number="CFZ",
        google_calendar_id="primary",
        tz="Europe/Stockholm",
    )
