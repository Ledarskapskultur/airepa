"""Tolkar uppringarens fritextönskemål ('i nästa vecka', 'på eftermiddagen')."""

from __future__ import annotations

import re
import unicodedata
from datetime import date, datetime, timedelta

from app.swedish import VECKODAGAR


def _normalisera(text: str) -> str:
    """Gemener utan diakriter, så 'FÖRMIDDAG' och 'formiddag' matchar likadant."""
    utan = unicodedata.normalize("NFKD", (text or "").lower())
    return "".join(c for c in utan if not unicodedata.combining(c))


FORMIDDAG = ("formiddag", "morgon", "fore lunch", "innan lunch", "tidigt pa dagen")
EFTERMIDDAG = ("eftermiddag", "efter lunch", "sent pa dagen", "kvall")


def _onskad_veckodag(text: str) -> int | None:
    for i, dag in enumerate(VECKODAGAR):
        if _normalisera(dag) in text:
            return i
    return None


def matchar_onskemal(slot_start: datetime, onskad_period: str, idag: date) -> bool:
    """True om tiden stämmer med önskemålet. Tomt önskemål matchar allt."""
    text = _normalisera(onskad_period)
    if not text.strip():
        return True

    krav: list[bool] = []

    if any(ord_ in text for ord_ in FORMIDDAG):
        krav.append(slot_start.hour < 12)
    if any(ord_ in text for ord_ in EFTERMIDDAG):
        krav.append(slot_start.hour >= 12)

    if re.search(r"\bnasta vecka\b", text):
        krav.append(_veckonummer(slot_start.date()) == _veckonummer(idag + timedelta(days=7)))
    elif re.search(r"\b(denna vecka|den har veckan|har veckan|innevarande vecka)\b", text):
        krav.append(_veckonummer(slot_start.date()) == _veckonummer(idag))

    if re.search(r"\bimorgon\b|\bi morgon\b", text):
        krav.append(slot_start.date() == idag + timedelta(days=1))

    veckodag = _onskad_veckodag(text)
    if veckodag is not None:
        krav.append(slot_start.weekday() == veckodag)

    # "så snart som möjligt" är ingen filtrering – tiderna kommer redan i tidsordning.
    return all(krav)


def _veckonummer(d: date) -> tuple[int, int]:
    iso = d.isocalendar()
    return (iso[0], iso[1])
