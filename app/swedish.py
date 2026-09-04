"""Talvänlig svenska: datum och klockslag som en människa säger dem."""

from __future__ import annotations

import re
from datetime import datetime

VECKODAGAR = [
    "måndag",
    "tisdag",
    "onsdag",
    "torsdag",
    "fredag",
    "lördag",
    "söndag",
]

MANADER = [
    "januari",
    "februari",
    "mars",
    "april",
    "maj",
    "juni",
    "juli",
    "augusti",
    "september",
    "oktober",
    "november",
    "december",
]

# Timmarna sägs som ord i 12-timmarsform: 14 -> "två", 9 -> "nio".
TIMORD = [
    "tolv",
    "ett",
    "två",
    "tre",
    "fyra",
    "fem",
    "sex",
    "sju",
    "åtta",
    "nio",
    "tio",
    "elva",
]


def _timme_ord(hour24: int) -> str:
    """12-timmarsform som ord. 13 -> 'ett', 12 -> 'tolv', 8 -> 'åtta'."""
    return TIMORD[hour24 % 12]


def klockslag_text(dt: datetime) -> str:
    """Klockslag som det sägs på svenska.

    08:00 -> 'klockan 8'          (hela timmar sägs med siffra, som i kravspecen)
    14:30 -> 'klockan halv tre'
    09:15 -> 'klockan kvart över nio'
    09:45 -> 'klockan kvart i tio'
    """
    h, m = dt.hour, dt.minute
    if m == 0:
        return f"klockan {h % 12 or 12}"
    if m == 30:
        return f"klockan halv {_timme_ord(h + 1)}"
    if m == 15:
        return f"klockan kvart över {_timme_ord(h)}"
    if m == 45:
        return f"klockan kvart i {_timme_ord(h + 1)}"
    if m < 30:
        return f"klockan {m} över {_timme_ord(h)}"
    return f"klockan {60 - m} i {_timme_ord(h + 1)}"


def datum_text(dt: datetime) -> str:
    """'måndag 8 september'."""
    return f"{VECKODAGAR[dt.weekday()]} {dt.day} {MANADER[dt.month - 1]}"


def tid_text(dt: datetime) -> str:
    """'måndag 8 september klockan halv tre'."""
    return f"{datum_text(dt)} {klockslag_text(dt)}"


# --- Telefonnummer ---------------------------------------------------------

def normalisera_telefon(nummer: str) -> str:
    """Gör om ett svenskt mobilnummer till +46-format.

    Talstyrda nummer kommer ofta som '070 123 45 67' eller 'noll sju noll...'
    (transkriberat till siffror). Vi städar bort allt utom siffror och plus.
    Okända format returneras rensade men oförändrade i övrigt.
    """
    rensat = re.sub(r"[^\d+]", "", nummer or "")
    if not rensat:
        return ""
    if rensat.startswith("+"):
        return "+" + re.sub(r"\D", "", rensat[1:])
    if rensat.startswith("00"):
        return "+" + rensat[2:]
    if rensat.startswith("0"):
        return "+46" + rensat[1:]
    if rensat.startswith("46"):
        return "+" + rensat
    return rensat
